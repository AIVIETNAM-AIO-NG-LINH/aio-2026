"""Repository cho `Media` — gom truy vấn bảng `media` một chỗ (mirror pattern Laravel).

Bảng `media` do api-aio sở hữu (`managed=False`); module này CHỈ ĐỌC. Service/helper
KHÔNG query `Media.objects` trực tiếp mà đi qua repository này. `query()` của base dùng
manager mặc định nên bản ghi soft-delete tự bị loại.
"""

from __future__ import annotations

from modules.base.repositories import BaseRepository

from ..models import Media


class MediaRepository(BaseRepository[Media]):
    """Truy vấn `media` (bảng dùng chung, managed=False — chỉ đọc)."""

    model = Media

    def map_by_id(self, media_ids: list[int]) -> dict[int, Media]:
        """Map `id → Media` cho list id (1 query) — tiện tra khi đính kèm nhiều file.

        Bỏ qua id không tồn tại / đã soft-delete (đơn giản là không có trong map).
        """
        if not media_ids:
            return {}
        return {m.pk: m for m in self.query().filter(pk__in=media_ids)}
