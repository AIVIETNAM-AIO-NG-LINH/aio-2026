"""Trạng thái phiên hội thoại chatbot, lưu ở `chatbot_conversations.status`."""

from __future__ import annotations

from django.db import models


class ConversationStatus(models.TextChoices):
    """Vòng đời 1 cuộc hội thoại.

    OPEN   — đang mở, còn nhận thêm tin nhắn (mặc định khi tạo).
    CLOSED — đã đóng (lưu trữ); không nhận thêm message mới.
    """

    OPEN = "OPEN"
    CLOSED = "CLOSED"
