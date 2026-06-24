"""Tên event realtime module chatbot đẩy xuống FE qua node-aio (Redis → WebSocket).

Dùng làm `type` trong envelope `{type, data}` khi publish. Đặt tên dạng namespace
`chatbot.<đối tượng>.<hành động>` để FE phân loại được nguồn event.
"""

from __future__ import annotations

from django.db import models


class RealtimeEvent(models.TextChoices):
    """Các loại event realtime của chatbot.

    DOCUMENT_PROGRESS  — tiến độ ingest 1 tài liệu (status/indexed_percent) đổi.
    CONVERSATION_TITLE — tiêu đề hội thoại vừa được sinh nền xong (đẩy riêng 1 user).
    """

    DOCUMENT_PROGRESS = "chatbot.document.progress"
    CONVERSATION_TITLE = "chatbot.conversation.title"
