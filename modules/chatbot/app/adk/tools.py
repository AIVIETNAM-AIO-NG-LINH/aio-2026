"""Tool RAG cho ADK agent — bọc `tools.knowledge_base.search()`.

ADK tự sinh schema tool từ chữ ký + docstring của hàm, nên docstring viết rõ ràng
(tiếng Anh) để model biết khi nào gọi. Hàm trả về DICT cố định `{"results": [...]}`
để `function_response` trong stream có shape ổn định (dễ trích citations).
"""

from __future__ import annotations

import logging
from typing import Any

from ..chat_pipeline.config import ChatConfig

logger = logging.getLogger(__name__)

# Default top_k = CHAT_CONTEXT_TOP_K (đọc 1 lần lúc nạp module). Agent vẫn có thể
# truyền top_k khác khi gọi tool.
_DEFAULT_TOP_K = ChatConfig.from_env().context_top_k


def search_knowledge_base(query: str, top_k: int = _DEFAULT_TOP_K) -> dict[str, Any]:
    """Search the internal document knowledge base for passages relevant to a query.

    Use this whenever the user asks anything that may be answered by the organization's
    documents (policies, processes, products, reports, etc.). Returns the most relevant
    text passages, each with its source document name and page number for citation.

    Args:
        query: The natural-language search query (use the user's wording or a refined version).
        top_k: Maximum number of passages to return (default 5).

    Returns:
        A dict with key "results": a list of passages, each having `chunk_text`, `score`,
        `document_id`, `media_id`, `original_name`, and `page`. An empty list means no
        relevant document was found.
    """
    # Import trong hàm để tránh phụ thuộc vòng lúc nạp module agent.
    from modules.chatbot.app.tools import knowledge_base

    try:
        chunks = knowledge_base.search(query, top_k=top_k)
    except Exception:
        logger.exception("[adk-tool] search_knowledge_base lỗi (trả rỗng)")
        return {"results": []}

    logger.info("[adk-tool] search_knowledge_base query=%r → %d kết quả", query, len(chunks))
    return {"results": chunks}


def search_knowledge_graph(query: str) -> dict[str, Any]:
    """Search the knowledge graph for entities and the relationships between them.

    Use this when a question is about HOW things relate — connections, dependencies,
    causes, comparisons across multiple documents, or multi-hop reasoning (e.g. "how
    does X affect Y", "what links A to B") that a plain passage search may not capture.
    For simple lookups of a single fact, prefer `search_knowledge_base` instead.

    Args:
        query: The natural-language question (use the user's wording or a refined version).

    Returns:
        A dict with key "context": a text block of related entities, relationships and
        supporting passages from the knowledge graph. An empty string means the graph
        had nothing relevant (or the graph is disabled).
    """
    # Import trong hàm để tránh phụ thuộc vòng lúc nạp module agent.
    from modules.chatbot.app.lightrag.lightrag_client import LightRagQuerier

    try:
        context = LightRagQuerier().query(query)
    except Exception:
        logger.exception("[adk-tool] search_knowledge_graph lỗi (trả rỗng)")
        return {"context": ""}

    logger.info("[adk-tool] search_knowledge_graph query=%r → %d ký tự", query, len(context))
    return {"context": context}
