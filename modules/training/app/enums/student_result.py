"""Kết quả học viên — lưu ở `training_class_students.result`.

Cột "Đạt/Không đạt" của `Output_1_Data_hv_Cleaned.csv`: 2 giá trị sạch, có ở
100% dòng → enum hóa. Dùng `TextChoices`, lưu thẳng chuỗi tiếng Việt khớp nguồn.
"""

from __future__ import annotations

from django.db import models


class StudentResult(models.TextChoices):
    """Học viên đạt hay không đạt lớp đào tạo."""

    PASS = "Đạt", "Đạt"
    FAIL = "Không đạt", "Không đạt"
