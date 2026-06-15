"""Transform `chat_messages` — shape item cho API list tin nhắn của 1 hội thoại."""

from __future__ import annotations

from typing import Any

from modules.base.transformers import TransformerAbstract

from ..models import ChatMessage


class MessageTransformer(TransformerAbstract):
    """Map 1 tin nhắn → dict trả FE (datetime format V1 qua `fmt_dt` của model)."""

    def transform(self, row: ChatMessage) -> dict[str, Any]:
        return {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "citations": row.citations,
            "status": row.status,
            "created_at": row.fmt_dt(row.created_at),
        }
