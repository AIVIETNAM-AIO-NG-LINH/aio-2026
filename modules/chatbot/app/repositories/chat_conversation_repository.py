"""Repository cho `ChatConversation` — gom mọi truy vấn DB của bảng này một chỗ.

Service/task không query model trực tiếp mà đi qua repository (mirror pattern
Laravel của dự án gốc).
"""

from __future__ import annotations

from modules.base.repositories import BaseRepository

from ..contracts.repositories import ChatConversationRepositoryInterface
from ..enums import ConversationStatus
from ..models import ChatConversation


class ChatConversationRepository(
    BaseRepository[ChatConversation], ChatConversationRepositoryInterface
):
    """Truy vấn `chat_conversations` theo nhu cầu của luồng chat."""

    model = ChatConversation

    def find_owned(self, conversation_id: int, user_id: int) -> ChatConversation | None:
        """Hội thoại theo id VÀ thuộc user — None nếu không tồn tại/không phải của user."""
        return self.query().filter(id=conversation_id, user_id=user_id).first()

    def create_open(self, user_id: int) -> ChatConversation:
        """Tạo hội thoại mới trạng thái OPEN cho user."""
        return self.create({"user_id": user_id, "status": ConversationStatus.OPEN})

    def paginate_for_user(
        self, user_id: int, page: int, limit: int
    ) -> tuple[int, list[ChatConversation]]:
        """`(total, items)` hội thoại của user, mới nhất trước."""
        qs = self.query().filter(user_id=user_id).order_by("-id")
        offset = (page - 1) * limit
        return qs.count(), list(qs[offset : offset + limit])

    def set_title_if_empty(self, conversation_id: int, title: str) -> bool:
        """Ghi `title` CHỈ KHI đang NULL (update có điều kiện — idempotent khi đua)."""
        return bool(
            self.query()
            .filter(id=conversation_id, title__isnull=True)
            .update(title=title)
        )
