"""Nguồn giảng viên — lưu ở `training_instructors.source`.

Cột "Nguồn GV" của `Data_Giang_Vien_Clean.csv`: 7 giá trị, SẠCH và ỔN ĐỊNH theo
mã giảng viên (0/409 mã GV có >1 nguồn) nên đủ điều kiện làm enum. Dùng
`TextChoices`, lưu thẳng chuỗi tiếng Việt khớp dữ liệu nguồn.
"""

from __future__ import annotations

from django.db import models


class InstructorSource(models.TextChoices):
    """Giảng viên đến từ đâu (nội bộ, thuê ngoài, khách mời...)."""

    INTERNAL = "GVNB", "GVNB"                       # giảng viên nội bộ
    OUTSOURCED = "Thuê ngoài", "Thuê ngoài"
    SENT_TO_STUDY = "Lớp cử đi học", "Lớp cử đi học"
    VCB_EXAMINER = "Giám khảo VCB", "Giám khảo VCB"
    GUEST = "Khách mời", "Khách mời"
    MATERIAL_AUTHOR = "Biên soạn TL", "Biên soạn TL"
    TEAMBUILDING = "Teambuilding", "Teambuilding"
