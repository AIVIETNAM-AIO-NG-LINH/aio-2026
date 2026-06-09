"""Exception handler toàn cục — đóng vai `render()` của exception bên Laravel.

Đăng ký ở `REST_FRAMEWORK["EXCEPTION_HANDLER"]`. Bắt 2 exception nghiệp vụ của
base module và dựng JSON đúng shape FE đang dùng; các lỗi khác để DRF xử lý mặc định.
"""

from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .exceptions import ApiException, FailSuccessException, RequestValidationException


def api_exception_handler(exc, context):
    """Render exception nghiệp vụ của base module, còn lại fallback DRF."""
    if isinstance(exc, RequestValidationException):
        # ≈ failedValidation() — HTTP 422, body lồng status + message + lỗi từng field.
        return Response(
            {
                "data": {
                    "status": exc.status_code,
                    "message": exc.message,
                    "data": exc.fields,
                }
            },
            status=exc.status_code,
        )

    if isinstance(exc, FailSuccessException):
        # ≈ ExceptionFailSuccess::render() — HTTP 200, body có success + data.
        return Response(
            {
                "data": {
                    "message": exc.message,
                    "success": exc.success,
                    "data": exc.data,
                }
            },
            status=exc.status_code,
        )

    if isinstance(exc, ApiException):
        # ≈ Exception::render() — { data: { message } } + status_code.
        return Response({"data": {"message": exc.message}}, status=exc.status_code)

    return drf_exception_handler(exc, context)
