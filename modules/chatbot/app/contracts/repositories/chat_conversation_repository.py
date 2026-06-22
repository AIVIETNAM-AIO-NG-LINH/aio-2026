"""Contract cho `ChatConversationRepository` — các truy vấn domain bắt buộc.

Khai báo "cái gì" (hợp đồng); implementation ở `repositories/`. Method CRUD nền
(`find`, `create`, ...) đã nằm ở `BaseRepository` nên không lặp lại ở đây.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models import ChatConversation


class ChatConversationRepositoryInterface(ABC):
    """Hợp đồng truy vấn `chat_conversations` cho luồng chat."""

    @abstractmethod
    def find_owned(self, conversation_id: int, user_id: int) -> ChatConversation | None:
        """Hội thoại theo id VÀ thuộc user — None nếu không có / không phải của user."""
        ...

    @abstractmethod
    def find_owned_locked(
        self, conversation_id: int, user_id: int
    ) -> ChatConversation | None:
        """Như `find_owned` nhưng khoá hàng (`SELECT ... FOR UPDATE`); gọi trong transaction."""
        ...

    @abstractmethod
    def create_open(self, user_id: int) -> ChatConversation:
        """Tạo hội thoại mới trạng thái OPEN cho user."""
        ...

    @abstractmethod
    def paginate_for_user(
        self,
        user_id: int,
        page: int,
        limit: int,
        max_id: int | None = None,
        q: str | None = None,
    ) -> tuple[int, list[ChatConversation]]:
        """`(total, items)` hội thoại của user, mới nhất trước.

        `max_id` (tuỳ chọn) chốt anchor cursor: chỉ tính hội thoại có ``id <= max_id``.
        `q` (tuỳ chọn) lọc theo từ khoá: khớp `title` HOẶC nội dung tin nhắn.
        """
        ...

    @abstractmethod
    def set_title_if_empty(self, conversation_id: int, title: str) -> bool:
        """Ghi `title` CHỈ KHI đang NULL (update có điều kiện — idempotent khi đua)."""
        ...
