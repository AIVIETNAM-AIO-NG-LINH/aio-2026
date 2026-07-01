"""Base class cho mọi class thao tác OpenSearch — tự quản config + connection.

Khác `S3Client`/`GeminiClient` (client độc lập, gọi method trực tiếp), OpenSearch
có nhiều class domain (indexer, retriever, LTM…) mỗi class một bộ mapping/query
riêng — nên đây là BASE CLASS để kế thừa (mirror `BaseService`/`BaseRepository`):

    from modules.base.app.clients.opensearch_client import BaseOpenSearchClient

    class MyIndexer(BaseOpenSearchClient):
        def do_something(self):
            self._client.indices.exists(index=self.index)

Base tự đọc env `OPENSEARCH_*` và dựng `opensearchpy.OpenSearch`; subclass dùng
`self._client` + các attribute public (`index`, `summary_index`, `vector_dims`),
KHÔNG tự parse env hay dựng connection nữa.
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    from opensearchpy import OpenSearch

logger = logging.getLogger(__name__)

T = TypeVar("T")

#: Số lần thử tối đa cho thao tác ghi khi gặp lỗi transient (mạng/429/5xx).
_TRANSIENT_MAX_ATTEMPTS = 3
#: Backoff khởi điểm giữa hai lần thử (giây), nhân đôi sau mỗi lần.
_TRANSIENT_BACKOFF_SECONDS = 1.0
#: Status HTTP coi là transient (quá tải/tạm thời phía server) — retry được.
_TRANSIENT_STATUSES = {429, 502, 503, 504}


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

    def _retry_transient(self, op: str, action: Callable[[], T]) -> T:
        """Chạy `action`, retry với backoff khi gặp lỗi transient (connection/429/5xx).

        Chỉ retry lỗi thử-lại-được (ConnectionError/Timeout, hoặc TransportError
        status 429/502/503/504); lỗi khác (mapping sai, dữ liệu hỏng…) raise ngay
        vì retry không cứu được. Caller phải đảm bảo `action` idempotent.
        LƯU Ý: nếu Phase sau bật Celery retry cho task ingest thì gỡ retry này
        để tránh retry kép (chỉ giữ 1 trong 2 tầng retry).
        """
        from opensearchpy.exceptions import (  # lazy như _build_client
            ConnectionError as OpenSearchConnectionError,
            TransportError,
        )

        delay = _TRANSIENT_BACKOFF_SECONDS
        for attempt in range(1, _TRANSIENT_MAX_ATTEMPTS):
            try:
                return action()
            except TransportError as exc:
                transient = (
                    isinstance(exc, OpenSearchConnectionError)
                    or exc.status_code in _TRANSIENT_STATUSES
                )
                if not transient:
                    raise
                logger.warning(
                    "[opensearch] %s lỗi transient (%s) — thử lại %d/%d sau %.0fs",
                    op, exc, attempt, _TRANSIENT_MAX_ATTEMPTS - 1, delay,
                )
                time.sleep(delay)
                delay *= 2
        # Lần thử cuối: lỗi gì cũng raise lên caller xử lý trung thực.
        return action()

    def _create_index_if_missing(self, index: str, body: dict[str, Any]) -> None:
        """Tạo index với mapping nếu chưa tồn tại (đã có → chỉ so lại vector dims).

        Check-rồi-tạo không atomic: 2 worker cùng tạo lần đầu thì worker thua
        cuộc ăn `resource_already_exists` — nuốt lỗi đó (index đã có đúng là
        điều cần), mọi lỗi khác vẫn raise để caller xử lý trung thực.
        """
        from opensearchpy.exceptions import RequestError  # lazy như _build_client

        if self._client.indices.exists(index=index):
            self._verify_vector_dims(index, body)
            return
        logger.info("[opensearch] tạo index '%s'", index)
        try:
            self._client.indices.create(index=index, body=body)
        except RequestError as exc:
            if exc.error != "resource_already_exists_exception":
                raise
            logger.info("[opensearch] index '%s' đã được worker khác tạo", index)

    @staticmethod
    def _knn_dims(mappings: dict[str, Any]) -> dict[str, int]:
        """Lấy {tên field: dimension} của mọi field `knn_vector` trong `mappings`."""
        properties = (mappings or {}).get("properties") or {}
        return {
            name: int(prop["dimension"])
            for name, prop in properties.items()
            if isinstance(prop, dict)
            and prop.get("type") == "knn_vector"
            and "dimension" in prop
        }

    def _verify_vector_dims(self, index: str, body: dict[str, Any]) -> None:
        """So `dimension` các field knn_vector của index HIỆN CÓ với mapping code mong đợi.

        OpenSearch không cho đổi dimension tại chỗ: đổi env OPENSEARCH_VECTOR_DIMS
        sau khi index đã tạo sẽ làm vector mới sai chiều — fail rối ở bulk lúc
        ingest, còn kNN lúc retrieve thì trả rỗng âm thầm. Phát hiện lệch → raise
        NGAY với thông điệp rõ thay vì để nổ xa nơi gây lỗi. Riêng lỗi ĐỌC mapping
        (mạng/transient) chỉ log warning rồi bỏ qua — check này không được phép tự
        trở thành lý do làm hỏng ingest.
        """
        expected: dict[str, int] = self._knn_dims(body.get("mappings") or {})
        if not expected:
            return
        try:
            # get_mapping trả {tên index thật: {"mappings": {...}}} (opensearchpy không type).
            response: dict[str, dict[str, Any]] = self._client.indices.get_mapping(index=index)
            existing: dict[str, int] = self._knn_dims(next(iter(response.values()))["mappings"])
        except Exception:
            logger.warning(
                "[opensearch] không đọc được mapping của '%s' để so vector dims, bỏ qua check",
                index,
            )
            return
        for field, dims in expected.items():
            current = existing.get(field)
            if current is not None and current != dims:
                raise RuntimeError(
                    f"Index '{index}' có field '{field}' đang {current} chiều nhưng cấu hình "
                    f"hiện tại yêu cầu {dims} (env OPENSEARCH_VECTOR_DIMS). OpenSearch không "
                    f"đổi dimension tại chỗ được — hoặc trả env về {current}, hoặc xoá/reindex "
                    f"'{index}' rồi re-ingest toàn bộ tài liệu."
                )
