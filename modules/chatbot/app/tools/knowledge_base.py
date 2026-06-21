"""Tool truy hồi chunk (knowledge base) cho chatbot — KHÔNG sinh câu trả lời LLM.

Một function thuần `search()` (stateless), không bọc class/Response — việc
dựng Response là của controller, còn đây chỉ là "công cụ" trả LIST chunk. Dùng bởi
ADK agent qua `adk/tools.py` (`search_knowledge_base`).

Luồng (mỗi bước fail-safe, hỏng bước phụ không làm chết truy hồi):
  1) Embed query (task_type=RETRIEVAL_QUERY, 768 chiều, L2-normalize); lỗi → None.
  2) Hybrid search OpenSearch (BM25 + kNN) hợp nhất RRF → top_n ứng viên kèm `page`.
  3) Rerank cross-encoder QUA HTTP trên (query, chunk_text) → xếp lại; tắt/lỗi → giữ hybrid.
  4) Cắt top_k, trả JSON list {chunk_text, score, document_id, media_id, original_name, page}.

Số trang được surface để caller/LLM trích "trang X". Đồng bộ (xử lý trong request) —
truy hồi nhanh, khác ingest chạy nền qua Celery.
"""

from __future__ import annotations

import logging

from ..rag.config import RerankConfig, RetrieveConfig
from ..rag.embedder import embed_query
from ..rag.reranker_client import rerank

logger = logging.getLogger(__name__)


def search(
    query: str,
    top_k: int | None = None,
    top_n: int | None = None,
) -> list[dict]:
    """Truy hồi thuần (embed → hybrid → rerank), trả LIST chunk.

    `top_k`/`top_n` None → lấy default từ env. Mỗi chunk:
    {chunk_text, score, document_id, media_id, original_name, page}.
    """
    rerank_config = RerankConfig.from_env()
    retrieve_config = RetrieveConfig.from_env()

    # Lazy import — tránh circular import với services/__init__.
    from ..opensearch import Retriever

    retriever = Retriever()  # tự đọc env OPENSEARCH_* (base client)

    top_k = top_k or retrieve_config.top_k
    top_n = top_n or retrieve_config.top_n
    query = (query or "").strip()

    # 1) Embed query (RETRIEVAL_QUERY). Vector None → chỉ chạy BM25.
    query_vector = embed_query(query, retriever.vector_dims)

    # 2) Hybrid search (BM25 + kNN) + RRF → top_n ứng viên (kèm metadata parent + page).
    candidates = retriever.retrieve(
        query, query_vector, top_n=top_n, rrf_k=retrieve_config.rrf_k
    )

    # 3) Rerank theo query → xếp lại; tắt/lỗi → giữ hybrid.
    ranked = rerank(query, candidates, rerank_config)

    # 3b) Lọc theo ngưỡng điểm liên quan — CHỈ khi rerank thực sự chạy (item có
    # `rerank_score`; điểm RRF hybrid không cùng thang nên không áp ngưỡng cho nó,
    # fail-safe). Câu hỏi ngoài phạm vi tài liệu → mọi chunk dưới ngưỡng bị loại →
    # trả [] → agent từ chối ("không có trong tài liệu") thay vì ghép từ nhiễu.
    threshold = rerank_config.score_threshold
    reranked = any("rerank_score" in c for c in ranked)
    if threshold > 0 and reranked:
        kept = [c for c in ranked if c.get("rerank_score", 0.0) >= threshold]
        if len(kept) != len(ranked):
            logger.info(
                "[retrieve] lọc ngưỡng %.3f: %d → %d chunk đạt",
                threshold,
                len(ranked),
                len(kept),
            )
        ranked = kept

    # 4) Cắt top_k, build payload trả về (số trang surface cho caller).
    items = [
        {
            "chunk_text": c.get("chunk_text", ""),
            "score": c.get("rerank_score", c.get("score")),
            "document_id": c.get("document_id"),
            "media_id": c.get("media_id"),
            "original_name": c.get("original_name"),
            "page": c.get("page"),
        }
        for c in ranked[:top_k]
    ]

    logger.info(
        "[retrieve] query=%r candidates=%d trả=%d",
        query,
        len(candidates),
        len(items),
    )
    return items
