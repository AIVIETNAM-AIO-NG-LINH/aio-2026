"""Transform `chatbot_documents` — clone của `Modules\\Chatbot\\Transformers\\V1\\DocumentTransformer`.

Bảng chỉ lưu `media_id` + `status` + `indexed_percent` — shape item cho API.
"""

from __future__ import annotations

from typing import Any

from modules.base.transformers import TransformerAbstract

from ..models import ChatbotDocument


class DocumentTransformer(TransformerAbstract):
    """Map 1 tài liệu chatbot → dict trả FE."""

    def transform(self, row: ChatbotDocument) -> dict[str, Any]:
        return {
            "id": row.id,
            "media_id": row.media_id,
            "status": row.status,
            "indexed_percent": int(row.indexed_percent),
            "created_at": row.fmt_dt(row.created_at),
            "updated_at": row.fmt_dt(row.updated_at),
        }
