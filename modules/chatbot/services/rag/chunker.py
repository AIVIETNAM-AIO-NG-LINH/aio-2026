"""Tách văn bản thành chunk bằng RecursiveCharacterTextSplitter (langchain).

Mỗi chunk được prefix bằng tên file gốc để giữ ngữ cảnh khi truy hồi (chunk lẻ
vẫn biết mình thuộc tài liệu nào).

Phase 4: `chunk_pages` cắt chunk TRONG từng trang để mỗi chunk mang đúng số trang
của nó (`PageChunk.page`) phục vụ trích dẫn. `chunk_text` (cắt cả khối) vẫn giữ
để tương thích.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import ChunkConfig

# Tách theo đoạn → dòng → ranh giới câu (regex lookbehind cuối câu).
_SEPARATORS = ["\n\n", "\n", "(?<=[.!?])"]


@dataclass(frozen=True)
class PageChunk:
    """Một chunk thuộc đúng 1 trang. `page` đánh số từ 1, `text` đã có prefix file."""

    text: str
    page: int


def _build_splitter(config: ChunkConfig) -> RecursiveCharacterTextSplitter:
    """Khởi tạo splitter chung (cùng tham số 800/120 + separators cho mọi đường cắt)."""
    return RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        separators=_SEPARATORS,
        is_separator_regex=True,
    )


def chunk_text(text: str, original_name: str, config: ChunkConfig) -> list[str]:
    """Tách `text` thành các chunk, prefix mỗi chunk bằng "File: {original_name}\\n".

    Trả list rỗng nếu text rỗng/chỉ khoảng trắng.
    """
    if not text or not text.strip():
        return []

    splitter = _build_splitter(config)
    prefix = f"File: {original_name}\n"
    return [f"{prefix}{piece}" for piece in splitter.split_text(text) if piece.strip()]


def chunk_pages(
    pages: Iterable,
    original_name: str,
    config: ChunkConfig,
) -> list[PageChunk]:
    """Cắt chunk TRONG từng trang, gắn số trang vào mỗi chunk.

    `pages` là các object có thuộc tính `.page` (int, từ 1) và `.text` (str) —
    đúng `ExtractedPage` mà extractor trả về. Mỗi chunk chỉ thuộc 1 trang; trang
    rỗng/chỉ khoảng trắng bị bỏ qua. Prefix "File: {original_name}\\n" giữ như cũ.
    """
    splitter = _build_splitter(config)
    prefix = f"File: {original_name}\n"

    chunks: list[PageChunk] = []
    for page in pages:
        text = page.text
        if not text or not text.strip():
            continue
        for piece in splitter.split_text(text):
            if piece.strip():
                chunks.append(PageChunk(text=f"{prefix}{piece}", page=page.page))
    return chunks
