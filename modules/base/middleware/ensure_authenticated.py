"""Auth gate middleware — bản Django của `Modules\\Base\\Http\\Middleware\\EnsureAuthenticated`.

Gate xác thực duy nhất — tin tưởng header `X-Auth-User-Id` do nginx `auth_request`
inject sau khi `/auth/verify` xác minh token.

Trách nhiệm: đọc `X-Auth-User-Id`, 401 nếu thiếu/không tìm thấy user, ngược lại
populate ``CurrentUser`` cho downstream rồi đi tiếp.

KHÔNG còn tách admin/user, KHÔNG còn check quyền — login là đủ.

Verify "user có thật trong DB" do nginx `auth_request` lo trước; ở đây chỉ trust
header rồi set id vào ``CurrentUser`` cho downstream.

Dùng theo kiểu route middleware của Laravel (``Route::middleware('auth')``): viết
dạng ``MiddlewareMixin.process_request`` nên vừa đăng ký global trong ``MIDDLEWARE``
được, vừa gắn per-route qua decorator ``ensure_authenticated`` (xuất sẵn dưới đây):

    path("chat", ensure_authenticated(ChatView.as_view()))
"""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import decorator_from_middleware
from django.utils.deprecation import MiddlewareMixin

from modules.base.catalogs import CommonCatalog
from modules.base.singletons import CurrentUser
from modules.base.supports import translate


class EnsureAuthenticated(MiddlewareMixin):
    """Đọc `X-Auth-User-Id`, thiếu/không thấy user thì 401; ngược lại set CurrentUser."""

    def process_request(self, request: HttpRequest):
        try:
            user_id = int(request.headers.get("X-Auth-User-Id", "0") or "0")
        except (TypeError, ValueError):
            user_id = 0

        if user_id <= 0:
            return JsonResponse(
                {"message": translate("Chưa xác thực", CommonCatalog.UNAUTHENTICATED)},
                status=401,
            )

        CurrentUser().set(user_id)
        return None


# Decorator gắn per-route (tương đương route middleware Laravel).
ensure_authenticated = decorator_from_middleware(EnsureAuthenticated)
