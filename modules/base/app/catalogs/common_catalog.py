"""CommonCatalog — bản Django của `Modules\\Base\\Catalog\\CommonCatalog`.

Catalog chuỗi UI **generic dùng chung** (NS `COMMON`) — CHỈ chứa chuỗi không gắn
entity cụ thể (kết quả thao tác, validation chung, auth chung). Chuỗi nêu tên
entity/field cụ thể để ở catalog của module sở hữu (vd ChatbotCatalog) — module
khác cần thì import catalog đó.
"""

from __future__ import annotations

from .lang_catalog import LangCatalog


class CommonCatalog(LangCatalog):
    """Key chuỗi dùng chung toàn hệ thống. Tên hằng mirror bản Laravel khi trùng chuỗi."""

    # Namespace dùng chung — giá trị IN HOA để dễ đọc trong DB.
    _NS = "COMMON"

    FORBIDDEN = _NS + ".FORBIDDEN"
    INVALID_DATA = _NS + ".INVALID_DATA"
    NAME_BLANK = _NS + ".NAME_BLANK"
    NAME_MAX_255 = _NS + ".NAME_MAX_255"
    NAME_REQUIRED = _NS + ".NAME_REQUIRED"
    NAME_TAKEN = _NS + ".NAME_TAKEN"
    UNAUTHENTICATED = _NS + ".UNAUTHENTICATED"
