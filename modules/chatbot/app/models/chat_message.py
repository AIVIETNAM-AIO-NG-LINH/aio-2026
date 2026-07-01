"""Model `ChatMessage` — 1 tin nhắn (user hoặc assistant) trong hội thoại.

Mỗi lượt hỏi-đáp sinh 2 row: 1 role=USER (câu hỏi) + 1 role=ASSISTANT (câu trả
lời). Row ASSISTANT được tạo trước với status=PROCESSING rồi cập nhật `content`
+ `citations` + status sau khi stream xong (xem `ChatService`).

`citations` lưu danh sách nguồn (chunk RAG) đã dùng để sinh câu trả lời, dạng
JSON: `[{document_id, media_id, original_name, page, score}, ...]` — để FE hiển
thị "trích từ tài liệu X, trang Y".

`reasoning` lưu nội dung "suy nghĩ" (reasoning/thoughts) model phát trước câu trả
lời — để FE dựng lại khối thinking khi mở lại hội thoại (rỗng nếu model không nghĩ).

`mind_map` lưu sơ đồ tư duy (mind map) sinh THEO YÊU CẦU cho lượt đó — JSON node
phẳng `{title, nodes: [{id, parent_id, label, notes, link}, ...]}` — null nếu lượt
này người dùng không yêu cầu vẽ sơ đồ. FE render bằng markmap khi mở lại hội thoại.
"""

from __future__ import annotations

from django.db import models

from modules.base.app.models import SoftDeleteModel

from modules.chatbot.app.enums import MessageRole, MessageStatus

from .chat_conversation import ChatConversation


class ChatMessage(SoftDeleteModel):
    """Một tin nhắn thuộc về 1 `ChatConversation`."""

    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        db_column="conversation_id",
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=MessageRole.choices)
    content = models.TextField(blank=True, default="")
    # Suy nghĩ (reasoning) model phát trước câu trả lời — rỗng nếu không có / message USER.
    reasoning = models.TextField(blank=True, default="")
    # Nguồn trích dẫn (chunk RAG) cho message ASSISTANT — null với message USER.
    citations = models.JSONField(null=True, blank=True, default=None)
    # Sơ đồ tư duy (mind map) sinh theo yêu cầu — {title, nodes:[...]} hoặc null.
    mind_map = models.JSONField(null=True, blank=True, default=None)
    status = models.CharField(
        max_length=20,
        choices=MessageStatus.choices,
        default=MessageStatus.SUCCESS,
    )

    class Meta(SoftDeleteModel.Meta):
        db_table = "chatbot_messages"
        # Tin nhắn đọc theo thứ tự thời gian (cũ → mới) để dựng lịch sử hội thoại.
        ordering = ["id"]

    def __str__(self) -> str:
        return f"ChatMessage#{self.pk} ({self.role} @ conv={self.conversation_id})"
