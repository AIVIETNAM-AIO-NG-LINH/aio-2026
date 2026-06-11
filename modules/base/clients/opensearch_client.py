"""Base class cho mọi class thao tác OpenSearch — tự quản config + connection.

Khác `S3Client`/`GeminiClient` (client độc lập, gọi method trực tiếp), OpenSearch
có nhiều class domain (indexer, retriever, LTM…) mỗi class một bộ mapping/query
riêng — nên đây là BASE CLASS để kế thừa (mirror `BaseService`/`BaseRepository`):

    from modules.base.clients.opensearch_client import BaseOpenSearchClient

    class MyIndexer(BaseOpenSearchClient):
        def do_something(self):
            self._client.indices.exists(index=self.index)

Base tự đọc env `OPENSEARCH_*` và dựng `opensearchpy.OpenSearch`; subclass dùng
`self._client` + các attribute public (`index`, `summary_index`, `vector_dims`),
KHÔNG tự parse env hay dựng connection nữa.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opensearchpy import OpenSearch


def _env(name: str, default: str = "") -> str:
    """Đọc env, strip khoảng trắng; rỗng/không set → default."""
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _env_int(name: str, default: int) -> int:
    """Parse env dạng int; lỗi/không set → default."""
    raw = _env(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


class BaseOpenSearchClient:
    """Base kết nối OpenSearch qua env — subclass thao tác qua `self._client`."""

    def __init__(self) -> None:
        self._url = _env("OPENSEARCH_URL", default="http://opensearch:9200")
        self._user = _env("OPENSEARCH_USER")
        self._password = _env("OPENSEARCH_PASSWORD")
        self._verify_certs = _env("OPENSEARCH_VERIFY_CERTS").lower() in {"1", "true", "yes", "on"}
        #: Index chính parent-child của RAG.
        self.index = _env("OPENSEARCH_INDEX", default="rag-index")
        #: Index riêng 1-doc-mỗi-tài-liệu cho tóm tắt + vector (Phase 2).
        self.summary_index = _env("OPENSEARCH_SUMMARY_INDEX", default="document-summary-index")
        #: Số chiều knn_vector của các index (phải khớp embedding).
        self.vector_dims = _env_int("OPENSEARCH_VECTOR_DIMS", default=768)
        self._client = self._build_client()

    def _build_client(self) -> "OpenSearch":
        """Khởi tạo OpenSearch client (URL, basic auth nếu có user, verify TLS)."""
        from opensearchpy import OpenSearch  # lazy import: image slim có thể không cài

        http_auth = (self._user, self._password) if self._user else None
        return OpenSearch(
            hosts=[self._url],
            http_auth=http_auth,
            verify_certs=self._verify_certs,
            ssl_show_warn=self._verify_certs,
        )
