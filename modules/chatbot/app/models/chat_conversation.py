"""Model `ChatConversation` — 1 phiên hội thoại của người dùng với chatbot.

Bảng `chatbot_conversations` do CHÍNH service này (ai-aio) sở hữu (managed=True,
có migration) — khác `chatbot_documents` (managed=False, do api-aio sở hữu).

`user_id` là id user của hệ AIO (Laravel Passport), nhận từ nginx qua header
`X-Auth-User-Id` rồi lưu lại — KHÔNG ForeignKey sang bảng `users` (bảng đó do
api-aio quản, không nằm trong app registry của ai-aio).
"""

from __future__ import annotations

from django.db import models

from modules.base.models import SoftDeleteModel

from modules.chatbot.app.enums import ConversationStatus


class ChatConversation(SoftDeleteModel):
    """Một cuộc hội thoại (thread) — gom nhiều `ChatMessage` của cùng 1 user."""

    user_id = models.BigIntegerField(db_index=True)
    # Tự sinh từ câu hỏi + trả lời đầu tiên (Celery, nền). Null khi chưa sinh xong.
    title = models.CharField(max_length=255, null=True, blank=True, default=None)
    status = models.CharField(
        max_length=20,
        choices=ConversationStatus.choices,
        default=ConversationStatus.OPEN,
    )

    class Meta(SoftDeleteModel.Meta):
        db_table = "chatbot_conversations"
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"ChatConversation#{self.pk} (user_id={self.user_id})"
