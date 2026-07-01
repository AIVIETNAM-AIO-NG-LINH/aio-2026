"""Request validate cho endpoint đổi tên hội thoại.

Body: `{ "title": <str> }`. `conversation_id` đến từ URL, `user_id` từ header —
KHÔNG nằm trong body. Chỉ validate SHAPE của `title` (bắt buộc, không rỗng, tối đa
255 ký tự khớp `ChatConversation.title`); quyền sở hữu hội thoại kiểm ở Service.
"""

from __future__ import annotations

from dataclasses import dataclass

from rest_framework import serializers

from modules.base.app.requests import BaseFormRequest
from modules.base.app.supports import translate_lazy

from ....catalogs import ChatbotCatalog


@dataclass(frozen=True)
class UpdateConversationDTO:
    """DTO bất biến cho 1 lượt đổi tên. `user_id`/`conversation_id` đến từ ngoài body."""

    title: str


class UpdateConversationRequest(BaseFormRequest):
    """Validate payload `{ title }`."""

    # error_messages bọc `translate_lazy` (đánh giá lúc import, resolve per-request).
    title = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        max_length=255,
        error_messages={
            "required": translate_lazy(
                "title là bắt buộc", ChatbotCatalog.TITLE_REQUIRED
            ),
            "blank": translate_lazy(
                "title không được rỗng", ChatbotCatalog.TITLE_BLANK
            ),
            "max_length": translate_lazy(
                "title tối đa 255 ký tự", ChatbotCatalog.TITLE_MAX
            ),
        },
    )

    def to_dto(self) -> UpdateConversationDTO:
        """`validated_data` → DTO. Gọi SAU `is_valid()`."""
        return UpdateConversationDTO(title=self.validated_data["title"])
