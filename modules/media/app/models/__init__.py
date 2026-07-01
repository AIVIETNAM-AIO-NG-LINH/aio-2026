"""Models của module Media — mỗi model 1 file, gom lại import ở đây.

Django cần model importable từ `modules.media.app.models`, nên mọi model mới thêm
vào package này phải được re-export tại đây.
"""

from .media import Media

__all__ = ["Media"]
