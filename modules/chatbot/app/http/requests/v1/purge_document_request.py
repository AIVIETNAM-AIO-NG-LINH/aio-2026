"""Request validate cho endpoint nội bộ purge tài liệu chatbot.

Body chỉ có 1 field `document_id`. KHÁC `IngestDocumentRequest`: KHÔNG check bản
ghi tồn tại — api-aio đã soft-delete bản ghi `chatbot_documents` TRƯỚC khi báo
purge, nên lúc này bản ghi đã biến mất khỏi DB (managed). Mọi index OpenSearch/KG
đều khoá theo document_id nên chỉ cần id hợp lệ (int > 0) là purge được.
"""

from __future__ import annotations

from dataclasses import dataclass

from rest_framework import serializers

from modules.base.app.requests import BaseFormRequest
from modules.base.app.supports import translate_lazy

from ....catalogs import ChatbotCatalog


@dataclass(frozen=True)
class PurgeDocumentDTO:
    """DTO bất biến truyền vào Service — Service không cần biết tới request/HTTP."""

    document_id: int


class PurgeDocumentRequest(BaseFormRequest):
    """Validate payload `{ "document_id": <int> }` (KHÔNG check tồn tại)."""

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

    def to_dto(self) -> PurgeDocumentDTO:
        """`validated_data` → DTO. Gọi SAU `is_valid()`."""
        return PurgeDocumentDTO(document_id=self.validated_data["document_id"])
