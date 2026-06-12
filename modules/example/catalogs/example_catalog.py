"""ExampleCatalog — catalog chuỗi UI của module Example (demo quy ước catalog).

Chuỗi generic về field `name` ("Tên là bắt buộc"...) nằm ở
`modules.base.catalogs.CommonCatalog` (không gắn entity); ở đây chỉ giữ chuỗi
nêu đích danh entity Example.
"""

from __future__ import annotations

from modules.base.catalogs import LangCatalog


class ExampleCatalog(LangCatalog):
    """Key chuỗi UI của module Example — giá trị IN HOA để dễ đọc trong DB."""

    _NS = "EXAMPLE"

    NOT_FOUND = _NS + ".NOT_FOUND"
