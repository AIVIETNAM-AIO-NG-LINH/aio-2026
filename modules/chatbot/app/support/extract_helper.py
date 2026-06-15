"""Trích xuất text từ file gốc, theo TỪNG TRANG — API công khai của khâu extract.

Đây là lớp điều phối mỏng: chọn luồng theo `kind` rồi gọi helper cấp thấp.
  * PDF  → `pdf_extract_helper.extract_pdf_pages` (pypdf + Gemini OCR theo trang).
  * Word → `word_to_pdf_helper.word_to_pdf` (LibreOffice headless) rồi đi đúng
    luồng PDF theo-trang ở trên.

`extract_pages` (Phase 4) trả [(page, text)] để giữ số trang cho trích dẫn.
`extract_text` vẫn còn để tương thích (ghép các trang thành full-text cho
summary/LightRAG). `ExtractedPage` được re-export từ `pdf_extract_helper`.
"""

from __future__ import annotations

from ..rag.exceptions import UnsupportedDocumentError
from .pdf_extract_helper import ExtractedPage, extract_pdf_pages
from .word_to_pdf_helper import word_to_pdf

__all__ = [
    "ExtractedPage",
    "KIND_PDF",
    "KIND_WORD",
    "extract_pages",
    "extract_text",
    "pages_to_text",
]

# Loại tài liệu hỗ trợ (= value của `media.enums.FileType`) — pipeline lấy từ
# `Media.document_kind` rồi truyền vào đây.
KIND_PDF = "PDF"
KIND_WORD = "WORD"


def extract_pages(
    file_bytes: bytes,
    kind: str,
    mime_type: str | None,
) -> list[ExtractedPage]:
    """Trích text THEO TRANG, trả [ExtractedPage(page, text)] (page từ 1).

    PDF  → duyệt từng trang bằng pypdf (text-số trực tiếp, scan thì OCR Gemini).
    WORD → convert .doc/.docx → PDF (LibreOffice headless) rồi duyệt trang như PDF.
    khác → không nên tới đây (pipeline đã gate), nhưng vẫn raise cho chắc.
    """
    if kind == KIND_PDF:
        return extract_pdf_pages(file_bytes)
    if kind == KIND_WORD:
        pdf_bytes = word_to_pdf(file_bytes, mime_type)
        return extract_pdf_pages(pdf_bytes)
    raise UnsupportedDocumentError(f"Loại tài liệu không hỗ trợ: kind={kind!r}")


def pages_to_text(pages: list[ExtractedPage]) -> str:
    """Ghép các trang thành full-text (cách nhau 1 dòng trống) cho summary/LightRAG."""
    return "\n\n".join(page.text for page in pages if page.text and page.text.strip())


def extract_text(
    file_bytes: bytes,
    kind: str,
    mime_type: str | None,
) -> str:
    """Trích full-text (tương thích cũ) = ghép text của tất cả các trang.

    Giữ lại cho các bước chỉ cần text đầy đủ, không cần số trang (summary, KG).
    """
    return pages_to_text(extract_pages(file_bytes, kind, mime_type))
