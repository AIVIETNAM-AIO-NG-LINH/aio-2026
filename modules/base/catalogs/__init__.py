"""Catalogs của module Base — bản Django của `Modules\\Base\\Catalog` bên Laravel.

Export gọn: `from modules.base.catalogs import CommonCatalog`.
"""

from .common_catalog import CommonCatalog
from .lang_catalog import LangCatalog

__all__ = ["LangCatalog", "CommonCatalog"]
