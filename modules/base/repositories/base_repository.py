"""Base cho mọi Repository — bản Django của `BaseRepositoryV2` (Laravel).

Gộp luôn vai trò của contract `BaseInterfaceRepositoryV2`: bên Laravel tách
interface riêng để bind vào service-container (DI). Django không có container nên
một ABC vừa là contract vừa là implementation là đủ — không cần file interface riêng.

Khác biệt cố ý so với Laravel:
  - `model` ở đây là **class** (vd `Article`), không phải instance — vì Django dùng
    manager trên class (`Model.objects`) làm query factory.
  - `create()` không cần `forceFill` (Django không có mass-assignment guard); vẫn
    `refresh_from_db()` sau create/update để khớp `refresh()` (reload DB defaults).
"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from django.db import models

TModel = TypeVar("TModel", bound=models.Model)


class BaseRepository(Generic[TModel]):
    """Base repository generic theo model — clone `BaseRepositoryV2` + contract.

    Subclass khai báo model qua class attribute hoặc truyền vào `__init__`::

        class ArticleRepository(BaseRepository[Article]):
            model = Article

        # hoặc
        repo = BaseRepository(Article)
    """

    #: Model class mà repo thao tác. Subclass set, hoặc truyền vào __init__.
    model: type[TModel]

    def __init__(self, model: type[TModel] | None = None) -> None:
        if model is not None:
            self.model = model
        if getattr(self, "model", None) is None:
            raise ValueError(
                f"{type(self).__name__} cần khai báo `model` (class attribute) "
                f"hoặc truyền model class vào __init__()."
            )

    def query(self) -> "models.QuerySet[TModel]":
        """≈ `newQuery()`: QuerySet mới qua manager mặc định.

        Với `SoftDeleteModel`, manager mặc định đã loại row đã soft-delete —
        tương đương `SoftDeletingScope` của Laravel.
        """
        return self.model._default_manager.all()

    def find(self, id: int) -> Optional[TModel]:
        """≈ `find($id)`: trả instance theo primary key, hoặc `None`."""
        return self.query().filter(pk=id).first()

    def create(self, attributes: dict[str, Any]) -> TModel:
        """≈ `create()`: tạo, lưu, rồi reload từ DB."""
        instance = self.model(**attributes)
        instance.save()
        instance.refresh_from_db()
        return instance

    def update_model(self, instance: TModel, attributes: dict[str, Any]) -> TModel:
        """≈ `updateModel()`: set field + save (chỉ khi có attr) rồi reload."""
        if attributes:
            for field, value in attributes.items():
                setattr(instance, field, value)
            instance.save()
        instance.refresh_from_db()
        return instance

    def delete_model(self, instance: TModel) -> bool:
        """≈ `deleteModel()`: xoá instance (soft delete nếu model hỗ trợ)."""
        return self._deleted(instance.delete())

    def force_delete_model(self, instance: TModel) -> bool:
        """≈ `forceDeleteModel()`: xoá vật lý, bypass soft delete.

        Model có `hard_delete()` (SoftDeleteModel) thì gọi nó; còn lại `delete()`
        vốn đã là xoá vật lý.
        """
        hard_delete = getattr(instance, "hard_delete", None)
        result = hard_delete() if callable(hard_delete) else instance.delete()
        return self._deleted(result)

    @staticmethod
    def _deleted(result: Any) -> bool:
        """Chuẩn hoá kết quả delete về bool.

        `Model.delete()` thường trả `(count, {...})`; còn `SoftDeleteModel.delete()`
        (override) trả `None` — coi như đã xoá thành công.
        """
        if isinstance(result, tuple):
            return result[0] > 0
        return True
