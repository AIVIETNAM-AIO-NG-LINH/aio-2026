"""Dựng nội dung tin nhắn người dùng cho ADK agent.

Khác bản trước (nhồi sẵn chunk vào prompt): ở kiến trúc ADK, ngữ cảnh tài liệu do
tool `search_knowledge_base` cung cấp nên prompt chỉ gồm (LTM nếu có) + câu hỏi.
Chỉ dẫn hệ thống nằm ở `adk/agent.py` (instruction của Agent).
"""

from __future__ import annotations

from collections.abc import Sequence


# Reminder mỗi lượt — chống "lệch" ngôn ngữ khi tài liệu RAG/LTM khác ngôn ngữ
# với câu hỏi (instruction hệ thống một mình không đủ chắc).
_LANGUAGE_REMINDER = (
    "\n\n(Reminder: reply in the same language as the question above.)"
)


def build_user_message(
    question: str,
    ltm_context: str = "",
    attached_file_names: Sequence[str] | None = None,
) -> str:
    """Ghép (file đính kèm) + trí nhớ dài hạn + câu hỏi thành 1 prompt người dùng.

    File đính kèm (nếu có) được gắn vào Content dưới dạng Part riêng (Gemini đọc
    native); ở prompt chỉ thêm 1 ghi chú liệt kê TÊN file để model biết có tài liệu
    kèm + dùng đúng tên khi trích nguồn. `attached_file_names` rỗng → bỏ qua block này.
    """
    question = (question or "").strip()

    attached_block = ""
    if attached_file_names:
        listed = "\n".join(f"- {name}" for name in attached_file_names if name)
        if listed:
            attached_block = (
                "### FILES ATTACHED BY THE USER TO THIS MESSAGE:\n"
                + listed
                + "\n(The file contents are attached directly — use them to answer "
                "and cite them by file name.)\n\n"
            )

    if not ltm_context.strip():
        return attached_block + question + _LANGUAGE_REMINDER

    return (
        attached_block
        + "### RELEVANT PAST CONVERSATIONS (long-term memory):\n"
        + ltm_context.strip()
        + "\n\n### QUESTION:\n"
        + question
        + _LANGUAGE_REMINDER
    )
