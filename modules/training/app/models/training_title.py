"""Model `TrainingTitle` — chức danh của học viên.

Tách từ cột "Chức danh" của `Output_1_Data_hv_Cleaned.csv` (57 giá trị, vd
"Cán bộ", "Trưởng Phòng thuộc Chi nhánh"). Tập đóng, low-cardinality, lặp nhiều
(~1.407 dòng/giá trị) và là CHIỀU PHÂN TÍCH cốt lõi (câu hỏi "bao nhiêu cán bộ
quản lý được đào tạo" = gom theo chức danh) → chuẩn hóa ra bảng riêng để filter/
gom gọn và phục vụ entity-resolution.

Chức danh là snapshot lúc học (đổi theo thời gian) nên FK nằm ở
`TrainingClassStudent`, không ở `TrainingStudent`.
"""

from __future__ import annotations

from django.db import models

from modules.base.models import NotSoftDeleteModel


class TrainingTitle(NotSoftDeleteModel):
    """Một chức danh — định danh theo tên (duy nhất)."""

    name = models.CharField(max_length=255, unique=True)   # "Cán bộ", "Trưởng Phòng thuộc Chi nhánh" (nguyên văn)

    class Meta(NotSoftDeleteModel.Meta):
        db_table = "training_titles"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"TrainingTitle#{self.pk} ({self.name})"
