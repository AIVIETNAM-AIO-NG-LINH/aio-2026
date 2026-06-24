"""Nghiệp vụ enqueue purge tài liệu chatbot — tách khỏi view/validate.

Service chỉ nhận DTO (đã qua validate ở `PurgeDocumentRequest`): đẩy task Celery
dọn OpenSearch/KG ở nền và trả `202 Accepted` NGAY (không xử lý đồng bộ trong
request — purge nhanh nhưng giữ đúng mô hình "báo rồi quên" như ingest).
"""

from __future__ import annotations

from rest_framework import status as http_status
from rest_framework.response import Response

from modules.base.services import BaseService

from ...contracts.services.v1 import PurgeDocumentServiceInterface
from ...http.requests.v1 import PurgeDocumentDTO
from ...tasks import purge_document


class PurgeDocumentService(BaseService, PurgeDocumentServiceInterface):
    """Enqueue task dọn dấu vết OpenSearch/KG cho document_id đã gỡ."""

    def purge(self, dto: PurgeDocumentDTO) -> Response:
        """Enqueue + 202 Accepted (không check tồn tại — bản ghi đã soft-delete)."""
        # Đẩy vào worker nền; KHÔNG chờ dọn xong.
        purge_document.delay(dto.document_id)

        return self.response_success(
            {"document_id": dto.document_id, "queued": True},
            status=http_status.HTTP_202_ACCEPTED,
        )
