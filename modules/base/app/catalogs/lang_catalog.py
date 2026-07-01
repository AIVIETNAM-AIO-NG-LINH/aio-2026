"""LangCatalog — bản Django của `Modules\\Base\\Catalog\\LangCatalog`.

Lớp cơ sở cho catalog khai báo **hằng key** chuỗi UI của 1 feature/module.

Mỗi catalog là 1 lớp con khai báo các hằng `namespace.name` (namespace khai báo
thẳng ở hằng `_NS` trong chính catalog) để call-site gọi
`translate("Text", MyCatalog.KEY)`. Giá trị key IN HOA (vd `CHATBOT.NOT_FOUND`)
cho dễ đọc khi lưu DB. Catalog dùng chung toàn hệ thống: `CommonCatalog`.
"""

from __future__ import annotations


class LangCatalog:
    """Base catalog — chỉ để các catalog kế thừa, không chứa key."""
