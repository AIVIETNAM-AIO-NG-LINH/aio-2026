"""HTTP middleware của module Base — bản Django của `Modules\\Base\\Http\\Middleware`.

Export gọn để đăng ký trong `MIDDLEWARE` (config/settings.py):
  - AuthenticateOptional — optional auth, thiếu header thì đi tiếp như guest.
  - EnsureAuthenticated  — gate xác thực, thiếu/không thấy user thì 401.
  - VerifyInternalToken  — chốt internal token cho path `/api/internal/` (sai → 403).
"""

from .authenticate_optional import AuthenticateOptional
from .ensure_authenticated import EnsureAuthenticated
from .verify_internal_token import VerifyInternalToken

__all__ = ["AuthenticateOptional", "EnsureAuthenticated", "VerifyInternalToken"]
