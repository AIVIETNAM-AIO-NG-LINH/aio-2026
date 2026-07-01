"""Repository cho `ChatConversation` — gom mọi truy vấn DB của bảng này một chỗ.

Service/task không query model trực tiếp mà đi qua repository (mirror pattern
Laravel của dự án gốc).
"""

from __future__ import annotations

from django.db.models import Exists, OuterRef, Q

from modules.base.app.repositories import BaseRepository

from ..contracts.repositories import ChatConversationRepositoryInterface
from ..enums import ConversationStatus
from ..models import ChatConversation, ChatMessage


class ChatConversationRepository(
    BaseRepository[ChatConversation], ChatConversationRepositoryInterface
):
    """Truy vấn `chat_conversations` theo nhu cầu của luồng chat."""

    model = ChatConversation

    def find_owned(self, conversation_id: int, user_id: int) -> ChatConversation | None:
        """Hội thoại theo id VÀ thuộc user — None nếu không tồn tại/không phải của user."""
        return self.query().filter(id=conversation_id, user_id=user_id).first()

    def find_owned_locked(
        self, conversation_id: int, user_id: int
    ) -> ChatConversation | None:
        """Như `find_owned` nhưng KHOÁ hàng (`SELECT ... FOR UPDATE`).

        Dùng để serialize các lượt chat đồng thời cùng hội thoại: hai request song
        song sẽ xếp hàng ở đây nên check `has_processing` + tạo placeholder trở
        thành atomic. BẮT BUỘC gọi trong `transaction.atomic()`.
        """
        return (
            self.query()
            .select_for_update()
            .filter(id=conversation_id, user_id=user_id)
            .first()
        )

    def create_open(self, user_id: int) -> ChatConversation:
        """Tạo hội thoại mới trạng thái OPEN cho user."""
        return self.create({"user_id": user_id, "status": ConversationStatus.OPEN})

    def paginate_for_user(
        self,
        user_id: int,
        page: int,
        limit: int,
        max_id: int | None = None,
        q: str | None = None,
    ) -> tuple[int, list[ChatConversation]]:
        """`(total, items)` hội thoại của user, mới nhất trước.

        `max_id` (tuỳ chọn) chốt một anchor cursor: chỉ tính các hội thoại có
        ``id <= max_id``. FE bắt id lớn nhất ở lần load đầu rồi gửi kèm mọi trang
        sau → snapshot ổn định, hội thoại mới tạo (id lớn hơn) bị loại khỏi cửa sổ
        phân trang nên không đẩy lệch các trang (khớp đúng ``order_by("-id")``).

        `q` (tuỳ chọn) lọc theo từ khoá: khớp `title` (icontains) HOẶC có ít nhất 1
        tin nhắn (`chatbot_messages.content`) chứa từ khoá. Dùng `Exists` subquery
        nên KHÔNG nhân dòng (mỗi hội thoại chỉ trả 1 lần dù khớp nhiều message); tin
        nhắn đã soft-delete bị loại sẵn (manager mặc định của `ChatMessage`).
        """
        qs = self.query().filter(user_id=user_id)
        if max_id is not None:
            qs = qs.filter(id__lte=max_id)
        if q:
            msg_match = ChatMessage.objects.filter(
                conversation_id=OuterRef("pk"), content__icontains=q
            )
            qs = qs.filter(Q(title__icontains=q) | Exists(msg_match))
        qs = qs.order_by("-id")
        offset = (page - 1) * limit
        return qs.count(), list(qs[offset : offset + limit])

    def set_title_if_empty(self, conversation_id: int, title: str) -> bool:
        """Ghi `title` CHỈ KHI đang NULL (update có điều kiện — idempotent khi đua)."""
        return bool(
            self.query()
            .filter(id=conversation_id, title__isnull=True)
            .update(title=title)
        )
