"""Helper dùng chung cho các view CÔNG KHAI (phân trang).

Danh tính user KHÔNG đọc ở đây — gate `ensure_authenticated` (urls/public.py)
chặn 401 + populate ``CurrentUser``, view đọc ``CurrentUser().get_id()``.
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
