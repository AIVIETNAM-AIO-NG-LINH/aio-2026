"""Transform `chat_conversations` — shape item cho API list hội thoại."""

from __future__ import annotations

from typing import Any

from modules.base.transformers import TransformerAbstract

from ..models import ChatConversation


class ConversationTransformer(TransformerAbstract):
    """Map 1 hội thoại → dict trả FE (datetime format V1 qua `fmt_dt` của model)."""

    def transform(self, row: ChatConversation) -> dict[str, Any]:
        return {
            "id": row.id,
            "title": row.title,
            "status": row.status,
            "created_at": row.fmt_dt(row.created_at),
            "updated_at": row.fmt_dt(row.updated_at),
        }
