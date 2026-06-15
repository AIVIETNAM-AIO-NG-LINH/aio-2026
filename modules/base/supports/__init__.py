"""Supports của module Base — bản Django của `Modules\\*\\Support` bên Laravel.

Export gọn: `from modules.base.supports import translate`.
"""

from .pagination_helper import parse_pagination
from .translate_helper import translate, translate_lazy

__all__ = ["parse_pagination", "translate", "translate_lazy"]
