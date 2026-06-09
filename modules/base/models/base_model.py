"""Gốc abstract cho mọi model — clone của `ModelV2`."""

from __future__ import annotations

from django.db import models

from .managers import BaseManager


class BaseModel(models.Model):
    """Gốc abstract cho mọi model module mới — clone của `ModelV2`.

    Cung cấp timestamps `created_at` / `updated_at` (Eloquent tự quản bên Laravel)
    và `BaseManager` với các scope tái sử dụng.

    Quy ước: model nghiệp vụ `extends` một trong hai lớp con (`SoftDeleteModel`
    hoặc `NotSoftDeleteModel`), KHÔNG kế thừa thẳng `BaseModel`.
    """

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
