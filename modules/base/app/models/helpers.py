"""Tiện ích nhỏ dùng chung cho base models."""

from __future__ import annotations


def fmt_dt(value) -> str | None:
    """Tương đương `ModelV2::serializeDate` — datetime → 'Y-m-d H:i:s' (DATETIME_FORMAT V1).

    Laravel format tự động khi serialize model; Django build dict thủ công nên
    transformer/service gọi helper này cho mọi field datetime. None giữ None.
    """
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def has_value(value) -> bool:
    """Tương đương `ModelV2::checkWhenQuery` — chỉ apply filter khi value có ý nghĩa.

    None và các collection/string rỗng được coi là "không có giá trị" nên bỏ qua,
    để tránh `WHERE field IN ()` luôn rỗng.
    """
    if value is None:
        return False
    if isinstance(value, (list, tuple, set, dict, str)) and len(value) == 0:
        return False
    return True
