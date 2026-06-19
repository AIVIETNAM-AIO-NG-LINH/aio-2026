"""Model `TrainingPeriod` — kỳ ghi nhận/báo cáo đào tạo.

Tách từ cột "KỲ GHI NHẬN" của `Data_Khoa_Hoc_Clean.csv` (24 kỳ, dạng chu kỳ
~nửa tháng "Từ 20/04-19/05"). Tách bảng riêng để CÒN QUERY theo thời gian:
text thuần không sort được theo trình tự kỳ, nên parse ra `start_date`/`end_date`
(DateField) để xếp/so sánh giữa các kỳ bằng ngày thật.

Chuỗi kỳ KHÔNG có năm — điền năm hiện tại lúc import. Giá trị đặc biệt
"Không tính khóa" không phải khoảng ngày → `start_date`/`end_date` để NULL
(nhận biết "không tính" qua `start_date IS NULL`).
"""

from __future__ import annotations

from django.db import models

from modules.base.models import NotSoftDeleteModel


class TrainingPeriod(NotSoftDeleteModel):
    """Một kỳ ghi nhận đào tạo — định danh theo tên (duy nhất)."""

    name = models.CharField(max_length=64, unique=True)            # "Từ 20/04-19/05" (nguyên văn)
    start_date = models.DateField(null=True, blank=True)           # ngày bắt đầu kỳ (parse từ name; năm thiếu → năm hiện tại)
    end_date = models.DateField(null=True, blank=True)             # ngày kết thúc kỳ (parse như start_date; năm thiếu → năm hiện tại)

    class Meta(NotSoftDeleteModel.Meta):
        db_table = "training_periods"
        ordering = ["start_date"]

    def __str__(self) -> str:
        return f"TrainingPeriod#{self.pk} ({self.name})"
