"""HTTP middleware của module Base — bản Django của `Modules\\Base\\Http\\Middleware`.

Export gọn để đăng ký trong `MIDDLEWARE` (config/settings.py) hoặc gắn per-route:
  - AuthenticateOptional   — optional auth, thiếu header thì đi tiếp như guest.
  - EnsureAuthenticated    — gate xác thực, thiếu/không thấy user thì 401.
  - ensure_authenticated   — decorator per-route của gate trên (kiểu Laravel
                             `Route::middleware('auth')`), bọc `View.as_view()`.
  - VerifyInternalToken    — chốt internal token cho path `/api/internal/` (sai → 403).
"""

from .authenticate_optional import AuthenticateOptional
from .ensure_authenticated import EnsureAuthenticated, ensure_authenticated
from .verify_internal_token import VerifyInternalToken

__all__ = [
    "AuthenticateOptional",
    "EnsureAuthenticated",
    "VerifyInternalToken",
    "ensure_authenticated",
]
