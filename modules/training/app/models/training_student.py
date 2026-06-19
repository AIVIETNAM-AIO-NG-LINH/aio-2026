"""Model `TrainingStudent` — một HỌC VIÊN (dimension người học).

Nguồn: file `Output_1_Data_hv_Cleaned.csv` (80.173 dòng đăng ký học). Một học
viên học nhiều lớp → tách dimension người ra khỏi bảng nối
`TrainingClassStudent` (nơi giữ điểm/kết quả theo từng lần học).

Định danh SẠCH (khác hẳn giảng viên): `Mã cán bộ` có ở 100% dòng và là khóa
ổn định — `employee_code` đặt `unique`. Tên có lệch nhẹ (158/18.622 mã ↔ >1 tên,
chủ yếu typo) nhưng chỉ là thuộc tính hiển thị, không dùng làm khóa.

`Chi nhánh tính KPI` ổn định theo người (0/18.622 mã đổi chi nhánh) nên đặt ở
đây; còn `Phòng/Trung tâm` và `Chức danh` THAY ĐỔI theo thời gian → là snapshot
lúc học, nằm ở `TrainingClassStudent`, không ở dimension này.
"""

from __future__ import annotations

from django.db import models

from modules.base.models import NotSoftDeleteModel

from .training_branch import TrainingBranch


class TrainingStudent(NotSoftDeleteModel):
    """Một học viên — định danh theo mã cán bộ (duy nhất)."""

    employee_code = models.CharField(max_length=32, unique=True)              # Mã cán bộ — KHÓA định danh
    name = models.CharField(max_length=255, db_index=True)                   # Họ tên học viên
    kpi_branch = models.ForeignKey(                                          # Chi nhánh tính KPI → training_branches
        TrainingBranch,
        on_delete=models.SET_NULL,
        db_column="kpi_branch_id",
        related_name="students",
        null=True,
        blank=True,
    )

    class Meta(NotSoftDeleteModel.Meta):
        db_table = "training_students"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"TrainingStudent#{self.pk} ({self.employee_code} - {self.name})"
