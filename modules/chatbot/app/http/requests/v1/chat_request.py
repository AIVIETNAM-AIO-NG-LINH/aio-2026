"""Request validate cho endpoint chat.

Body: `{ "question": <str>, "conversation_id"?: <int> }`.
`user_id` KHÔNG nằm trong body — view lấy từ header `X-Auth-User-Id` (nginx set
sau khi verify token ở api-aio) rồi nhồi vào DTO. `conversation_id` vắng → tạo
hội thoại mới.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from rest_framework import serializers

from modules.base.requests import BaseFormRequest
from modules.base.supports import translate_lazy

from ....catalogs import ChatbotCatalog


@dataclass(frozen=True)
class ChatDTO:
    """DTO bất biến cho 1 lượt chat. `user_id` đến từ header, không từ body."""

    user_id: int
    question: str
    conversation_id: Optional[int]


class ChatRequest(BaseFormRequest):
    """Validate payload `{ question, conversation_id? }`."""

    # error_messages bọc `translate_lazy` (KHÔNG phải translate): class-attribute
    # evaluate lúc import, lazy mới resolve ngôn ngữ per-request lúc render lỗi.
    question = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            "required": translate_lazy(
                "question là bắt buộc", ChatbotCatalog.QUESTION_REQUIRED
            ),
            "blank": translate_lazy(
                "question không được rỗng", ChatbotCatalog.QUESTION_BLANK
            ),
        },
    )
    conversation_id = serializers.IntegerField(
        required=False,
        min_value=1,
        error_messages={
            "invalid": translate_lazy(
                "conversation_id phải là số nguyên", ChatbotCatalog.CONVERSATION_ID_INVALID
            ),
            "min_value": translate_lazy(
                "conversation_id không hợp lệ", ChatbotCatalog.CONVERSATION_ID_MIN
            ),
        },
    )

    def to_dto(self, user_id: int) -> ChatDTO:
        """`validated_data` + `user_id` (từ header) → DTO. Gọi SAU `is_valid()`."""
        data = self.validated_data
        return ChatDTO(
            user_id=user_id,
            question=data["question"],
            conversation_id=data.get("conversation_id"),
        )
