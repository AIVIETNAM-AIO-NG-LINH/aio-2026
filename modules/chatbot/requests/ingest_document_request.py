"""Request validate cho endpoint nội bộ ingest tài liệu chatbot.

Body chỉ có 1 field `document_id` (id của bản ghi `chatbot_documents` mà api-aio
vừa tạo). Validate cả dạng dữ liệu (int > 0) lẫn bản ghi có TỒN TẠI hay không
(chưa xóa mềm) — fail đều trả 422 shape V1; Service chỉ còn enqueue.
"""

from __future__ import annotations

from dataclasses import dataclass

from rest_framework import serializers

from modules.base.requests import BaseFormRequest

from ..repositories import ChatbotDocumentRepository


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

    def validate_document_id(self, value: int) -> int:
        """Bản ghi phải tồn tại (repository đã lọc xóa mềm)."""
        if not ChatbotDocumentRepository().exists(value):
            raise serializers.ValidationError("document_id không tồn tại")
        return value

    def to_dto(self) -> IngestDocumentDTO:
        """`validated_data` → DTO. Gọi SAU `is_valid()`."""
        return IngestDocumentDTO(document_id=self.validated_data["document_id"])
