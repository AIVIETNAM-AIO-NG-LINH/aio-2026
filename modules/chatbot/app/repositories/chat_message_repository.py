"""Repository cho `ChatMessage` — gom mọi truy vấn DB của bảng này một chỗ.

Service/helper không query model trực tiếp mà đi qua repository (mirror pattern
Laravel của dự án gốc).
"""

from __future__ import annotations

from modules.base.repositories import BaseRepository

from ..contracts.repositories import ChatMessageRepositoryInterface
from ..enums import MessageRole, MessageStatus
from ..models import ChatConversation, ChatMessage


class ChatMessageRepository(
    BaseRepository[ChatMessage], ChatMessageRepositoryInterface
):
    """Truy vấn `chat_messages` theo nhu cầu của luồng chat."""

    model = ChatMessage

    def has_processing(self, conversation_id: int) -> bool:
        """Hội thoại còn message PROCESSING (lượt trước chưa xong) hay không."""
        return (
            self.query()
            .filter(conversation_id=conversation_id, status=MessageStatus.PROCESSING)
            .exists()
        )

    def add_user_message(
        self, conversation: ChatConversation, content: str
    ) -> ChatMessage:
        """Lưu câu hỏi của user (SUCCESS ngay — không có bước xử lý sau)."""
        return self.create(
            {
                "conversation": conversation,
                "role": MessageRole.USER,
                "content": content,
                "status": MessageStatus.SUCCESS,
            }
        )

    def add_assistant_placeholder(self, conversation: ChatConversation) -> ChatMessage:
        """Tạo placeholder câu trả lời (PROCESSING, content rỗng) cho lượt hiện tại."""
        return self.create(
            {
                "conversation": conversation,
                "role": MessageRole.ASSISTANT,
                "content": "",
                "status": MessageStatus.PROCESSING,
            }
        )

    def mark_success(
        self,
        message: ChatMessage,
        answer: str,
        citations: list[dict],
        reasoning: str = "",
    ) -> None:
        """Chốt câu trả lời thành công — chỉ ghi các cột thay đổi (update_fields)."""
        message.content = answer
        message.citations = citations
        message.reasoning = reasoning
        message.status = MessageStatus.SUCCESS
        message.save(
            update_fields=["content", "citations", "reasoning", "status", "updated_at"]
        )

    def mark_error(self, message: ChatMessage, partial: str, reasoning: str = "") -> None:
        """Đánh dấu lượt lỗi — giữ phần text + reasoning đã stream được (nếu có)."""
        message.content = partial
        message.reasoning = reasoning
        message.status = MessageStatus.ERROR
        message.save(update_fields=["content", "reasoning", "status", "updated_at"])

    def recent_success(
        self, conversation_id: int, exclude_ids: list[int], limit: int
    ) -> list[ChatMessage]:
        """`limit` message SUCCESS gần nhất (bỏ `exclude_ids` + content rỗng), cũ → mới.

        Query mới-nhất-trước để cắt đúng N message cuối, rồi đảo lại cho đúng
        thứ tự thời gian.
        """
        qs = (
            self.query()
            .filter(conversation_id=conversation_id, status=MessageStatus.SUCCESS)
            .exclude(id__in=exclude_ids)
            .exclude(content="")
            .order_by("-id")[:limit]
        )
        return list(reversed(list(qs)))

    def paginate_for_conversation(
        self, conversation_id: int, page: int, limit: int
    ) -> tuple[int, list[ChatMessage]]:
        """`(total, items)` tin nhắn của hội thoại, cũ → mới."""
        qs = self.query().filter(conversation_id=conversation_id).order_by("id")
        offset = (page - 1) * limit
        return qs.count(), list(qs[offset : offset + limit])
