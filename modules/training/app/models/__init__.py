"""Models của module Training — mỗi model 1 file, gom lại import ở đây.

Django cần model importable từ `modules.training.app.models`, nên mọi model mới
thêm vào package này phải được re-export tại đây.
"""

from .training_staff import TrainingStaff
from .training_period import TrainingPeriod
from .training_class import TrainingClass
from .training_instructor import TrainingInstructor
from .training_class_instructor import TrainingClassInstructor

__all__ = [
    "TrainingStaff",
    "TrainingPeriod",
    "TrainingClass",
    "TrainingInstructor",
    "TrainingClassInstructor",
]
