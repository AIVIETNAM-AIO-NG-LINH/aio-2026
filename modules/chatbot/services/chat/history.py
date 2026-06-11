"""Nạp lịch sử hội thoại (sliding window) thành `types.Content` cho Gemini.

Lấy N tin nhắn gần nhất của hội thoại (cả USER lẫn ASSISTANT, status SUCCESS) theo
thứ tự thời gian, bỏ qua message đang xử lý của lượt hiện tại. Mỗi message → 1
`Content` với role hợp lệ của Gemini ("user" / "model").
"""

from __future__ import annotations

from google.genai import types

from modules.chatbot.enums import MessageRole, MessageStatus
from modules.chatbot.models import ChatConversation, ChatMessage


def _genai_role(role: str) -> str:
    """Map role nội bộ → role Gemini: ASSISTANT → 'model', còn lại → 'user'."""
    return "model" if role == MessageRole.ASSISTANT else "user"


def load_history_contents(
    conversation: ChatConversation,
    exclude_message_ids: list[int],
    limit: int,
) -> list[types.Content]:
    """Trả `limit` tin nhắn gần nhất (đã hoàn tất) dạng Content, cũ → mới.

    `exclude_message_ids`: id các message vừa tạo cho lượt hiện tại (câu hỏi user
    + placeholder assistant) — không đưa vào lịch sử.
    """
    qs = (
        ChatMessage.objects.filter(
            conversation_id=conversation.id,
            status=MessageStatus.SUCCESS,
        )
        .exclude(id__in=exclude_message_ids)
        .exclude(content="")
        .order_by("-id")[:limit]
    )
    # Lấy mới-nhất-trước để giới hạn N, rồi đảo lại cho đúng thứ tự thời gian.
    messages = list(reversed(list(qs)))
    return [
        types.Content(
            role=_genai_role(msg.role),
            parts=[types.Part(text=msg.content)],
        )
        for msg in messages
    ]
