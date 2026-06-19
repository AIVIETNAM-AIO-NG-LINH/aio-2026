"""Model `TrainingStaff` — nhân sự phòng đào tạo (quản lý lớp / LĐP QLĐT).

Tách từ 2 cột text của `Data_Khoa_Hoc_Clean.csv`: "Quản lý lớp" và "LĐP QLĐT".
Cả hai đều là TÊN NGƯỜI nên gom về một bảng người dùng chung, `TrainingClass`
chỉ tham chiếu (lưu id) thay vì lặp chuỗi tên.

Vai trò không cố định theo người: phân biệt vai (quản lý lớp vs LĐP) thể hiện qua
QUAN HỆ ở `TrainingClass` (`training_dept_leader` FK, `class_managers` M2M), không
lưu cờ vai trò trên bản ghi người này.
"""

from __future__ import annotations

from django.db import models

from modules.base.models import NotSoftDeleteModel


class TrainingStaff(NotSoftDeleteModel):
    """Một nhân sự đào tạo — định danh theo tên (duy nhất)."""

    name = models.CharField(max_length=128, unique=True)  # Họ tên

    class Meta(NotSoftDeleteModel.Meta):
        db_table = "training_staff"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"TrainingStaff#{self.pk} ({self.name})"
