"""Auth gate middleware — bản Django của `Modules\\Base\\Http\\Middleware\\EnsureAuthenticated`.

Gate xác thực duy nhất — tin tưởng header `X-Auth-User-Id` do nginx `auth_request`
inject sau khi `/auth/verify` xác minh token.

Trách nhiệm: đọc `X-Auth-User-Id`, 401 nếu thiếu/không tìm thấy user, ngược lại
populate ``CurrentUser`` cho downstream rồi đi tiếp.

KHÔNG còn tách admin/user, KHÔNG còn check quyền — login là đủ.

Verify "user có thật trong DB" do nginx `auth_request` lo trước; ở đây chỉ trust
header rồi set id vào ``CurrentUser`` cho downstream.
"""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse

from modules.base.singletons import CurrentUser


class EnsureAuthenticated:
    """Đọc `X-Auth-User-Id`, thiếu/không thấy user thì 401; ngược lại set CurrentUser."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        user_id = int(request.headers.get("X-Auth-User-Id", "0") or "0")

        if user_id <= 0:
            return JsonResponse({"message": "Unauthenticated"}, status=401)

        CurrentUser().set(user_id)

        return self.get_response(request)
