"""Base model KHÔNG soft delete — clone của `BaseModelNotSoftDeletesV2`."""

from __future__ import annotations

from .base_model import BaseModel


class NotSoftDeleteModel(BaseModel):
    """Base model KHÔNG soft delete — clone của `BaseModelNotSoftDeletesV2`.

    Dùng cho model dạng pivot/catalog không có cột `deleted_at`. Hiện chỉ là alias
    rõ nghĩa của `BaseModel`, tách riêng để callsite thể hiện ý định và để sau này
    nới rộng độc lập với nhánh soft delete.
    """

    class Meta(BaseModel.Meta):
        abstract = True
