"""Request validate cho endpoint chat.

Body: `{ "question": <str>, "conversation_id"?: <int>, "media_ids"?: [<int>] }`.
`user_id` KHÔNG nằm trong body — view lấy từ header `X-Auth-User-Id` (nginx set
sau khi verify token ở api-aio) rồi nhồi vào DTO. `conversation_id` vắng → tạo
hội thoại mới. `media_ids` (tuỳ chọn) là danh sách id bản ghi `media` user upload
kèm lượt này — sẽ được đẩy lên Gemini để hỏi đáp trong PHẠM VI hội thoại đó.
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
    media_ids: tuple[int, ...]


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
    # Danh sách id media user đính kèm (tuỳ chọn). Chỉ validate SHAPE (list số nguyên
    # dương); media có TỒN TẠI / đúng loại hay không xử lý fail-safe ở tầng đính kèm
    # (bỏ qua file lỗi, không 422 cả lượt). `allow_empty` để FE gửi list rỗng vô hại.
    media_ids = serializers.ListField(
        child=serializers.IntegerField(
            min_value=1,
            error_messages={
                "invalid": translate_lazy(
                    "media_id phải là số nguyên", ChatbotCatalog.MEDIA_ID_INVALID
                ),
                "min_value": translate_lazy(
                    "media_id không hợp lệ", ChatbotCatalog.MEDIA_ID_INVALID
                ),
            },
        ),
        required=False,
        allow_empty=True,
        error_messages={
            "not_a_list": translate_lazy(
                "media_ids phải là danh sách", ChatbotCatalog.MEDIA_IDS_INVALID
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
            media_ids=tuple(data.get("media_ids") or ()),
        )
