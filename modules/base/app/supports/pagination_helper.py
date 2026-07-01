"""Pagination helper — đọc `page`/`limit` từ query params của request DRF.

Dùng chung cho mọi controller cần phân trang: `page` mặc định 1, `limit` mặc định
20 (tối đa 100). Giá trị thiếu hoặc không parse được số → rơi về mặc định.
"""

from __future__ import annotations

from rest_framework.request import Request


def parse_pagination(request: Request) -> tuple[int, int]:
    """Đọc `page`/`limit` từ query (default 1/20, limit tối đa 100)."""

    def _int(name: str, default: int) -> int:
        try:
            return int(request.query_params.get(name, default))
        except (TypeError, ValueError):
            return default

    page = max(1, _int("page", 1))
    limit = max(1, min(_int("limit", 20), 100))
    return page, limit
