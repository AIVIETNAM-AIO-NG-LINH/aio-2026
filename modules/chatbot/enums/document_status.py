"""Trạng thái tài liệu chatbot — clone của `Modules\\Chatbot\\Enums\\V1\\DocumentStatus`."""

from __future__ import annotations

from django.db import models


class DocumentStatus(models.TextChoices):
    """Trạng thái vòng đời tài liệu chatbot, lưu ở `chatbot_documents.status`.

    PENDING — đã upload, CHỜ xử lý (parse/chunk/embed). Reserve cho pipeline học.
    READY   — file đã lưu thành công, sẵn sàng (mặc định sau upload).
    FAILED  — xử lý thất bại (reserve cho pipeline tương lai).
    """

    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"
