"""Trạng thái 'Cam kết đào tạo' — lưu ở `training_classes.training_commitment`.

Tách riêng khỏi `TestStatus` để mỗi cột tiến hóa độc lập (giá trị tương lai của
'Cam kết đào tạo' không nhất thiết giống 'Bài kiểm tra'). Dùng `TextChoices`,
lưu thẳng chuỗi tiếng Việt khớp dữ liệu nguồn.
"""

from __future__ import annotations

from django.db import models


class CommitmentStatus(models.TextChoices):
    """Lớp có yêu cầu cam kết đào tạo hay không."""

    YES = "Có", "Có"
    NO = "Không", "Không"
