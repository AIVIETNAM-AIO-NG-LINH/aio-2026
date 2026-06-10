"""Request validate cho endpoint nội bộ ingest tài liệu chatbot.

Body chỉ có 1 field `document_id` (id của bản ghi `chatbot_documents` mà api-aio
vừa tạo). Tầng này CHỈ validate dạng dữ liệu (int > 0); việc kiểm tra bản ghi có
TỒN TẠI hay không nằm ở `IngestDocumentService` để trả 404 tách bạch khỏi 422.
"""

from __future__ import annotations

from dataclasses import dataclass

from rest_framework import serializers

from modules.base.requests import BaseFormRequest


@dataclass(frozen=True)
class IngestDocumentDTO:
    """DTO bất biến truyền vào Service — Service không cần biết tới request/HTTP."""

    document_id: int


class IngestDocumentRequest(BaseFormRequest):
    """Validate payload `{ "document_id": <int> }`."""

    document_id = serializers.IntegerField(
        min_value=1,
        error_messages={
            "required": "document_id là bắt buộc",
            "invalid": "document_id phải là số nguyên",
            "min_value": "document_id phải lớn hơn 0",
        },
    )

    def to_dto(self) -> IngestDocumentDTO:
        """`validated_data` → DTO. Gọi SAU `is_valid()`."""
        return IngestDocumentDTO(document_id=self.validated_data["document_id"])
