"""Tiện ích nhỏ dùng chung cho base models."""

from __future__ import annotations


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
