"""Exception nghiệp vụ — clone `App\\Exceptions\\Exception` & `ExceptionFailSuccess`.

Cặp đôi với `handler.api_exception_handler` (cùng package, đăng ký ở
`REST_FRAMEWORK["EXCEPTION_HANDLER"]`) — handler đó đóng vai trò `render()` của
exception bên Laravel: dựng JSON đúng shape rồi trả về.

Cả hai kế thừa `APIException` để DRF tự bắt và đẩy qua exception handler khi raise
trong view; còn `status_code` / payload thì do handler quyết định theo từng loại.
"""

from __future__ import annotations

from typing import Any

from rest_framework import status as http_status
from rest_framework.exceptions import APIException

from ..constants import RES_FAILED


class ApiException(APIException):
    """≈ `App\\Exceptions\\Exception`.

    Render thành `{ "data": { "message": <message> } }` với HTTP `status_code`.
    """

    status_code = http_status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, status_code: int = http_status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(detail=message, code=status_code)


class FailSuccessException(APIException):
    """≈ `App\\Exceptions\\ExceptionFailSuccess`.

    Fail thuộc luồng nghiệp vụ (login sai, state machine chặn action) — KHÔNG phải
    HTTP error. Render thành **HTTP 200** với
    `{ "data": { "message": <message>, "success": <success>, "data": <data> } }`.
    """

    status_code = http_status.HTTP_200_OK

    def __init__(self, message: str, success: int = RES_FAILED, data: dict[str, Any] | None = None):
        self.message = message
        # Mirror `if (!$success) $success = RES_FAILD;`
        self.success = success or RES_FAILED
        self.data = data or {}
        super().__init__(detail=message)


class RequestValidationException(APIException):
    """≈ `BaseFormDataRequestV2::failedValidation()`.

    Render thành HTTP **422** với shape V1 (giữ nguyên cho FE):
    `{ "data": { "status": 422, "message": <message>, "data": { <field>: <first error> } } }`.
    """

    status_code = http_status.HTTP_422_UNPROCESSABLE_ENTITY

    def __init__(self, fields: dict[str, str], message: str = "Invalid data transmission"):
        self.fields = fields
        self.message = message
        super().__init__(detail=message)
