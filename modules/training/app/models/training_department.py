"""Model `TrainingDepartment` — phòng/trung tâm thuộc một chi nhánh (cây tổ chức).

Tách từ cột "Phòng/Trung tâm" của `Output_1_Data_hv_Cleaned.csv`. Tên phòng KHÔNG
duy nhất toàn hệ thống: 1 tên như "Kế toán" xuất hiện ở 125 chi nhánh khác nhau
(tổng 704 tên → 1.841 cặp (chi nhánh, phòng)). Vì vậy mỗi phòng được định danh
bằng CẶP `(branch, name)` — "Kế toán @ Ba Đình" khác "Kế toán @ An Giang".

Khác `TrainingBranch`/`TrainingTitle` (key theo tên đơn) ở chỗ phải có `branch`
để khử nhập nhằng. Lúc import: resolve `branch` trước, rồi
`get_or_create(branch=..., name=...)`.
"""

from __future__ import annotations

from django.db import models

from modules.base.models import NotSoftDeleteModel

from .training_branch import TrainingBranch


class TrainingDepartment(NotSoftDeleteModel):
    """Một phòng/trung tâm thuộc đúng một chi nhánh — định danh theo (chi nhánh, tên)."""

    branch = models.ForeignKey(                                # Chi nhánh chứa phòng này
        TrainingBranch,
        on_delete=models.CASCADE,
        db_column="branch_id",
        related_name="departments",
    )
    name = models.CharField(max_length=255)                    # "Kế toán", "Ban Giám đốc" (nguyên văn)

    class Meta(NotSoftDeleteModel.Meta):
        db_table = "training_departments"
        ordering = ["name"]
        unique_together = ("branch", "name")

    def __str__(self) -> str:
        return f"TrainingDepartment#{self.pk} ({self.name} @ branch={self.branch_id})"
