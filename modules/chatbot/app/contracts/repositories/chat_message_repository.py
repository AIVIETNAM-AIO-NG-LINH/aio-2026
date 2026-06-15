"""Contract cho `ChatMessageRepository` — các truy vấn domain bắt buộc.

Khai báo "cái gì" (hợp đồng); implementation ở `repositories/`. Method CRUD nền
(`find`, `create`, ...) đã nằm ở `BaseRepository` nên không lặp lại ở đây.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models import ChatConversation, ChatMessage


class ChatMessageRepositoryInterface(ABC):
    """Hợp đồng truy vấn `chat_messages` cho luồng chat."""

    @abstractmethod
    def has_processing(self, conversation_id: int) -> bool:
        """Hội thoại còn message PROCESSING (lượt trước chưa xong) hay không."""
        ...

    @abstractmethod
    def add_user_message(
        self, conversation: ChatConversation, content: str
    ) -> ChatMessage:
        """Lưu câu hỏi của user (SUCCESS ngay — không có bước xử lý sau)."""
        ...

    @abstractmethod
    def add_assistant_placeholder(self, conversation: ChatConversation) -> ChatMessage:
        """Tạo placeholder câu trả lời (PROCESSING, content rỗng) cho lượt hiện tại."""
        ...

    @abstractmethod
    def mark_success(
        self, message: ChatMessage, answer: str, citations: list[dict]
    ) -> None:
        """Chốt câu trả lời thành công — chỉ ghi các cột thay đổi."""
        ...

    @abstractmethod
    def mark_error(self, message: ChatMessage, partial: str) -> None:
        """Đánh dấu lượt lỗi — giữ phần text đã stream được (nếu có)."""
        ...

    @abstractmethod
    def recent_success(
        self, conversation_id: int, exclude_ids: list[int], limit: int
    ) -> list[ChatMessage]:
        """`limit` message SUCCESS gần nhất (bỏ `exclude_ids` + content rỗng), cũ → mới."""
        ...

    @abstractmethod
    def paginate_for_conversation(
        self, conversation_id: int, page: int, limit: int
    ) -> tuple[int, list[ChatMessage]]:
        """`(total, items)` tin nhắn của hội thoại, cũ → mới."""
        ...
