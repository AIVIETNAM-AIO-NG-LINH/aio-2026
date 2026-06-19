"""Model `TrainingClassInstructor` — phân công GIẢNG VIÊN ↔ LỚP (bảng nối).

Mỗi dòng `Data_Giang_Vien_Clean.csv` là một lần phân công: 1 lớp có nhiều GV,
và điểm học viên chấm / thời lượng giờ là RIÊNG theo từng GV trong lớp → phải
nằm ở bảng nối, không gộp lên `TrainingClass` hay `TrainingInstructor`.

KHÔNG đặt `unique_together(class, instructor)`: dữ liệu có 99 cặp trùng
(cùng GV ghi nhiều dòng trong một lớp) — coi mỗi dòng là một bản ghi phân công.
Các cột lớp (mã khóa, tháng học, ngày, quản lý lớp) đã có ở `TrainingClass`,
join qua `budget_code` nên không lặp lại tại đây.
"""

from __future__ import annotations

from django.db import models

from modules.base.models import NotSoftDeleteModel

from .training_class import TrainingClass
from .training_instructor import TrainingInstructor


class TrainingClassInstructor(NotSoftDeleteModel):
    """Một lần phân công giảng viên cho một lớp (kèm điểm & thời lượng riêng)."""

    training_class = models.ForeignKey(
        TrainingClass,
        on_delete=models.CASCADE,
        db_column="training_class_id",
        related_name="instructor_assignments",
    )
    instructor = models.ForeignKey(
        TrainingInstructor,
        on_delete=models.SET_NULL,
        db_column="instructor_id",
        related_name="class_assignments",
        null=True,
        blank=True,
    )

    ptct_record_info = models.CharField(max_length=255, null=True, blank=True)   # Thông tin GV của PTCT ghi nhận
    student_score = models.DecimalField(                                         # Điểm đánh giá của học viên (cho GV này)
        max_digits=3, decimal_places=2, null=True, blank=True
    )
    student_qll_avg_score = models.DecimalField(                                 # Điểm đánh giá TB của học viên và QLL
        max_digits=3, decimal_places=2, null=True, blank=True
    )
    duration_hours = models.DecimalField(                                        # Thời lượng (giờ) GV này dạy trong lớp
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    timeline_source = models.CharField(max_length=32, null=True, blank=True)     # Nguồn GV trên Timelines (I, O(VN)...)
    note = models.TextField(null=True, blank=True)                              # Ghi chú

    class Meta(NotSoftDeleteModel.Meta):
        db_table = "training_class_instructors"
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"TrainingClassInstructor#{self.pk} (class={self.training_class_id} gv={self.instructor_id})"
