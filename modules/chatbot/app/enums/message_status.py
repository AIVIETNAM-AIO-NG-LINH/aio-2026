"""Trạng thái xử lý của 1 tin nhắn, lưu ở `chatbot_messages.status`."""

from __future__ import annotations

from django.db import models


class MessageStatus(models.TextChoices):
    """Trạng thái sinh câu trả lời (chủ yếu áp dụng cho message ASSISTANT).

    PROCESSING — đang stream / chờ Gemini sinh xong (placeholder vừa tạo).
    SUCCESS    — đã sinh xong câu trả lời (mặc định cho message người dùng).
    ERROR      — sinh thất bại (lỗi LLM / timeout); content có thể rỗng/dở.
    """

    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
