"""QuerySet tái sử dụng — clone các `#[Scope]` của `ModelV2` / `BaseModelV2`."""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from .helpers import has_value


class BaseQuerySet(models.QuerySet):
    """Các scope tái sử dụng — clone các `#[Scope]` của `ModelV2`."""

    def when(self, field: str, value):
        """≈ scope `whenQuery`: chỉ thêm điều kiện khi value có giá trị.

        Truyền list/tuple/set thì dùng `field__in`, còn lại dùng so sánh bằng.
        """
        if not has_value(value):
            return self
        if isinstance(value, (list, tuple, set)):
            return self.filter(**{f"{field}__in": value})
        return self.filter(**{field: value})

    def when_many(self, filters: dict | None):
        """≈ scope `whenQueryArray`: apply nhiều cặp field=value, bỏ value rỗng."""
        qs = self
        for field, value in (filters or {}).items():
            qs = qs.when(field, value)
        return qs

    def order_by_id_desc(self):
        """≈ scope `orderByCreatedAtDesc` (order theo id desc)."""
        return self.order_by("-id")

    def order_by_id_asc(self):
        """≈ scope `orderByCreatedAtAsc` (order theo id asc)."""
        return self.order_by("id")

    def order_by_updated_desc(self):
        """≈ scope `orderByUpdatedAtDesc`."""
        return self.order_by("-updated_at")


class SoftDeleteQuerySet(BaseQuerySet):
    """QuerySet hỗ trợ soft delete — `delete()` set `deleted_at` thay vì xoá thật."""

    def delete(self):
        """Soft delete hàng loạt: set `deleted_at = now()`."""
        return self.update(deleted_at=timezone.now())

    def hard_delete(self):
        """Xoá vật lý thật sự (bypass soft delete)."""
        return super().delete()

    def restore(self):
        """Khôi phục hàng loạt row đã soft-delete."""
        return self.update(deleted_at=None)

    def alive(self):
        """Chỉ row chưa xoá."""
        return self.filter(deleted_at__isnull=True)

    def trashed(self):
        """Chỉ row đã soft-delete."""
        return self.filter(deleted_at__isnull=False)
