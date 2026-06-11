"""Index chunk + vector vào OpenSearch theo mô hình parent-child join.

Một tài liệu = 1 parent doc (metadata) + N child doc (chunk_text + chunk_vector),
nối nhau qua join field `doc_join`. Truy hồi kNN chạy trên child; parent giữ
metadata để lọc/hiển thị. Ghi lại idempotent: xoá sạch parent+child cũ của
document_id rồi index lại.
"""

from __future__ import annotations

import logging
from typing import Any

from opensearchpy import helpers

from modules.base.clients.opensearch_client import BaseOpenSearchClient

logger = logging.getLogger(__name__)

# Tên join field + 2 quan hệ parent/child.
JOIN_FIELD = "doc_join"
PARENT_RELATION = "document"
CHILD_RELATION = "chunk"


class OpenSearchIndexer(BaseOpenSearchClient):
    """Tạo index (nếu chưa có) và ghi parent-child cho một tài liệu."""

    # --- Mapping / index ---------------------------------------------------
    def _index_body(self) -> dict[str, Any]:
        """Settings + mapping cho index: bật kNN, join field, knn_vector HNSW/lucene."""
        return {
            "settings": {"index": {"knn": True}},
            "mappings": {
                "properties": {
                    JOIN_FIELD: {
                        "type": "join",
                        "relations": {PARENT_RELATION: CHILD_RELATION},
                    },
                    # Parent fields (metadata tài liệu).
                    "document_id": {"type": "long"},
                    "media_id": {"type": "long"},
                    "original_name": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
                    },
                    "mime_type": {"type": "keyword"},
                    "file_type": {"type": "keyword"},
                    # Tổng số trang của tài liệu (Phase 4, trên parent).
                    "page_count": {"type": "integer"},
                    # Child fields (chunk + vector).
                    "chunk_text": {"type": "text"},
                    # Số trang nguồn của chunk (Phase 4, từ 1) — phục vụ trích dẫn.
                    "page": {"type": "integer"},
                    "chunk_vector": {
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

    def ensure_index(self) -> None:
        """Tạo index với mapping nếu chưa tồn tại (no-op nếu đã có, an toàn khi đua)."""
        self._create_index_if_missing(self.index, self._index_body())

    # --- Ghi document ------------------------------------------------------
    def index_document(
        self,
        parent_meta: dict[str, Any],
        children: list[tuple[str, list[float], int | None]],
    ) -> int:
        """Ghi 1 tài liệu (idempotent): xoá bản cũ → index parent → bulk children.

        `parent_meta` chứa document_id/media_id/original_name/mime_type/file_type
        (+ page_count nếu có). Mỗi child là (chunk_text, chunk_vector, page) với
        `page` là số trang nguồn (từ 1, có thể None nếu không xác định được).
        Trả về số child đã index.
        """
        self.ensure_index()

        document_id = parent_meta["document_id"]
        parent_id = str(document_id)
        index = self.index

        self._delete_existing(parent_id, document_id)

        # Index parent: metadata + join name = "document".
        self._client.index(
            index=index,
            id=parent_id,
            routing=parent_id,
            body={**parent_meta, JOIN_FIELD: {"name": PARENT_RELATION}},
        )

        # Bulk index children: routing = parent id để cùng shard với parent.
        actions = [
            {
                "_op_type": "index",
                "_index": index,
                "_id": f"{parent_id}:{i}",
                "routing": parent_id,
                "_source": {
                    "chunk_text": chunk_text,
                    "chunk_vector": chunk_vector,
                    "page": page,
                    JOIN_FIELD: {"name": CHILD_RELATION, "parent": parent_id},
                },
            }
            for i, (chunk_text, chunk_vector, page) in enumerate(children)
        ]
        if actions:
            helpers.bulk(self._client, actions)

        self._client.indices.refresh(index=index)
        logger.info(
            "[opensearch] document_id=%s đã index %d child", document_id, len(actions)
        )
        return len(actions)

    def _delete_existing(self, parent_id: str, document_id: int) -> None:
        """Xoá parent + toàn bộ child cũ của document_id (đảm bảo ghi lại sạch).

        Khớp cả parent (term document_id) lẫn child (parent_id trên join field),
        chạy trong shard routing của parent để không đụng tài liệu khác.
        """
        query = {
            "query": {
                "bool": {
                    "should": [
                        {"term": {"document_id": document_id}},
                        {"parent_id": {"type": CHILD_RELATION, "id": parent_id}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        }
        self._client.delete_by_query(
            index=self.index,
            body=query,
            routing=parent_id,
            refresh=True,
            conflicts="proceed",
            ignore=[404],
        )
