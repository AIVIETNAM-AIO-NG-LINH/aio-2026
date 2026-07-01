"""Optional auth middleware — bản Django của `Modules\\Base\\Http\\Middleware\\AuthenticateOptional`.

Optional auth — KHÔNG bắt buộc login. Nếu nginx `auth_request` đã inject header
`X-Auth-User-Id` (token hợp lệ) thì populate ``CurrentUser``; không có thì đi tiếp
như guest (KHÔNG trả 401).

Khác ``EnsureAuthenticated`` ở chỗ thiếu `X-Auth-User-Id` không ném 401 mà đi tiếp
như guest.

Có header thì trust id rồi set vào ``CurrentUser``; không có thì đi tiếp guest
(``get_id()`` của downstream sẽ là 0).
"""

from __future__ import annotations

from django.http import HttpRequest

from modules.base.app.singletons import CurrentUser


class AuthenticateOptional:
    """Đọc `X-Auth-User-Id`, có user thì set CurrentUser; không thì đi tiếp guest."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        user_id = int(request.headers.get("X-Auth-User-Id", "0") or "0")

        if user_id > 0:
            CurrentUser().set(user_id)

        return self.get_response(request)
