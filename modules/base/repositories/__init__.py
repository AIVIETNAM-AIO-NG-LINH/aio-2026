"""
Repository layer cho module mới — bản Django của `Modules/Base/app/Repositories`.

  - base_repository.py → BaseRepository  (≈ BaseRepositoryV2 + BaseInterfaceRepositoryV2)

Import gọn: `from modules.base.repositories import BaseRepository`.
"""

from .base_repository import BaseRepository

__all__ = ["BaseRepository"]
