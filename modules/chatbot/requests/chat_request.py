"""Request validate cho endpoint chat.

Body: `{ "question": <str>, "conversation_id"?: <int>, "top_k"?: <int> }`.
`user_id` KHÔNG nằm trong body — view lấy từ header `X-Auth-User-Id` (nginx set
sau khi verify token ở api-aio) rồi nhồi vào DTO. `conversation_id` vắng → tạo
hội thoại mới.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from rest_framework import serializers

from modules.base.requests import BaseFormRequest


@dataclass(frozen=True)
class ChatDTO:
    """DTO bất biến cho 1 lượt chat. `user_id` đến từ header, không từ body."""

    user_id: int
    question: str
    conversation_id: Optional[int]
    top_k: Optional[int]


class ChatRequest(BaseFormRequest):
    """Validate payload `{ question, conversation_id?, top_k? }`."""

    question = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            "required": "question là bắt buộc",
            "blank": "question không được rỗng",
        },
    )
    conversation_id = serializers.IntegerField(
        required=False,
        min_value=1,
        error_messages={
            "invalid": "conversation_id phải là số nguyên",
            "min_value": "conversation_id không hợp lệ",
        },
    )
    top_k = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=50,
        error_messages={
            "invalid": "top_k phải là số nguyên",
            "min_value": "top_k phải lớn hơn 0",
            "max_value": "top_k tối đa 50",
        },
    )

    def to_dto(self, user_id: int) -> ChatDTO:
        """`validated_data` + `user_id` (từ header) → DTO. Gọi SAU `is_valid()`."""
        data = self.validated_data
        return ChatDTO(
            user_id=user_id,
            question=data["question"],
            conversation_id=data.get("conversation_id"),
            top_k=data.get("top_k"),
        )
