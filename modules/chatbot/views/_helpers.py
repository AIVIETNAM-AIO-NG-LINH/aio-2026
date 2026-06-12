"""Helper dùng chung cho các view CÔNG KHAI (đọc danh tính user + phân trang)."""

from __future__ import annotations

from rest_framework import status as http_status
from rest_framework.request import Request

from modules.base.exceptions import ApiException


def resolve_user_id(request: Request) -> int:
    """Lấy user_id từ header `X-Auth-User-Id` (nginx set). Thiếu/sai → 401."""
    raw = request.headers.get("X-Auth-User-Id")
    if not raw:
        raise ApiException(
            "Thiếu danh tính người dùng (X-Auth-User-Id).",
            http_status.HTTP_401_UNAUTHORIZED,
        )
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ApiException(
            "X-Auth-User-Id không hợp lệ.", http_status.HTTP_401_UNAUTHORIZED
        )


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
