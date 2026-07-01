"""Request validate cho endpoint nội bộ ingest tài liệu chatbot.

Body chỉ có 1 field `document_id` (id của bản ghi `chatbot_documents` mà api-aio
vừa tạo). Validate cả dạng dữ liệu (int > 0) lẫn bản ghi có TỒN TẠI hay không
(chưa xóa mềm) — fail đều trả 422 shape V1; Service chỉ còn enqueue.
"""

from __future__ import annotations

from dataclasses import dataclass

from rest_framework import serializers

from modules.base.app.requests import BaseFormRequest
from modules.base.app.supports import translate, translate_lazy

from ....catalogs import ChatbotCatalog
from ....repositories import ChatbotDocumentRepository


@dataclass(frozen=True)
class IngestDocumentDTO:
    """DTO bất biến truyền vào Service — Service không cần biết tới request/HTTP."""

    document_id: int


class IngestDocumentRequest(BaseFormRequest):
    """Validate payload `{ "document_id": <int> }`."""

    # error_messages bọc `translate_lazy` (KHÔNG phải translate): class-attribute
    # evaluate lúc import, lazy mới resolve ngôn ngữ per-request lúc render lỗi.
    document_id = serializers.IntegerField(
        min_value=1,
        error_messages={
            "required": translate_lazy(
                "document_id là bắt buộc", ChatbotCatalog.DOCUMENT_ID_REQUIRED
            ),
            "invalid": translate_lazy(
                "document_id phải là số nguyên", ChatbotCatalog.DOCUMENT_ID_INVALID
            ),
            "min_value": translate_lazy(
                "document_id phải lớn hơn 0", ChatbotCatalog.DOCUMENT_ID_MIN
            ),
        },
    )

    def validate_document_id(self, value: int) -> int:
        """Bản ghi phải tồn tại (repository đã lọc xóa mềm)."""
        if not ChatbotDocumentRepository().exists(value):
            raise serializers.ValidationError(
                translate("document_id không tồn tại", ChatbotCatalog.DOCUMENT_NOT_FOUND)
            )
        return value

    def to_dto(self) -> IngestDocumentDTO:
        """`validated_data` → DTO. Gọi SAU `is_valid()`."""
        return IngestDocumentDTO(document_id=self.validated_data["document_id"])
