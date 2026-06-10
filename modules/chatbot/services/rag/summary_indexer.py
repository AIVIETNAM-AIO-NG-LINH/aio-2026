"""Sinh tóm tắt tài liệu (Gemini Flash) + index vào OpenSearch summary index.

Sau khi rag-index chính đã xong, bước này tạo 1 doc/tài liệu trong index riêng
(`OPENSEARCH_SUMMARY_INDEX`): tóm tắt ≤200 ký tự + vector 768 chiều để truy hồi
nhanh ở mức tài liệu. Toàn bộ fail-safe — lỗi ở đây KHÔNG làm hỏng rag-index
chính, pipeline chỉ log rồi bỏ qua (xem `pipeline.py`).

Idempotent theo `document_id`: doc id = str(document_id) nên re-ingest ghi đè.
"""

from __future__ import annotations

import logging
from typing import Any

from opensearchpy import OpenSearch

from .config import GeminiConfig, OpenSearchConfig
from .embedder import embed_chunks
from .gemini_client import build_client

logger = logging.getLogger(__name__)

# Giới hạn cứng độ dài tóm tắt (ký tự) — khớp mapping/UI mong đợi.
_SUMMARY_MAX_CHARS = 200

# Cắt bớt text đầu vào trước khi nhờ Gemini tóm tắt (tránh payload quá lớn; phần
# đầu tài liệu thường đủ để tóm tắt tổng quan).
_SUMMARY_INPUT_MAX_CHARS = 12000

_SUMMARY_PROMPT = (
    "Summarize the following document in at most 200 characters. "
    "Write one concise sentence capturing the main topic. "
    "Return ONLY the summary text, no preamble or quotes.\n\n"
    "DOCUMENT:\n"
)


class SummaryIndexer:
    """Tạo summary index (nếu chưa có) và ghi 1 doc tóm tắt cho mỗi tài liệu."""

    def __init__(self, os_config: OpenSearchConfig, gemini_config: GeminiConfig) -> None:
        self._os_config = os_config
        self._gemini_config = gemini_config
        self._client = self._build_client(os_config)

    @staticmethod
    def _build_client(config: OpenSearchConfig) -> OpenSearch:
        http_auth = (config.user, config.password) if config.user else None
        return OpenSearch(
            hosts=[config.url],
            http_auth=http_auth,
            verify_certs=config.verify_certs,
            ssl_show_warn=config.verify_certs,
        )

    # --- Mapping / index ---------------------------------------------------
    def _index_body(self) -> dict[str, Any]:
        """Mapping summary index: knn bật, summary_vector HNSW/lucene/cosinesimil."""
        return {
            "settings": {"index": {"knn": True}},
            "mappings": {
                "properties": {
                    "document_id": {"type": "long"},
                    "media_id": {"type": "long"},
                    "summary_text": {"type": "text"},
                    "summary_vector": {
                        "type": "knn_vector",
                        "dimension": self._os_config.vector_dims,
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
        index = self._os_config.summary_index
        if self._client.indices.exists(index=index):
            return
        logger.info("[summary] tạo index '%s'", index)
        self._client.indices.create(index=index, body=self._index_body())

    # --- Sinh tóm tắt ------------------------------------------------------
    def _summarize(self, text: str) -> str:
        """Gọi Gemini Flash sinh tóm tắt ≤200 ký tự (cắt cứng nếu model trả dài hơn)."""
        client = build_client(self._gemini_config)
        prompt = _SUMMARY_PROMPT + text[:_SUMMARY_INPUT_MAX_CHARS]
        response = client.models.generate_content(
            model=self._gemini_config.summary_model,
            contents=[prompt],
        )
        summary = (response.text or "").strip()
        if len(summary) > _SUMMARY_MAX_CHARS:
            summary = summary[:_SUMMARY_MAX_CHARS].rstrip()
        return summary

    # --- Ghi document ------------------------------------------------------
    def index_summary(self, document_id: int, media_id: int, text: str) -> bool:
        """Sinh tóm tắt + embed + ghi 1 doc (idempotent theo document_id).

        Trả True nếu index thành công, False nếu bỏ qua (text rỗng / không tóm tắt
        được / embed sai chiều). Caller bọc try/except nên hàm này có thể raise —
        pipeline nuốt lỗi và giữ status READY.
        """
        if not text or not text.strip():
            logger.warning("[summary] document_id=%s text rỗng, bỏ qua", document_id)
            return False

        summary = self._summarize(text)
        if not summary:
            logger.warning("[summary] document_id=%s Gemini trả tóm tắt rỗng, bỏ qua", document_id)
            return False

        # Tái dùng embedder Phase 1 (đảm bảo đúng số chiều); lấy vector đầu tiên.
        embedded = embed_chunks([summary], self._os_config.vector_dims, self._gemini_config)
        if not embedded:
            logger.warning(
                "[summary] document_id=%s không embed được tóm tắt (sai chiều?), bỏ qua",
                document_id,
            )
            return False
        summary_vector = embedded[0][1]

        self._ensure_index()
        self._client.index(
            index=self._os_config.summary_index,
            id=str(document_id),
            body={
                "document_id": document_id,
                "media_id": media_id,
                "summary_text": summary,
                "summary_vector": summary_vector,
            },
            refresh=True,
        )
        logger.info(
            "[summary] document_id=%s đã index tóm tắt (%d ký tự)", document_id, len(summary)
        )
        return True
