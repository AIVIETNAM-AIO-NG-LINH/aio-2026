"""Base model CÓ soft delete — clone của `BaseModelV2`."""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from .base_model import BaseModel
from .managers import SoftDeleteManager


class SoftDeleteModel(BaseModel):
    """Base model CÓ soft delete — clone của `BaseModelV2` (`ModelV2` + SoftDeletes).

    Model nào cần soft delete thì `extends SoftDeleteModel`; cột `deleted_at`,
    manager lọc sẵn và các method delete/restore đã có ở đây.

      - `Model.objects`     → chỉ row chưa xoá (mặc định)
      - `Model.all_objects` → gồm cả row đã soft-delete (≈ withTrashed)
      - `obj.delete()`      → soft delete; `obj.hard_delete()` → xoá thật
    """

    deleted_at = models.DateTimeField(null=True, blank=True, default=None, db_index=True)

    objects = SoftDeleteManager()
    all_objects = SoftDeleteManager(with_trashed=True)

    class Meta(BaseModel.Meta):
        abstract = True

    def delete(self, using=None, keep_parents=False):
        """Soft delete: set `deleted_at` thay vì xoá row."""
        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=["deleted_at", "updated_at"])

    def hard_delete(self, using=None, keep_parents=False):
        """Xoá vật lý thật sự (bypass soft delete)."""
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self, using=None):
        """Khôi phục row đã soft-delete."""
        self.deleted_at = None
        self.save(using=using, update_fields=["deleted_at", "updated_at"])

    @property
    def is_trashed(self) -> bool:
        return self.deleted_at is not None
