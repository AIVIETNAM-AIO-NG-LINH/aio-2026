"""
Transformer layer — bản Django của `Modules/Base/app/Transformers` (league/fractal).

  - transformer_abstract.py → TransformerAbstract (≈ Fractal TransformerAbstract)
  - transformer_service.py  → TransformerService, Paginator (≈ TransformerService.php)

Import gọn: `from modules.base.app.transformers import TransformerService, TransformerAbstract`.
"""

from .transformer_abstract import (
    CollectionResource,
    ItemResource,
    NullResource,
    TransformerAbstract,
)
from .transformer_service import Paginator, TransformerService

__all__ = [
    "TransformerAbstract",
    "TransformerService",
    "Paginator",
    "ItemResource",
    "CollectionResource",
    "NullResource",
]
