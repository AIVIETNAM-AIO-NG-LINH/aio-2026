"""Model `ChatbotDocument` — clone của `Modules\\Chatbot\\Models\\ChatbotDocument`.

Liên kết 1 tài liệu (bản ghi `Media`) vào chatbot để học (knowledge base). Bảng CHỈ
lưu `media_id` + `status`; file thật + metadata (file_name/mime/size/url) sống ở bảng
`media` (module Media). Module này chỉ đọc — không xử lý upload, không tạo bảng.
"""

from __future__ import annotations

from django.db import models

from modules.base.models import SoftDeleteModel
from modules.media.models import Media

from modules.chatbot.enums import DocumentStatus


class ChatbotDocument(SoftDeleteModel):
    """Tài liệu thuộc kho tri thức chatbot (read-only ở service này)."""

    TABLE = "chatbot_documents"

    COL_MEDIA_ID = "media_id"
    COL_STATUS = "status"

    media = models.ForeignKey(
        Media,
        on_delete=models.DO_NOTHING,
        db_column="media_id",
        related_name="chatbot_documents",
    )
    # `media_id` do ForeignKey tự sinh — khai báo kiểu để type checker không coi là Any
    # (annotation rỗng, không gán value nên Django KHÔNG hiểu nhầm thành field).
    media_id: int

    status = models.CharField(max_length=20, choices=DocumentStatus.choices)

    class Meta(SoftDeleteModel.Meta):
        db_table = "chatbot_documents"
        # Bảng do service khác sở hữu/ghi — Django chỉ đọc, KHÔNG tạo/migrate.
        managed = False

    def __str__(self) -> str:
        return f"ChatbotDocument#{self.pk} (media_id={self.media_id})"
