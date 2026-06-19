"""Model `TrainingBranch` — chi nhánh tính KPI của học viên.

Tách từ cột "Chi nhánh tính KPI" của `Output_1_Data_hv_Cleaned.csv` (131 chi
nhánh, vd "VCB Ba Đình"). Ổn định tuyệt đối theo người (0/18.622 mã cán bộ đổi
chi nhánh) → là dimension dùng chung, chuẩn hóa ra bảng riêng để
`TrainingStudent` chỉ giữ FK, tránh lặp chuỗi và query/gom theo chi nhánh dễ.
"""

from __future__ import annotations

from django.db import models

from modules.base.models import NotSoftDeleteModel


class TrainingBranch(NotSoftDeleteModel):
    """Một chi nhánh tính KPI — định danh theo tên (duy nhất)."""

    name = models.CharField(max_length=255, unique=True)   # "VCB Ba Đình" (nguyên văn)

    class Meta(NotSoftDeleteModel.Meta):
        db_table = "training_branches"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"TrainingBranch#{self.pk} ({self.name})"
