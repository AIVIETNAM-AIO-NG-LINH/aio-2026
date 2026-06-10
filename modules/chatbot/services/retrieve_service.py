"""Nghiệp vụ truy hồi chunk cho chatbot — KHÔNG sinh câu trả lời LLM.

Luồng (mỗi bước fail-safe, hỏng bước phụ không làm chết truy hồi):
  1) Query rewriting (Gemini Flash, Việt↔Anh) → list truy vấn; lỗi/tắt → chỉ query gốc.
  2) Embed mỗi truy vấn (task_type=RETRIEVAL_QUERY, 768 chiều, L2-normalize); lỗi → None.
  3) Hybrid search OpenSearch (BM25 + kNN) hợp nhất RRF → top_n ứng viên kèm `page`.
  4) Rerank cross-encoder QUA HTTP trên (query GỐC, chunk_text) → xếp lại; tắt/lỗi → giữ hybrid.
  5) Cắt top_k, trả JSON list {chunk_text, score, document_id, media_id, original_name, page}.

Số trang được surface để caller/LLM trích "trang X". Service đồng bộ (xử lý trong
request) — truy hồi nhanh, khác ingest chạy nền qua Celery.
"""

from __future__ import annotations

import logging

from rest_framework import status as http_status
from rest_framework.response import Response

from modules.base.services import BaseService

from ..requests import RetrieveDTO
from .rag.config import (
    GeminiConfig,
    OpenSearchConfig,
    QueryRewriteConfig,
    RerankConfig,
    RetrieveConfig,
)
from .rag.embedder import embed_query
from .rag.query_rewriter import rewrite_query
from .rag.reranker_client import rerank
from .rag.retriever import Retriever

logger = logging.getLogger(__name__)


class RetrieveService(BaseService):
    """Điều phối rewrite → embed → hybrid → rerank, trả top_k chunk (không sinh LLM)."""

    def retrieve(self, dto: RetrieveDTO) -> Response:
        gemini_config = GeminiConfig.from_env()
        opensearch_config = OpenSearchConfig.from_env()
        rewrite_config = QueryRewriteConfig.from_env()
        rerank_config = RerankConfig.from_env()
        retrieve_config = RetrieveConfig.from_env()

        # Override default env bằng giá trị request nếu có.
        top_k = dto.top_k or retrieve_config.top_k
        top_n = dto.top_n or retrieve_config.top_n
        query = dto.query.strip()

        # 1) Query rewriting (fail-safe → chỉ query gốc).
        variants = rewrite_query(query, gemini_config, rewrite_config)

        # 2) Embed từng biến thể (RETRIEVAL_QUERY). Vector None → variant chỉ chạy BM25.
        query_variants = [
            (text, embed_query(text, opensearch_config.vector_dims, gemini_config))
            for text in variants
        ]

        # 3) Hybrid search + RRF → top_n ứng viên (kèm metadata parent + page).
        candidates = Retriever(opensearch_config).retrieve(
            query_variants, top_n=top_n, rrf_k=retrieve_config.rrf_k
        )

        # 4) Rerank theo QUERY GỐC (không phải biến thể) → xếp lại; tắt/lỗi → giữ hybrid.
        ranked = rerank(query, candidates, rerank_config)

        # 5) Cắt top_k, build payload trả về (số trang surface cho caller).
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
            "[retrieve] query=%r variants=%d candidates=%d trả=%d",
            query,
            len(variants),
            len(candidates),
            len(items),
        )
        return self.response_success(
            {"query": query, "count": len(items), "results": items},
            status=http_status.HTTP_200_OK,
        )
