"""TransformerService — bản Django của `Modules/Base/app/Transformers/TransformerService.php`.

Entry-point tĩnh để transform model → dict qua transformer (port từ league/fractal):
  - item()                  — 1 object → dict (unwrap, không bọc `data`).
  - collection()            — list object → `{"data": [...]}` (+ `meta` nếu có).
  - paginator()             — Paginator → `{"data": [...], "meta": {"pagination": ...}}`.
  - make_paginator()        — dựng Paginator từ `(total, items)` của repository.
  - make_paginator_hollow() — Paginator rỗng (vd quyền không cho xem → trang trắng).

Khác bản PHP (cố ý):
  - Không có Manager singleton — mỗi lần gọi là stateless nên không có chuyện
    "dính" includes giữa 2 lần transform (lý do PHP phải parseIncludes lại mỗi lần).
  - Include lồng KHÔNG bọc thêm `{"data": ...}` quanh từng quan hệ như
    DataArraySerializer của Fractal — nest thẳng dict/list cho FE đỡ bóc.
  - `paginator()` nhận `Paginator` tự chế (Django không có LengthAwarePaginator);
    meta giữ nguyên shape Fractal + `next_page` (đã bỏ `links` như bản PHP).

Dùng trong service (kết hợp `BaseService.response_success`)::

    total, rows = self.repo.paginate_for_user(user_id, page, limit)
    data = TransformerService.paginator(
        TransformerService.make_paginator(rows, total, limit, page),
        ConversationTransformer(),
    )
    return self.response_success(data)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

from .transformer_abstract import (
    CollectionResource,
    ItemResource,
    NullResource,
    Resource,
    TransformerAbstract,
)


@dataclass(frozen=True)
class Paginator:
    """≈ `LengthAwarePaginator`: items của trang hiện tại + tổng số để tính meta."""

    items: Sequence[Any]
    total: int
    limit: int
    current_page: int

    @property
    def total_pages(self) -> int:
        """≈ `lastPage()`: tối thiểu 1 (kể cả khi rỗng) — khớp Laravel."""
        if self.limit <= 0:
            return 1
        return max(math.ceil(self.total / self.limit), 1)

    @property
    def next_page(self) -> int | None:
        """Trang kế tiếp, `None` nếu đã ở trang cuối (helper bản PHP thêm vào)."""
        return None if self.current_page >= self.total_pages else self.current_page + 1


class TransformerService:
    """Static service — gọi thẳng `TransformerService.item(...)` như bản PHP."""

    @staticmethod
    def item(
        item: Any,
        transformer: TransformerAbstract,
        includes: Sequence[str] = (),
    ) -> dict[str, Any]:
        """Transform 1 object → dict (≈ `item()`, đã unwrap khỏi key `data`)."""
        return _transform_obj(item, transformer, _parse_includes(includes))

    @staticmethod
    def collection(
        items: Iterable[Any],
        transformer: TransformerAbstract,
        includes: Sequence[str] = (),
        meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Transform danh sách → `{"data": [...]}`, thêm `meta` nếu truyền vào."""
        parsed = _parse_includes(includes)
        result: dict[str, Any] = {
            "data": [_transform_obj(o, transformer, parsed) for o in items]
        }
        if meta:
            result["meta"] = meta
        return result

    @staticmethod
    def paginator(
        paginator: Paginator,
        transformer: TransformerAbstract,
        includes: Sequence[str] = (),
        meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Transform trang dữ liệu → `{"data": [...], "meta": {"pagination": ...}}`."""
        parsed = _parse_includes(includes)
        data = [_transform_obj(o, transformer, parsed) for o in paginator.items]
        pagination = {
            "total": paginator.total,
            "count": len(data),
            "per_page": paginator.limit,
            "current_page": paginator.current_page,
            "total_pages": paginator.total_pages,
            "next_page": paginator.next_page,
        }
        return {"data": data, "meta": {**(meta or {}), "pagination": pagination}}

    @staticmethod
    def make_paginator(
        items: Optional[Iterable[Any]] = None,
        total: int = 0,
        limit: int = 10,
        current_page: int = 1,
    ) -> Paginator:
        """Dựng Paginator từ `(total, items)` mà các repository đang trả về."""
        rows = list(items) if (items is not None and total > 0) else []
        return Paginator(rows, total, limit, current_page)

    @staticmethod
    def make_paginator_hollow(limit: int = 10, current_page: int = 1) -> Paginator:
        """Paginator rỗng — giữ nguyên shape pagination khi không có gì để trả."""
        return Paginator([], 0, limit, current_page)


# --- Nội bộ: serialize đệ quy (vai trò Manager + DataArraySerializer) ----------
def _parse_includes(includes: Sequence[str]) -> list[str]:
    """Lọc chuỗi rỗng/khoảng trắng (mirror `parseIncludes` bản PHP)."""
    return [i.strip() for i in includes if isinstance(i, str) and i.strip()]


def _transform_obj(
    obj: Any, transformer: TransformerAbstract, includes: list[str]
) -> dict[str, Any]:
    """transform() + nest các include đang active (default ∪ được yêu cầu)."""
    data = transformer.transform(obj)

    requested = {i.split(".", 1)[0] for i in includes}
    active = list(transformer.default_includes) + [
        name
        for name in transformer.available_includes
        if name in requested and name not in transformer.default_includes
    ]
    for name in active:
        method = getattr(transformer, f"include_{name}", None)
        if not callable(method):
            raise RuntimeError(
                f"{type(transformer).__name__} khai báo include '{name}' "
                f"nhưng thiếu method include_{name}(obj)."
            )
        # Includes lồng sâu: "media.user" → transformer của media nhận ["user"].
        child = [i.split(".", 1)[1] for i in includes if i.startswith(f"{name}.")]
        data[name] = _serialize_resource(method(obj), child)
    return data


def _serialize_resource(resource: Resource, includes: list[str]) -> Any:
    """Item → dict, Collection → list[dict], Null/None → None."""
    if resource is None or isinstance(resource, NullResource):
        return None
    if isinstance(resource, ItemResource):
        return _transform_obj(resource.data, resource.transformer, includes)
    if isinstance(resource, CollectionResource):
        return [
            _transform_obj(o, resource.transformer, includes) for o in resource.data
        ]
    raise TypeError(
        "include_*() phải trả về self.item()/self.collection()/self.null(), "
        f"nhận được: {type(resource).__name__}."
    )
