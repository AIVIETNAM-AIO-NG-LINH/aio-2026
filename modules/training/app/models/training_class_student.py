"""Model `TrainingClassStudent` — đăng ký HỌC VIÊN ↔ LỚP (bảng nối).

Mỗi dòng `Output_1_Data_hv_Cleaned.csv` là một lần học viên tham gia một lớp.
Khác file giảng viên: cặp `(lớp, học viên)` là KHÓA TỰ NHIÊN duy nhất (0 trùng)
nên đặt `unique_together(training_class, student)` để chặn đăng ký lặp.

`department` (FK → `TrainingDepartment`, cây tổ chức) và `title` (FK →
`TrainingTitle`) lưu tại đây (KHÔNG ở `TrainingStudent`) vì chúng thay đổi theo
thời gian — đây là ảnh chụp lúc học viên tham gia lớp, phục vụ câu hỏi kiểu
"bao nhiêu cán bộ quản lý đã được đào tạo" (đếm theo chức danh tại thời điểm học).
Các cột lớp (tên khóa, mã khóa, mã lớp) đã có ở `TrainingClass`, join qua
`budget_code` nên không lặp lại.
"""

from __future__ import annotations

from django.db import models

from modules.base.models import NotSoftDeleteModel

from modules.training.app.enums import StudentResult

from .training_class import TrainingClass
from .training_department import TrainingDepartment
from .training_student import TrainingStudent
from .training_title import TrainingTitle


class TrainingClassStudent(NotSoftDeleteModel):
    """Một lần học viên tham gia một lớp (kèm phòng/chức danh/điểm lúc học)."""

    training_class = models.ForeignKey(
        TrainingClass,
        on_delete=models.CASCADE,
        db_column="training_class_id",
        related_name="student_enrollments",
    )
    student = models.ForeignKey(
        TrainingStudent,
        on_delete=models.CASCADE,
        db_column="student_id",
        related_name="class_enrollments",
    )

    department = models.ForeignKey(                                        # Phòng/Trung tâm (snapshot lúc học) → training_departments
        TrainingDepartment,
        on_delete=models.SET_NULL,
        db_column="department_id",
        related_name="enrollments",
        null=True,
        blank=True,
    )
    title = models.ForeignKey(                                             # Chức danh (snapshot lúc học) → training_titles
        TrainingTitle,
        on_delete=models.SET_NULL,
        db_column="title_id",
        related_name="enrollments",
        null=True,
        blank=True,
    )
    score = models.DecimalField(                                           # Điểm (0–10; chỉ ~22% có điểm)
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    result = models.CharField(                                             # Đạt/Không đạt (luôn có — 100% dòng)
        max_length=16, choices=StudentResult.choices
    )

    class Meta(NotSoftDeleteModel.Meta):
        db_table = "training_class_students"
        ordering = ["-id"]
        unique_together = ("training_class", "student")

    def __str__(self) -> str:
        return f"TrainingClassStudent#{self.pk} (class={self.training_class_id} hv={self.student_id})"
