"""Trạng thái 'Bài kiểm tra' của lớp — lưu ở `training_classes.has_test`.

Dùng `TextChoices` (không phải BooleanField) để còn mở rộng — sau này nếu phát
sinh giá trị khác chỉ thêm thành viên, không phải migrate đổi kiểu cột. Lưu thẳng
chuỗi tiếng Việt khớp dữ liệu nguồn.
"""

from __future__ import annotations

from django.db import models


class TestStatus(models.TextChoices):
    """Lớp có bài kiểm tra hay không."""

    YES = "Có", "Có"
    NO = "Không", "Không"
