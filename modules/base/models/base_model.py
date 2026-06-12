"""Gốc abstract cho mọi model — clone của `ModelV2`."""

from __future__ import annotations

from django.db import models

from . import helpers
from .managers import BaseManager


class BaseModel(models.Model):
    """Gốc abstract cho mọi model module mới — clone của `ModelV2`.

    Cung cấp timestamps `created_at` / `updated_at` (Eloquent tự quản bên Laravel)
    và `BaseManager` với các scope tái sử dụng.

    Quy ước: model nghiệp vụ `extends` một trong hai lớp con (`SoftDeleteModel`
    hoặc `NotSoftDeleteModel`), KHÔNG kế thừa thẳng `BaseModel`.
    """

    # Khai báo pk TƯỜNG MINH để static checker (Pylance) thấy được `.id` — Django
    # vốn thêm field này lúc runtime qua metaclass nên IDE báo "Cannot access
    # attribute". Kwargs phải TRÙNG KHỚP field auto-created (xem 0001_initial của
    # các app) để makemigrations không sinh AlterField vô nghĩa.
    id = models.BigAutoField(
        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BaseManager()

    class Meta:
        abstract = True
        ordering = ["-id"]

    @classmethod
    def get_table_name(cls) -> str:
        """≈ `ModelV2::getTableName()` — trả về tên bảng thật trong DB."""
        return cls._meta.db_table

    # ≈ `ModelV2::serializeDate()` — mọi model format datetime ra shape V1
    # qua `obj.fmt_dt(obj.created_at)` (hoặc import trực tiếp từ helpers).
    fmt_dt = staticmethod(helpers.fmt_dt)
