"""Hybrid retrieval trên `rag-index` (parent-child): BM25 + kNN, hợp nhất bằng RRF.

Query chạy 2 lượt search trên CHILD doc: BM25 trên `chunk_text` và kNN trên
`chunk_vector`. Hai danh sách kết quả được hợp nhất bằng Reciprocal Rank Fusion
(RRF) — không cần search pipeline hybrid của OpenSearch nên hoạt động trên cụm
tối thiểu. Top_n child sau hợp nhất được gắn
metadata PARENT (document_id, media_id, original_name) + số trang `page` để trả cho
caller trích dẫn "trang X".

Embedding query có thể vắng (lỗi embed) → tự bỏ nhánh kNN, vẫn chạy BM25 (fail-safe).
"""

from __future__ import annotations

import logging
from typing import Any

from modules.base.clients.opensearch_client import BaseOpenSearchClient

logger = logging.getLogger(__name__)


class Retriever(BaseOpenSearchClient):
    """Chạy hybrid search + RRF và trả ứng viên chunk kèm metadata parent."""

    # --- Search helpers ----------------------------------------------------
    def _search_hits(self, body: dict[str, Any], size: int) -> list[dict[str, Any]]:
        """Chạy 1 search, trả list hit thô (rỗng nếu lỗi/không có index)."""
        try:
            response = self._client.search(
                index=self.index,
                body={"size": size, "_source": ["chunk_text", "page"], **body},
            )
            return response.get("hits", {}).get("hits", [])
        except Exception:
            logger.exception("[retriever] lỗi search (bỏ qua nhánh này)")
            return []

    def _bm25_hits(self, query: str, size: int) -> list[dict[str, Any]]:
        """BM25 trên child: chỉ child có `chunk_text` nên match tự loại parent."""
        return self._search_hits({"query": {"match": {"chunk_text": query}}}, size)

    def _knn_hits(self, vector: list[float], size: int) -> list[dict[str, Any]]:
        """kNN trên child `chunk_vector` (lucene HNSW, space cosinesimil)."""
        body = {"query": {"knn": {"chunk_vector": {"vector": vector, "k": size}}}}
        return self._search_hits(body, size)

    @staticmethod
    def _parent_id(hit: dict[str, Any]) -> str:
        """Parent id của 1 child hit: `_routing` nếu có, else tách từ `_id` "pid:i"."""
        routing = hit.get("_routing")
        if routing:
            return str(routing)
        return str(hit.get("_id", "")).rsplit(":", 1)[0]

    # --- RRF ----------------------------------------------------------------
    def _fuse(
        self,
        ranked_lists: list[list[dict[str, Any]]],
        rrf_k: int,
        top_n: int,
    ) -> list[dict[str, Any]]:
        """Hợp nhất nhiều ranked list child hit bằng RRF, trả top_n đã xếp hạng.

        Điểm RRF của 1 child = Σ 1/(rrf_k + rank) trên mọi list nó xuất hiện (rank từ 1).
        Giữ lại chunk_text/page/parent_id của lần gặp đầu để build kết quả.
        """
        scores: dict[str, float] = {}
        meta: dict[str, dict[str, Any]] = {}
        for hits in ranked_lists:
            for rank, hit in enumerate(hits, start=1):
                child_id = str(hit.get("_id"))
                scores[child_id] = scores.get(child_id, 0.0) + 1.0 / (rrf_k + rank)
                if child_id not in meta:
                    source: dict[str, Any] = hit.get("_source", {})
                    meta[child_id] = {
                        "chunk_text": source.get("chunk_text", ""),
                        "page": source.get("page"),
                        "parent_id": self._parent_id(hit),
                    }
        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
        return [
            {**meta[child_id], "child_id": child_id, "hybrid_score": score}
            for child_id, score in ordered
        ]

    # --- Parent metadata ----------------------------------------------------
    def _attach_parents(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """mget metadata parent (document_id/media_id/original_name) cho từng ứng viên.

        Lỗi mget → parent rỗng (vẫn trả chunk_text + page; không làm hỏng truy hồi).
        """
        parent_ids = list({c["parent_id"] for c in candidates if c.get("parent_id")})
        parents: dict[str, dict[str, Any]] = {}
        if parent_ids:
            try:
                docs = self._client.mget(
                    index=self.index,
                    body={
                        "docs": [
                            {
                                "_id": pid,
                                "routing": pid,
                                "_source": ["document_id", "media_id", "original_name"],
                            }
                            for pid in parent_ids
                        ]
                    },
                )
                for doc in docs.get("docs", []):
                    if doc.get("found"):
                        parents[str(doc["_id"])] = doc.get("_source", {})
            except Exception:
                logger.exception("[retriever] lỗi mget parent (trả metadata rỗng)")

        enriched: list[dict[str, Any]] = []
        for candidate in candidates:
            parent = parents.get(candidate.get("parent_id", ""), {})
            enriched.append(
                {
                    "chunk_text": candidate["chunk_text"],
                    "page": candidate.get("page"),
                    "document_id": parent.get("document_id"),
                    "media_id": parent.get("media_id"),
                    "original_name": parent.get("original_name"),
                    "score": candidate["hybrid_score"],
                }
            )
        return enriched

    # --- Public -------------------------------------------------------------
    def retrieve(
        self,
        query: str,
        query_vector: list[float] | None,
        top_n: int,
        rrf_k: int,
    ) -> list[dict[str, Any]]:
        """Hybrid search BM25 + kNN cho 1 query → RRF → top_n + metadata parent.

        BM25 trên `chunk_text` (luôn) + kNN trên `chunk_vector` (nếu có vector;
        vector None → chỉ BM25, fail-safe). Trả về list dict
        {chunk_text, page, document_id, media_id, original_name, score}.
        """
        ranked_lists: list[list[dict[str, Any]]] = []
        if query:
            ranked_lists.append(self._bm25_hits(query, top_n))
        if query_vector:
            ranked_lists.append(self._knn_hits(query_vector, top_n))

        fused = self._fuse(ranked_lists, rrf_k, top_n)
        if not fused:
            logger.info("[retriever] hybrid search không có kết quả")
            return []
        return self._attach_parents(fused)
