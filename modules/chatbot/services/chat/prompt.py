"""Dựng nội dung tin nhắn người dùng cho ADK agent.

Khác bản trước (nhồi sẵn chunk vào prompt): ở kiến trúc ADK, ngữ cảnh tài liệu do
tool `search_knowledge_base` cung cấp nên prompt chỉ gồm (LTM nếu có) + câu hỏi.
Chỉ dẫn hệ thống nằm ở `adk/agent.py` (instruction của Agent).
"""

from __future__ import annotations


def build_user_message(question: str, ltm_context: str = "") -> str:
    """Ghép trí nhớ dài hạn (nếu có) + câu hỏi thành 1 prompt người dùng."""
    question = (question or "").strip()
    if not ltm_context.strip():
        return question

    return (
        "### HỘI THOẠI LIÊN QUAN TRƯỚC ĐÂY (trí nhớ dài hạn):\n"
        + ltm_context.strip()
        + "\n\n### CÂU HỎI:\n"
        + question
    )
