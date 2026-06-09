"""Internal-token gate middleware — chốt cho endpoint nội bộ (service-to-service).

Chỉ áp dụng cho các path dưới prefix `/api/internal/` (request user thường đi tiếp
như bình thường). Với các path đó: header `X-Internal-Token` PHẢI khớp
``settings.INTERNAL_TOKEN``, sai/thiếu → 403.

Chỉ chứng minh "là service trong hệ AIO" — KHÔNG gắn danh tính user. Đi kèm
reverse-proxy nội bộ nginx:8080 (chỉ container trong aio-net tới được); nginx đã
chặn 401 khi thiếu header, lớp này kiểm tra GIÁ TRỊ token (sai → 403).
"""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils.crypto import constant_time_compare

INTERNAL_PATH_PREFIX = "/api/internal/"


class VerifyInternalToken:
    """Chặn path `/api/internal/` nếu `X-Internal-Token` không khớp settings."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if request.path.startswith(INTERNAL_PATH_PREFIX):
            expected = settings.INTERNAL_TOKEN or ""
            provided = request.headers.get("X-Internal-Token", "")

            if not (expected and constant_time_compare(expected, provided)):
                return JsonResponse({"message": "Forbidden"}, status=403)

        return self.get_response(request)
