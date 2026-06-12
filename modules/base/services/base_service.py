"""Base Service cho module mới — bản Django/DRF của `BaseServiceV2` (Laravel).

Giữ nguyên API V1 để shape response FE không đổi:
  - response_success()        — wrap `{ data: { ... , success: 1 } }`, status 200.
  - response_success_json()   — raw JSON, không wrap.
  - exception()               — raise ApiException với status.
  - not_permission()          — sugar 403.
  - not_found()               — sugar 404 cho "resource không tồn tại / không thuộc bạn".
  - response_success_failed() — raise FailSuccessException: HTTP 200 nhưng body có
    `success: 0` cho fail nghiệp vụ (login sai, state không hợp lệ), không phải HTTP error.

Các method raise dựa vào `exceptions.api_exception_handler` (đăng ký ở
REST_FRAMEWORK) để render — mirror cơ chế `render()` của exception bên Laravel.
"""

from __future__ import annotations

from typing import Any, NoReturn

from rest_framework import status as http_status
from rest_framework.response import Response

from ..constants import RES_FAILED, RES_SUCCESS
from ..exceptions import ApiException, FailSuccessException


class BaseService:
    """Base Service — `abstract` như Laravel: chỉ dùng qua subclass."""

    def __init__(self) -> None:
        if type(self) is BaseService:
            raise TypeError("BaseService là abstract — hãy kế thừa, không instantiate trực tiếp.")

    def response_success(
        self,
        data: dict[str, Any],
        status: int = http_status.HTTP_200_OK,
    ) -> Response:
        """Response success — wrap data trong key `data`, tự thêm `success: 1`."""
        # Mirror `if (! isset($data['success']))` — vắng key hoặc value None đều set.
        if data.get("success") is None:
            data = {**data, "success": RES_SUCCESS}
        return Response({"data": data}, status=status)

    def response_success_json(
        self,
        data: dict[str, Any],
        status: int = http_status.HTTP_200_OK,
    ) -> Response:
        """Response raw JSON — không wrap (vd token grant, file metadata)."""
        return Response(data, status=status)

    def exception(self, message: str, status_code: int) -> NoReturn:
        """Raise HTTP error. Subclass thường dùng sugar bên dưới hơn."""
        raise ApiException(message, status_code)

    def not_permission(self, message: str) -> NoReturn:
        """Sugar — raise 403 Forbidden."""
        raise ApiException(message, http_status.HTTP_403_FORBIDDEN)

    def not_found(self, message: str) -> NoReturn:
        """Sugar — raise 404 Not Found (resource không tồn tại / không thuộc bạn)."""
        raise ApiException(message, http_status.HTTP_404_NOT_FOUND)

    def response_success_failed(
        self,
        message: str,
        success: int = RES_FAILED,
        data: dict[str, Any] | None = None,
    ) -> NoReturn:
        """Raise fail nghiệp vụ — HTTP 200 + body `{ success: 0, message, data }`."""
        raise FailSuccessException(message, success, data or {})
