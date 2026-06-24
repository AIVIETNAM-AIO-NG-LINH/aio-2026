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
    text passages, each with its source document name, page number, and a `media_id`
    (pass it to `get_document_url` if you need a clickable link to the file).

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


def get_document_url(media_id: int) -> dict[str, Any]:
    """Get a public link (URL) to a source document file by its media_id.

    Call this ONLY when you need to give the user a clickable link to a source — e.g.
    the user explicitly asks for the file/link, or you want to cite a passage with a
    link they can open. The `media_id` comes from a `search_knowledge_base` result; do
    NOT guess it. Skip this tool for normal questions that don't need a link.

    Args:
        media_id: The media_id of the source document (from search_knowledge_base results).

    Returns:
        A dict {"media_id", "original_name", "url"}. `url` is a public link to the file,
        or null if the document was not found or has no link. Use the url EXACTLY as
        returned — never invent or alter it.
    """
    # Import trong hàm để tránh phụ thuộc vòng lúc nạp module agent.
    from modules.chatbot.app.tools import document_link

    fallback = {"media_id": media_id, "original_name": None, "url": None}
    try:
        result = document_link.get_url(media_id)
    except Exception:
        logger.exception("[adk-tool] get_document_url lỗi (media_id=%s)", media_id)
        return fallback

    logger.info("[adk-tool] get_document_url media_id=%s → %s", media_id, bool(result))
    return result or fallback


def create_mind_map(content: str, focus: str = "") -> dict[str, Any]:
    """Build a visual MIND MAP (sơ đồ tư duy) for the user, from CONTENT YOU choose.

    Call this ONLY when the user explicitly asks to draw, visualize, or summarize
    something as a mind map (e.g. "sơ đồ tư duy", "mind map", "vẽ sơ đồ").

    YOU decide WHAT the mind map covers, matching exactly what the user asked for, and
    pass that material in `content`. The system then turns `content` into a structured
    diagram for the user — so the diagram's scope is whatever you put in `content`:
      - "vẽ sơ đồ câu trả lời vừa rồi" / "tóm tắt ý chính" → put your own answer (the
        key points) in `content`.
      - "sơ đồ về <chủ đề X>" → put the material about X (from the documents / the
        conversation) in `content`, and set `focus` to X.
      - "sơ đồ cả cuộc trò chuyện" → leave `content` empty ("") to map the whole
        conversation.
    Write `content` in the user's language, grounded ONLY in the conversation / tool
    results (never outside knowledge). After calling this, ALWAYS also write one short
    sentence (in the user's language) telling the user the mind map is shown below;
    never leave your reply empty. Do NOT call it for ordinary questions.

    Args:
        content: The material to turn into the mind map — the text YOU select to match
            the user's request (your answer, the key points, or the topic's details).
            Leave empty ("") to fall back to mapping the whole conversation.
        focus: Optional topic to center the mind map on (used for titling / emphasis).

    Returns:
        A dict {"requested": true, "content": <content>, "focus": <focus>} —
        confirmation that the mind map was queued (the actual diagram is generated
        from `content` and sent to the user separately).
    """
    # TRIGGER + nội dung do agent chọn — KHÔNG gọi Gemini ở đây. Tool sync chạy TRỰC
    # TIẾP trên thread event-loop của ADK runner (không phải thread riêng), nên việc
    # nặng/blocking (gọi Gemini structured-output + đếm token) PHẢI để ngoài tool, chạy
    # sau lượt trả lời ở chat_service — vừa không chặn event-loop, vừa đếm được token.
    # `content` chính là PHẠM VI sơ đồ: agent hiểu user muốn gì nên tự chọn nội dung,
    # tránh việc tóm tắt mù cả hội thoại (sai phạm vi). Xem chat_pipeline/mind_map.py
    # và services/v1/chat_service.py.
    logger.info(
        "[adk-tool] create_mind_map focus=%r content_len=%d", focus, len(content or "")
    )
    return {"requested": True, "content": content or "", "focus": focus or ""}


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
