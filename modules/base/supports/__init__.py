"""Supports của module Base — bản Django của `Modules\\*\\Support` bên Laravel.

Export gọn: `from modules.base.supports import translate`.
"""

from .translate_helper import translate, translate_lazy

__all__ = ["translate", "translate_lazy"]
