"""Vai trò của 1 tin nhắn trong hội thoại, lưu ở `chatbot_messages.role`."""

from __future__ import annotations

from django.db import models


class MessageRole(models.TextChoices):
    """Ai là người phát ra tin nhắn.

    USER      — câu hỏi do người dùng gửi.
    ASSISTANT — câu trả lời do chatbot (Gemini) sinh ra.
    """

    USER = "user"
    ASSISTANT = "assistant"
