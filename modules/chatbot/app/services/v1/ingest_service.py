"""Nghiệp vụ enqueue ingest tài liệu chatbot — tách khỏi view/validate.

Service chỉ nhận DTO (đã qua validate ở `IngestDocumentRequest`, gồm cả check
bản ghi tồn tại): đẩy task Celery xử lý nền và trả `202 Accepted` NGAY
(không xử lý đồng bộ trong request).
"""

from __future__ import annotations

from rest_framework import status as http_status
from rest_framework.response import Response

from modules.base.app.services import BaseService

from ...contracts.services.v1 import IngestDocumentServiceInterface
from ...http.requests.v1 import IngestDocumentDTO
from ...tasks import ingest_document


class IngestDocumentService(BaseService, IngestDocumentServiceInterface):
    """Enqueue pipeline ingest cho document_id đã validate."""

    def ingest(self, dto: IngestDocumentDTO) -> Response:
        """Enqueue + 202 Accepted (tồn tại đã được check ở request → 422)."""
        # Đẩy vào worker nền; KHÔNG chờ pipeline chạy xong.
        ingest_document.delay(dto.document_id)

        return self.response_success(
            {"document_id": dto.document_id, "queued": True},
            status=http_status.HTTP_202_ACCEPTED,
        )
