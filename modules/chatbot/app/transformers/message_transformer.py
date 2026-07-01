"""Transform `chat_messages` — shape item cho API list tin nhắn của 1 hội thoại."""

from __future__ import annotations

from typing import Any

from modules.base.app.transformers import TransformerAbstract

from ..models import ChatMessage


class MessageTransformer(TransformerAbstract):
    """Map 1 tin nhắn → dict trả FE (datetime format V1 qua `fmt_dt` của model)."""

    def transform(self, row: ChatMessage) -> dict[str, Any]:
        return {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            # Suy nghĩ (reasoning) để FE dựng lại khối thinking; "" nếu không có.
            "reasoning": row.reasoning or "",
            "citations": row.citations,
            # Sơ đồ tư duy (mind map) — null nếu lượt này không vẽ; FE render bằng markmap.
            "mind_map": row.mind_map,
            "status": row.status,
            "created_at": row.fmt_dt(row.created_at),
        }
