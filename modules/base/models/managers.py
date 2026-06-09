"""Manager cho base models."""

from __future__ import annotations

from django.db import models

from .querysets import BaseQuerySet, SoftDeleteQuerySet


class BaseManager(models.Manager.from_queryset(BaseQuerySet)):
    """Manager mặc định, expose toàn bộ helper của `BaseQuerySet`."""


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Manager soft delete.

    `with_trashed=False` (mặc định): tự lọc bỏ row đã xoá — tương đương global
    scope `SoftDeletingScope` của Laravel. `with_trashed=True`: trả về tất cả
    (dùng cho manager `all_objects`, ≈ `withTrashed()`).
    """

    def __init__(self, *args, with_trashed: bool = False, **kwargs):
        self._with_trashed = with_trashed
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        if self._with_trashed:
            return qs
        return qs.filter(deleted_at__isnull=True)
