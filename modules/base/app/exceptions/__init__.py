"""Exception nghiệp vụ + handler — bản Django của `app/Exceptions`.

  - exceptions.py → ApiException, FailSuccessException, RequestValidationException
  - handler.py    → api_exception_handler (đăng ký ở REST_FRAMEWORK["EXCEPTION_HANDLER"])

Import gọn: `from modules.base.app.exceptions import ApiException, api_exception_handler`.
"""

from .exceptions import ApiException, FailSuccessException, RequestValidationException
from .handler import api_exception_handler

__all__ = [
    "ApiException",
    "FailSuccessException",
    "RequestValidationException",
    "api_exception_handler",
]
