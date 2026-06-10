"""Nghiệp vụ enqueue ingest tài liệu chatbot — tách khỏi view/validate.

Service chỉ nhận DTO. Kiểm tra bản ghi tồn tại (đọc DB), nếu OK thì đẩy task
Celery xử lý nền và trả `202 Accepted` NGAY (không xử lý đồng bộ trong request).
"""

from __future__ import annotations

from rest_framework import status as http_status
from rest_framework.response import Response

from modules.base.services import BaseService

from ..models import ChatbotDocument
from ..requests import IngestDocumentDTO
from ..tasks import ingest_document


class IngestDocumentService(BaseService):
    """Validate-tồn-tại + enqueue pipeline ingest (Phase 0: pipeline còn STUB)."""

    def ingest(self, dto: IngestDocumentDTO) -> Response:
        """document_id không tồn tại → 404; hợp lệ → enqueue + 202 Accepted."""
        if not ChatbotDocument.objects.filter(pk=dto.document_id).exists():
            self.exception(
                "chatbot_documents không tồn tại",
                http_status.HTTP_404_NOT_FOUND,
            )

        # Đẩy vào worker nền; KHÔNG chờ pipeline chạy xong.
        ingest_document.delay(dto.document_id)

        return self.response_success(
            {"document_id": dto.document_id, "queued": True},
            status=http_status.HTTP_202_ACCEPTED,
        )
