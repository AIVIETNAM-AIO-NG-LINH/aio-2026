"""CurrentUser singleton — bản Django của `Modules\\Base\\Singletons\\CurrentUser`.

Per-request holder cho user đã xác thực. Bản này CHỈ giữ `id` (không giữ cả model
User) — đủ cho downstream cần biết "ai đang gọi"; muốn thuộc tính khác thì tự load
qua repository/cache theo id.

Khác Laravel (bind `singleton()` qua container, mỗi request 1 instance):
Django không có DI container nên dùng ``contextvars.ContextVar`` làm state per-request.
Nhờ vậy dù ``CurrentUser()`` được khởi tạo nhiều lần (mỗi middleware một instance)
tất cả vẫn đọc/ghi chung một ô nhớ theo request — đúng ngữ nghĩa singleton-per-request.

Populate bởi middleware xác thực (``EnsureAuthenticated`` / ``AuthenticateOptional``)
sau khi đọc header `X-Auth-User-Id`. Request chưa qua middleware đó → ``get_id()``
trả 0 (guest).

Đây là "current user" duy nhất của hệ thống — KHÔNG tách admin/user, KHÔNG còn lớp
phân quyền (login là đủ).
"""

from __future__ import annotations

import contextvars

# State per-request — default 0 nghĩa là guest (chưa đăng nhập).
_current_user_id: contextvars.ContextVar[int] = contextvars.ContextVar(
    "current_user_id", default=0
)


class CurrentUser:
    """Holder id user hiện tại theo request. Chưa đăng nhập → id = 0."""

    def set(self, user_id: int) -> None:
        """Gán id user cho request hiện tại."""
        _current_user_id.set(int(user_id))

    def get_id(self) -> int:
        """Id user hiện tại; chưa đăng nhập (guest) → 0."""
        return _current_user_id.get()

    def reset(self) -> None:
        """Xoá state về guest — gọi khi kết thúc/khởi đầu một request nếu cần."""
        _current_user_id.set(0)
