"""Tách văn bản thành chunk bằng RecursiveCharacterTextSplitter (langchain).

Mỗi chunk được prefix bằng CONTEXTUAL HEADER (bản "light", không gọi LLM): ghép
tên tài liệu + số trang + loại file thành 1 dòng để chunk lẻ tự đủ ngữ cảnh khi
truy hồi → tăng recall. Header đi vào CHÍNH `text` của chunk nên vừa ảnh hưởng
vector (lúc embed) vừa được lưu nguyên trong `chunk_text` ở OpenSearch.

Phase 4: `chunk_pages` cắt chunk TRONG từng trang để mỗi chunk mang đúng số trang
của nó (`PageChunk.page`) phục vụ trích dẫn — và vì page đã biết ngay tại đây nên
header (kèm `Trang`) được dựng đúng 1 lần ở bước này, không lặp. `chunk_text` (cắt
cả khối) vẫn giữ để tương thích.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import ChunkConfig, ContextualHeaderConfig

# Tách theo đoạn → dòng → ranh giới câu (regex lookbehind cuối câu).
_SEPARATORS = ["\n\n", "\n", "(?<=[.!?])"]


def _build_prefix(
    header_config: ContextualHeaderConfig | None,
    original_name: str,
    page: int | str,
    kind: str,
) -> str:
    """Dựng prefix (kèm "\\n") cho 1 chunk theo cấu hình header.

    Bật → contextual header giàu metadata (`template.format(name/page/kind)`);
    template lỗi placeholder lạ → tự lùi về prefix cũ. Tắt/không cấu hình → giữ
    nguyên prefix cũ "File: {name}" để tương thích Phase 1-4.
    """
    legacy = f"File: {original_name}\n"
    if header_config is None or not header_config.enabled:
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
    kind: str = "",
    header_config: ContextualHeaderConfig | None = None,
) -> list[PageChunk]:
    """Cắt chunk TRONG từng trang, gắn số trang + contextual header vào mỗi chunk.

    `pages` là các object có thuộc tính `.page` (int, từ 1) và `.text` (str) —
    đúng `ExtractedPage` mà extractor trả về. Mỗi chunk chỉ thuộc 1 trang; trang
    rỗng/chỉ khoảng trắng bị bỏ qua. Header dựng theo `header_config` (kèm số trang
    THẬT của chunk) ngay tại đây — page đã biết nên không cần dựng lại về sau.
    `kind` là loại file (vd "PDF"/"WORD") để điền `{kind}` trong header.
    """
    splitter = _build_splitter(config)

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
