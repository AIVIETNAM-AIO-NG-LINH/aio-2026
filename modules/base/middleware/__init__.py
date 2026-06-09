"""HTTP middleware của module Base — bản Django của `Modules\\Base\\Http\\Middleware`.

Export gọn để đăng ký trong `MIDDLEWARE` (config/settings.py):
  - AuthenticateOptional — optional auth, thiếu header thì đi tiếp như guest.
  - EnsureAuthenticated  — gate xác thực, thiếu/không thấy user thì 401.
"""

from .authenticate_optional import AuthenticateOptional
from .ensure_authenticated import EnsureAuthenticated

__all__ = ["AuthenticateOptional", "EnsureAuthenticated"]
