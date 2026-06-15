"""Công cụ (tools) cho chatbot — khối "làm việc" được agent/endpoint gọi tới.

Hiện có `knowledge_base.search()`: truy hồi chunk (embed → hybrid → rerank),
KHÔNG sinh câu trả lời LLM. Là tool RAG cho ADK agent (qua `adk/tools.py`
bọc thành `search_knowledge_base`). Mỗi tool là function thuần, tách khỏi
`services/` (orchestration) vì là công cụ độc lập, dùng lại nhiều nơi.
"""

from . import knowledge_base

__all__ = ["knowledge_base"]
