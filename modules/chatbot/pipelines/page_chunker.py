"""Cắt chunk THEO TRANG cho ingest, bằng RecursiveCharacterTextSplitter (langchain).

Mỗi chunk thuộc đúng 1 trang (`PageChunk.page`, đánh số từ 1) phục vụ trích dẫn,
và được prefix bằng CONTEXTUAL HEADER (bản "light", không gọi LLM): ghép tên tài
liệu + số trang + loại file thành 1 dòng để chunk lẻ tự đủ ngữ cảnh khi truy hồi
→ tăng recall. Header đi vào CHÍNH `text` của chunk nên vừa ảnh hưởng vector
(lúc embed) vừa được lưu nguyên trong `chunk_text` ở OpenSearch. Vì page đã biết
ngay tại đây nên header (kèm `Page`) được dựng đúng 1 lần, không lặp về sau.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .chunk_config import ChunkConfig
from .contextual_header_config import ContextualHeaderConfig
from .extractor import ExtractedPage

# Tách theo đoạn → dòng → ranh giới câu (regex lookbehind cuối câu).
_SEPARATORS = ["\n\n", "\n", "(?<=[.!?])"]


def _build_splitter() -> RecursiveCharacterTextSplitter:
    """Khởi tạo splitter — tham số (800/120) đọc từ env NGAY TẠI ĐÂY qua `ChunkConfig`."""
    config = ChunkConfig.from_env()
    return RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        separators=_SEPARATORS,
        is_separator_regex=True,
    )


def _build_prefix(
    header_config: ContextualHeaderConfig,
    original_name: str,
    page: int | str,
    kind: str,
) -> str:
    """Dựng prefix (kèm "\\n") cho 1 chunk theo cấu hình header.

    Bật → contextual header giàu metadata (`template.format(name/page/kind)`);
    template lỗi placeholder lạ → tự lùi về prefix cũ. Tắt (env) → giữ nguyên
    prefix cũ "File: {name}" để tương thích Phase 1-4.
    """
    legacy = f"File: {original_name}\n"
    if not header_config.enabled:
        return legacy
    try:
        header = header_config.template.format(
            name=original_name, page=page, kind=kind
        )
    except (KeyError, IndexError):
        return legacy
    return f"{header}\n"


@dataclass(frozen=True)
class PageChunk:
    """Một chunk thuộc đúng 1 trang. `page` đánh số từ 1, `text` đã có prefix file."""

    text: str
    page: int


def chunk_pages(
    pages: Iterable[ExtractedPage],
    original_name: str,
    kind: str = "",
) -> list[PageChunk]:
    """Cắt chunk TRONG từng trang, gắn số trang + contextual header vào mỗi chunk.

    `pages` là các `ExtractedPage` (`.page` int từ 1, `.text` str) mà extractor
    cùng package trả về. Mỗi chunk chỉ thuộc 1 trang; trang rỗng/chỉ khoảng trắng
    bị bỏ qua. Mọi config (chunk + header) đọc từ env NGAY TẠI ĐÂY — caller không
    cần biết. Header dựng kèm số trang THẬT của chunk vì page đã biết, không cần
    dựng lại về sau. `kind` là loại file (vd "PDF"/"WORD") để điền `{kind}` trong
    header.
    """
    header_config = ContextualHeaderConfig.from_env()
    splitter = _build_splitter()

    chunks: list[PageChunk] = []
    for page in pages:
        text = page.text
        if not text or not text.strip():
            continue
        prefix = _build_prefix(header_config, original_name, page.page, kind)
        for piece in splitter.split_text(text):
            if piece.strip():
                chunks.append(PageChunk(text=f"{prefix}{piece}", page=page.page))
    return chunks
