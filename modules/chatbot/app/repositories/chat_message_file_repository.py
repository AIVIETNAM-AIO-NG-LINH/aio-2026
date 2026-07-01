"""Repository cho `ChatMessageFile` — truy vấn cache file đính kèm + URI Gemini.

Gom mọi truy vấn DB của bảng `chatbot_message_files` một chỗ (mirror pattern Laravel):
service/helper không query model trực tiếp. `query()` của base đã loại row soft-delete.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from modules.base.app.repositories import BaseRepository

from ..models import ChatMessageFile


class ChatMessageFileRepository(BaseRepository[ChatMessageFile]):
    """Truy vấn `chatbot_message_files` theo nhu cầu của luồng đính kèm file."""

    model = ChatMessageFile

    def find_fresh_for_media(
        self, media_id: int, ttl_hours: int
    ) -> ChatMessageFile | None:
        """Row gần nhất của `media_id` đã đẩy Gemini còn trong hạn TTL (tái dùng URI).

        Gemini Files API tự xoá file sau ~48h; chỉ tái dùng URI nếu `pushed_at` còn
        trong `ttl_hours`. None nếu chưa từng đẩy / đã quá hạn → caller tự re-push.
        Cho phép tái dùng URI giữa các lượt/hội thoại của cùng 1 media (đỡ upload lại).
        """
        cutoff = timezone.now() - timedelta(hours=ttl_hours)
        return (
            self.query()
            .filter(media_id=media_id, pushed_at__gte=cutoff)
            .exclude(gemini_uri="")
            .order_by("-id")
            .first()
        )

    def for_message_ids(
        self, message_ids: list[int]
    ) -> dict[int, list[ChatMessageFile]]:
        """Gom file đính kèm theo `message_id` (cho nạp lại lịch sử có file).

        Trả dict rỗng nếu không có id nào. Mỗi message → list file đúng thứ tự tạo.
        """
        grouped: dict[int, list[ChatMessageFile]] = {}
        if not message_ids:
            return grouped
        rows = self.query().filter(message_id__in=message_ids).order_by("id")
        for row in rows:
            grouped.setdefault(row.message_id, []).append(row)
        return grouped
