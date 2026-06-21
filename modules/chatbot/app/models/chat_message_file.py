"""Model `ChatMessageFile` — file người dùng đính kèm vào 1 lượt chat (đẩy lên Gemini).

Mỗi lần user gửi câu hỏi kèm `media_ids`, MỖI media → 1 row ở đây: trỏ tới bản ghi
`media` (do api-aio sở hữu, ta CHỈ ĐỌC) + cache URI sau khi đẩy file lên **Gemini
Files API**. Bảng này do CHÍNH ai-aio sở hữu (managed=True, có migration) — luồng
đính kèm KHÔNG ghi bất cứ thứ gì vào bảng `media`.

Vì sao tách bảng riêng (khác ga-ai lưu thẳng `uri`/`time_push` trên model media của
nó): bảng `media` ở ai-aio là `managed=False` (cấu trúc do api-aio quản, KHÔNG có cột
`uri`/`pushed_at`), nên trạng thái "đã đẩy Gemini" + URI phải sống ở bảng của ai-aio.

`media_id` để dạng số thường (KHÔNG ForeignKey): `media` là bảng ngoài → tránh ràng
buộc khoá ngoại chéo nguồn; cần metadata media thì query `Media` qua repo khi dùng
(giống cách `ChatConversation.user_id` không FK sang bảng `users` của api-aio).
"""

from __future__ import annotations

from django.db import models

from modules.base.models import SoftDeleteModel

from .chat_conversation import ChatConversation
from .chat_message import ChatMessage


class ChatMessageFile(SoftDeleteModel):
    """1 file đính kèm của 1 `ChatMessage` (role=user) — cache URI Gemini Files API."""

    TABLE = "chatbot_message_files"

    COL_CONVERSATION_ID = "conversation_id"
    COL_MESSAGE_ID = "message_id"
    COL_MEDIA_ID = "media_id"
    COL_GEMINI_URI = "gemini_uri"
    COL_PUSHED_AT = "pushed_at"

    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        db_column="conversation_id",
        related_name="message_files",
    )
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        db_column="message_id",
        related_name="files",
    )
    # `conversation_id`/`message_id` do ForeignKey tự sinh ở runtime — khai báo kiểu để
    # type checker không coi là Any/thiếu (annotation RỖNG, không gán value nên Django
    # KHÔNG hiểu nhầm thành field). Giống `ChatbotDocument.media_id`.
    conversation_id: int
    message_id: int
    # Id bản ghi `media` (bảng ngoài, managed=False) — KHÔNG FK để tránh ràng buộc chéo.
    # Tên gốc + mime KHÔNG lưu ở đây: tên đọc thẳng từ `media` lúc đính kèm, còn mime
    # đẩy Gemini luôn là PDF (file hỗ trợ chỉ PDF/Word→PDF) nên dùng hằng, khỏi lưu.
    media_id = models.BigIntegerField(db_index=True)
    # URI file trên Gemini Files API (dùng cho `types.Part.from_uri`) — rỗng nếu đẩy lỗi.
    gemini_uri = models.TextField(blank=True, default="")
    # Thời điểm đẩy lên Gemini — Files API có TTL (~48h) nên cần để biết khi nào re-push.
    pushed_at = models.DateTimeField(null=True, blank=True, default=None)

    class Meta(SoftDeleteModel.Meta):
        # = ChatMessageFile.TABLE (Meta lồng nhau không ref được const class).
        db_table = "chatbot_message_files"
        # Đọc theo thứ tự tạo (cũ → mới) để gắn file đúng thứ tự vào message.
        ordering = ["id"]

    def __str__(self) -> str:
        return f"ChatMessageFile#{self.pk} (media_id={self.media_id}, msg={self.message_id})"
