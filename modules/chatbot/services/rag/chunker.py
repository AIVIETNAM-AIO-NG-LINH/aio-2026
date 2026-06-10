"""Tách văn bản thành chunk bằng RecursiveCharacterTextSplitter (langchain).

Mỗi chunk được prefix bằng tên file gốc để giữ ngữ cảnh khi truy hồi (chunk lẻ
vẫn biết mình thuộc tài liệu nào).
"""

from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import ChunkConfig

# Tách theo đoạn → dòng → ranh giới câu (regex lookbehind cuối câu).
_SEPARATORS = ["\n\n", "\n", "(?<=[.!?])"]


def chunk_text(text: str, original_name: str, config: ChunkConfig) -> list[str]:
    """Tách `text` thành các chunk, prefix mỗi chunk bằng "File: {original_name}\\n".

    Trả list rỗng nếu text rỗng/chỉ khoảng trắng.
    """
    if not text or not text.strip():
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        separators=_SEPARATORS,
        is_separator_regex=True,
    )
    prefix = f"File: {original_name}\n"
    return [f"{prefix}{piece}" for piece in splitter.split_text(text) if piece.strip()]
