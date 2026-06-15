"""Index chunk + vector vào OpenSearch theo mô hình parent-child join.

Một tài liệu = 1 parent doc (metadata) + N child doc (chunk_text + chunk_vector),
nối nhau qua join field `doc_join`. Truy hồi kNN chạy trên child; parent giữ
metadata để lọc/hiển thị.

Re-ingest KHÔNG có khoảng trống: mỗi lần ingest dùng một version mới trong `_id`
(parent = "{document_id}:{version}", child = "{parent_id}:{i}") — ghi bản mới
trước, đợi bản mới search thấy được rồi mới xoá mọi bản cũ. Tài liệu không bao
giờ biến mất khỏi search giữa chừng; đổi lại có cửa sổ ngắn cả 2 bản cùng hiện
(worker chết giữa chừng thì bản cũ vẫn nguyên, lần ingest thành công kế tiếp
dọn sạch bản thừa).
"""

from __future__ import annotations

import logging
import uuid
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
        """Ghi 1 tài liệu (idempotent): index parent + bulk children MỚI → xoá bản cũ.

        `parent_meta` chứa document_id/media_id/original_name/mime_type/file_type
        (+ page_count nếu có). Mỗi child là (chunk_text, chunk_vector, page) với
        `page` là số trang nguồn (từ 1, có thể None nếu không xác định được).
        Trả về số child đã index.

        Ghi-mới-trước-xoá-sau để re-ingest không có khoảng trống trên search
        (xem docstring module). Routing của mọi doc = parent_id (retriever lấy
        parent id từ `_routing` của child hit để mget metadata).
        """
        self.ensure_index()

        document_id = parent_meta["document_id"]
        # Version mới mỗi lần ingest → _id không đụng bản cũ, ghi song song an toàn.
        parent_id = f"{document_id}:{uuid.uuid4().hex[:8]}"
        index = self.index

        # Index parent: metadata + join name = "document".
        self._retry_transient(
            "index parent",
            lambda: self._client.index(
                index=index,
                id=parent_id,
                routing=parent_id,
                body={**parent_meta, JOIN_FIELD: {"name": PARENT_RELATION}},
            ),
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
            # wait_for: đợi bản mới search thấy được TRƯỚC khi xoá bản cũ bên
            # dưới (không có khoảng trống) và trước khi tài liệu được đánh READY.
            # max_retries: helpers.bulk tự retry các ITEM bị 429 (queue đầy);
            # _retry_transient lo lỗi cấp request (mạng/timeout) — hai tầng
            # khác nhau, không retry kép trên cùng một lỗi.
            self._retry_transient(
                "bulk index children",
                lambda: helpers.bulk(
                    self._client, actions, refresh="wait_for", max_retries=3
                ),
            )

        self._delete_stale(document_id, parent_id)

        logger.info(
            "[opensearch] document_id=%s đã index %d child", document_id, len(actions)
        )
        return len(actions)

    def _delete_stale(self, document_id: int, keep_parent_id: str) -> None:
        """Xoá mọi parent + child của document_id TRỪ version vừa ghi.

        2 bước, CHILD TRƯỚC PARENT: child cũ chỉ tìm được qua has_parent theo
        document_id (cover mọi version, kể cả định dạng id cũ không có version);
        xoá parent trước mà chết giữa chừng thì child thành mồ côi không query
        lại được nữa. Chết giữa 2 bước chỉ để lại parent cũ (không có child nên
        vô hình với retrieval), lần ingest sau dọn nốt.

        Không truyền routing: version khác nhau nằm shard khác nhau (routing
        theo parent_id). refresh=True ở bước child để lúc trả về, search chỉ
        còn đúng 1 bản.
        """
        # Bước 1: child của mọi parent thuộc document_id, trừ con của parent mới.
        children_query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "has_parent": {
                                "parent_type": PARENT_RELATION,
                                "query": {"term": {"document_id": document_id}},
                            }
                        }
                    ],
                    "must_not": [
                        {"parent_id": {"type": CHILD_RELATION, "id": keep_parent_id}}
                    ],
                }
            }
        }
        # Bước 2: parent mang document_id, trừ parent mới (chỉ parent có field
        # document_id nên không cần lọc thêm theo join).
        parents_query = {
            "query": {
                "bool": {
                    "must": [{"term": {"document_id": document_id}}],
                    "must_not": [{"ids": {"values": [keep_parent_id]}}],
                }
            }
        }
        for op, query, refresh in (
            ("delete_by_query child cũ", children_query, True),
            ("delete_by_query parent cũ", parents_query, False),
        ):
            self._retry_transient(
                op,
                lambda q=query, r=refresh: self._client.delete_by_query(
                    index=self.index,
                    body=q,
                    refresh=r,
                    conflicts="proceed",
                    ignore=[404],
                ),
            )
