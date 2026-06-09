"""
Base model hierarchy cho mọi module mới — bản Django tương đương 3 lớp
`ModelV2` / `BaseModelV2` / `BaseModelNotSoftDeletesV2` bên Laravel
(`Modules/Base/app/Models`).

Mirror cấu trúc nhiều file:
  - base_model.py            → BaseModel           (≈ ModelV2)
  - soft_delete_model.py     → SoftDeleteModel     (≈ BaseModelV2)
  - not_soft_delete_model.py → NotSoftDeleteModel  (≈ BaseModelNotSoftDeletesV2)
  - querysets.py / managers.py / helpers.py → scope & manager dùng chung

Import gọn từ ngoài: `from modules.base.models import SoftDeleteModel`.
"""

from .base_model import BaseModel
from .helpers import has_value
from .managers import BaseManager, SoftDeleteManager
from .not_soft_delete_model import NotSoftDeleteModel
from .querysets import BaseQuerySet, SoftDeleteQuerySet
from .soft_delete_model import SoftDeleteModel

__all__ = [
    "has_value",
    "BaseQuerySet",
    "SoftDeleteQuerySet",
    "BaseManager",
    "SoftDeleteManager",
    "BaseModel",
    "SoftDeleteModel",
    "NotSoftDeleteModel",
]
