"""Nạp lịch sử hội thoại (sliding window) thành `types.Content` cho Gemini.

Lấy N tin nhắn gần nhất của hội thoại (cả USER lẫn ASSISTANT, status SUCCESS) theo
thứ tự thời gian, bỏ qua message đang xử lý của lượt hiện tại. Mỗi message → 1
`Content` với role hợp lệ của Gemini ("user" / "model").

File user đính kèm ở các lượt cũ được GẮN LẠI vào đúng message của chúng (Part
Gemini Files API) để các lượt hỏi tiếp vẫn "thấy" tài liệu — giống `memory.py` ga-ai.
"""

from __future__ import annotations

import logging

from google.genai import types

from modules.chatbot.app.enums import MessageRole
from modules.chatbot.app.models import ChatConversation, ChatMessage
from modules.chatbot.app.repositories import ChatMessageRepository

logger = logging.getLogger(__name__)

_messages = ChatMessageRepository()


def _genai_role(role: str) -> str:
    """Map role nội bộ → role Gemini: ASSISTANT → 'model', còn lại → 'user'."""
    return "model" if role == MessageRole.ASSISTANT else "user"


def _attachment_parts_by_message(
    messages: list[ChatMessage],
) -> dict[int, list[types.Part]]:
    """File parts (Gemini Files API) cho các message cũ có đính kèm — FAIL-SAFE.

    Lỗi (DB/đẩy lại Gemini) chỉ log → lịch sử vẫn nạp được phần text, không phá lượt.
    """
    try:
        from modules.chatbot.app.support.chat_attachments import ChatAttachments

        return ChatAttachments().history_parts(messages)
    except Exception:
        logger.exception("[chat] nạp file đính kèm cho lịch sử lỗi (bỏ qua)")
        return {}


def load_history_contents(
    conversation: ChatConversation,
    exclude_message_ids: list[int],
    limit: int,
) -> list[types.Content]:
    """Trả `limit` tin nhắn gần nhất (đã hoàn tất) dạng Content, cũ → mới.

    `exclude_message_ids`: id các message vừa tạo cho lượt hiện tại (câu hỏi user
    + placeholder assistant) — không đưa vào lịch sử. Message USER cũ nào có file
    đính kèm thì Content của nó gồm cả text + các Part file.
    """
    messages = _messages.recent_success(conversation.id, exclude_message_ids, limit)
    files_by_message = _attachment_parts_by_message(messages)

    contents: list[types.Content] = []
    for msg in messages:
        parts: list[types.Part] = [types.Part(text=msg.content)]
        parts.extend(files_by_message.get(msg.id, []))
        contents.append(types.Content(role=_genai_role(msg.role), parts=parts))
    return contents
