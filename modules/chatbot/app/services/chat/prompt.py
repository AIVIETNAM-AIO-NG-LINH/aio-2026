"""Dựng nội dung tin nhắn người dùng cho ADK agent.

Khác bản trước (nhồi sẵn chunk vào prompt): ở kiến trúc ADK, ngữ cảnh tài liệu do
tool `search_knowledge_base` cung cấp nên prompt chỉ gồm (LTM nếu có) + câu hỏi.
Chỉ dẫn hệ thống nằm ở `adk/agent.py` (instruction của Agent).
"""

from __future__ import annotations


# Reminder mỗi lượt — chống "lệch" ngôn ngữ khi tài liệu RAG/LTM khác ngôn ngữ
# với câu hỏi (instruction hệ thống một mình không đủ chắc).
_LANGUAGE_REMINDER = (
    "\n\n(Reminder: reply in the same language as the question above.)"
)


def build_user_message(question: str, ltm_context: str = "") -> str:
    """Ghép trí nhớ dài hạn (nếu có) + câu hỏi thành 1 prompt người dùng."""
    question = (question or "").strip()
    if not ltm_context.strip():
        return question + _LANGUAGE_REMINDER

    return (
        "### RELEVANT PAST CONVERSATIONS (long-term memory):\n"
        + ltm_context.strip()
        + "\n\n### QUESTION:\n"
        + question
        + _LANGUAGE_REMINDER
    )
