"""Trí nhớ dài hạn (LTM) của hội thoại — index + truy hồi trên OpenSearch.

Mỗi lượt hỏi-đáp hoàn tất được index thành 1 doc: text "User: ...\\nAssistant: ..."
+ vector 768 chiều (embed từ CÂU HỎI, task RETRIEVAL_DOCUMENT). Khi user hỏi câu
mới, ta embed câu hỏi (RETRIEVAL_QUERY) rồi kNN trong phạm vi user_id để lấy vài
lượt hội thoại cũ liên quan làm ngữ cảnh — giúp bot "nhớ" xuyên hội thoại.

Toàn bộ FAIL-SAFE: lỗi OpenSearch/embed KHÔNG làm hỏng luồng chat (chỉ log, trả
rỗng). Index tạo lười (lazy) lần ghi đầu.
"""

from __future__ import annotations

import logging
from typing import Any

from modules.base.clients.opensearch_client import BaseOpenSearchClient

from ..rag.embedder import embed_chunks, embed_query
from .config import ChatConfig

logger = logging.getLogger(__name__)


class ChatHistoryIndex(BaseOpenSearchClient):
    """Đọc/ghi index lịch sử hội thoại (vector) cho LTM."""

    def __init__(self, chat_config: ChatConfig) -> None:
        super().__init__()
        self._chat_config = chat_config

    # --- Mapping / index ---------------------------------------------------
    def _index_body(self) -> dict[str, Any]:
        return {
            "settings": {"index": {"knn": True}},
            "mappings": {
                "properties": {
                    "conversation_id": {"type": "long"},
                    "user_id": {"type": "long"},
                    "content": {"type": "text"},
                    "content_vector": {
                        "type": "knn_vector",
                        "dimension": self.vector_dims,
                        "method": {
                            "name": "hnsw",
                            "engine": "lucene",
                            "space_type": "cosinesimil",
                            "parameters": {"ef_construction": 128, "m": 16},
                        },
                    },
                }
            },
        }

    def _ensure_index(self) -> None:
        index = self._chat_config.ltm_index
        if self._client.indices.exists(index=index):
            return
        logger.info("[ltm] tạo index '%s'", index)
        self._client.indices.create(index=index, body=self._index_body())

    # --- Ghi ----------------------------------------------------------------
    def index_turn(
        self,
        conversation_id: int,
        user_id: int,
        question: str,
        answer: str,
    ) -> bool:
        """Index 1 lượt hỏi-đáp. Trả True nếu ghi thành công, False nếu bỏ qua.

        Vector lấy từ CÂU HỎI (document side) để khớp với câu hỏi tương lai. Caller
        nên bọc try/except (task Celery) — fail-safe ở mức luồng chat.
        """
        question = (question or "").strip()
        answer = (answer or "").strip()
        if not question or not answer:
            return False

        embedded = embed_chunks([question], self.vector_dims)
        if not embedded:
            logger.warning("[ltm] conv=%s không embed được câu hỏi, bỏ qua", conversation_id)
            return False
        vector = embedded[0][1]

        self._ensure_index()
        self._client.index(
            index=self._chat_config.ltm_index,
            body={
                "conversation_id": conversation_id,
                "user_id": user_id,
                "content": f"User: {question}\nAssistant: {answer}",
                "content_vector": vector,
            },
            refresh=False,
        )
        logger.info("[ltm] conv=%s đã index 1 lượt hội thoại", conversation_id)
        return True

    # --- Đọc ----------------------------------------------------------------
    def search(self, user_id: int, query: str) -> str:
        """kNN trong phạm vi user_id → ghép text các lượt liên quan (≥ min_score).

        Trả chuỗi rỗng nếu LTM tắt / index chưa có / không đủ điểm / lỗi (fail-safe).
        """
        query = (query or "").strip()
        if not query:
            return ""

        vector = embed_query(query, self.vector_dims)
        if vector is None:
            return ""

        top_k = self._chat_config.ltm_top_k
        body = {
            "size": top_k,
            "_source": ["content"],
            "query": {
                "bool": {
                    "filter": [{"term": {"user_id": user_id}}],
                    "must": [
                        {"knn": {"content_vector": {"vector": vector, "k": top_k}}}
                    ],
                }
            },
        }
        try:
            response = self._client.search(index=self._chat_config.ltm_index, body=body)
        except Exception:
            logger.exception("[ltm] lỗi search (bỏ qua, trả rỗng)")
            return ""

        hits = response.get("hits", {}).get("hits", [])
        parts: list[str] = []
        for hit in hits:
            if hit.get("_score", 0.0) < self._chat_config.ltm_min_score:
                continue
            content = (hit.get("_source", {}) or {}).get("content", "").strip()
            if content:
                parts.append(content)
        return "\n\n".join(parts)
