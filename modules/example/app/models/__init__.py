"""Models của module Example — mỗi model 1 file, gom lại import ở đây.

Django cần model importable từ `modules.example.app.models`, nên mọi model mới
thêm vào package này phải được re-export tại đây.
"""

from .example import Example

__all__ = ["Example"]
