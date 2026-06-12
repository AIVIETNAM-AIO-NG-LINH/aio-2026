"""TransformerAbstract — bản Django của `League\\Fractal\\TransformerAbstract`.

Transformer là "công thức" map 1 model/object → dict trả cho FE (tách shape
response khỏi service/repository). Subclass bắt buộc override `transform()`.

Quan hệ lồng (includes) khai báo qua 2 class attribute:
  - `default_includes`:   luôn nest (≈ `$defaultIncludes`).
  - `available_includes`: chỉ nest khi caller yêu cầu qua tham số `includes`
                          của TransformerService (≈ `$availableIncludes`).

Mỗi tên `x` trong 2 danh sách trên cần method `include_x(obj)` trả về
`self.item(...)` / `self.collection(...)` / `self.null()` — mirror cách viết
`includeMedia()` bên Fractal::

    class DocumentTransformer(TransformerAbstract):
        default_includes = ("media",)

        def transform(self, row) -> dict:
            return {"id": row.id, "media_id": row.media_id}

        def include_media(self, row):
            return self.item(row.media, MediaTransformer()) if row.media else self.null()

Includes lồng sâu dùng dấu chấm như Fractal: `includes=["media", "media.user"]`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


class Resource:
    """Đánh dấu giá trị trả về của `include_*()` — Item/Collection/Null."""


@dataclass(frozen=True)
class ItemResource(Resource):
    """Quan hệ 1-1 / belongs-to — serialize thành dict."""

    data: Any
    transformer: "TransformerAbstract"


@dataclass(frozen=True)
class CollectionResource(Resource):
    """Quan hệ 1-n — serialize thành list[dict]."""

    data: Iterable[Any]
    transformer: "TransformerAbstract"


class NullResource(Resource):
    """Quan hệ rỗng — serialize thành `None` (≈ `$this->null()`)."""


class TransformerAbstract:
    """Base cho mọi transformer — chỉ dùng qua subclass (override `transform`)."""

    #: Includes LUÔN nest, không cần caller yêu cầu (≈ `$defaultIncludes`).
    default_includes: tuple[str, ...] = ()
    #: Includes nest KHI caller yêu cầu (≈ `$availableIncludes`).
    available_includes: tuple[str, ...] = ()

    def transform(self, obj: Any) -> dict[str, Any]:
        """Map 1 object → dict. Subclass bắt buộc override."""
        raise NotImplementedError(
            f"{type(self).__name__} phải override transform(obj) -> dict."
        )

    # --- Sugar tạo resource trong include_*() (≈ $this->item()/collection()/null()) --
    def item(self, data: Any, transformer: "TransformerAbstract") -> ItemResource:
        """Nest 1 object con qua transformer của nó."""
        return ItemResource(data, transformer)

    def collection(
        self, data: Iterable[Any], transformer: "TransformerAbstract"
    ) -> CollectionResource:
        """Nest danh sách object con qua transformer của chúng."""
        return CollectionResource(data, transformer)

    def null(self) -> NullResource:
        """Quan hệ không có dữ liệu → field nhận `None`."""
        return NullResource()
