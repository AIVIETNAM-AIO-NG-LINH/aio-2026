"""Trích xuất text từ file gốc bằng Google GenAI (Gemini), theo TỪNG TRANG.

PDF được duyệt từng trang bằng pypdf: trang nào có sẵn text-số thì lấy thẳng
(`page.extract_text()`), trang nào rỗng/quá ngắn thì coi là trang SCAN/ảnh →
tách thành PDF 1-trang rồi đưa bytes cho Gemini multimodal OCR riêng trang đó.
Word (.doc/.docx) ở Phase 2 được convert sang PDF bằng LibreOffice headless rồi
đi qua đúng luồng theo-trang này — lỗi convert chỉ làm FAILED đúng file đó (raise
`UnsupportedDocumentError`).

`extract_pages` là đường mới (Phase 4) trả [(page, text)] để giữ số trang cho
trích dẫn. `extract_text` vẫn còn để tương thích (ghép các trang thành full-text
cho summary/LightRAG).
"""

from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

from google.genai import types
from pypdf import PdfReader, PdfWriter

from modules.base.clients.gemini_client import GeminiClient

from .exceptions import UnsupportedDocumentError

logger = logging.getLogger(__name__)

# Binary LibreOffice headless — override qua env nếu image cài tên khác.
_SOFFICE_BIN = os.getenv("LIBREOFFICE_BIN", "soffice").strip() or "soffice"
# Timeout (giây) cho 1 lần convert — tránh treo worker nếu LibreOffice kẹt.
_SOFFICE_TIMEOUT = int(os.getenv("LIBREOFFICE_TIMEOUT", "120") or "120")
# Phase 4: trang PDF có ÍT HƠN ngưỡng này ký tự (sau strip) coi là trang scan/ảnh
# → OCR riêng trang đó qua Gemini. Chỉnh ngưỡng qua env MIN_PAGE_TEXT_CHARS.
_MIN_PAGE_TEXT_CHARS = int(os.getenv("MIN_PAGE_TEXT_CHARS", "20") or "20")


@dataclass(frozen=True)
class ExtractedPage:
    """Một trang đã trích text. `page` đánh số từ 1 (như người đọc thấy)."""

    page: int
    text: str

# Loại tài liệu hỗ trợ (= value của `media.enums.FileType`) — pipeline lấy từ
# `Media.document_kind` rồi truyền vào đây.
KIND_PDF = "PDF"
KIND_WORD = "WORD"

# Prompt trích text thô — ưu tiên giữ thứ tự đọc, không tự bịa nội dung.
_EXTRACT_PROMPT = (
    "Extract ALL readable text from this document as plain UTF-8 text. "
    "Preserve the natural reading order and paragraph breaks. "
    "Do not summarise, translate, or add commentary — return only the document's text."
)


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
        return _extract_pdf_pages(file_bytes)
    if kind == KIND_WORD:
        pdf_bytes = _word_to_pdf(file_bytes, mime_type)
        return _extract_pdf_pages(pdf_bytes)
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


def _word_suffix(mime_type: str | None) -> str:
    """Đoán đuôi file Word từ mime_type (mặc định .docx) cho LibreOffice nhận dạng."""
    mime = (mime_type or "").strip().lower()
    return ".doc" if mime == "application/msword" else ".docx"


def _word_to_pdf(file_bytes: bytes, mime_type: str | None) -> bytes:
    """Convert bytes Word → bytes PDF bằng LibreOffice headless.

    Ghi file tạm, gọi `soffice --headless --convert-to pdf --outdir <tmp> <file>`,
    đọc lại PDF sinh ra. Mọi lỗi (thiếu binary, convert fail, timeout, không ra
    file) đều gói thành `UnsupportedDocumentError` để pipeline đánh FAILED đúng
    tài liệu này mà không làm hỏng các bước khác.
    """
    if shutil.which(_SOFFICE_BIN) is None:
        raise UnsupportedDocumentError(
            f"Không tìm thấy LibreOffice ('{_SOFFICE_BIN}') để convert Word→PDF"
        )

    with tempfile.TemporaryDirectory(prefix="word2pdf_") as tmp_dir:
        src_path = os.path.join(tmp_dir, f"source{_word_suffix(mime_type)}")
        with open(src_path, "wb") as fh:
            fh.write(file_bytes)

        # `--convert-to pdf` sinh <basename>.pdf trong outdir. Dùng HOME riêng để
        # LibreOffice tự tạo profile trong tmp (tránh đụng HOME của user 'app').
        env = {**os.environ, "HOME": tmp_dir}
        try:
            proc = subprocess.run(
                [
                    _SOFFICE_BIN,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    tmp_dir,
                    src_path,
                ],
                capture_output=True,
                timeout=_SOFFICE_TIMEOUT,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise UnsupportedDocumentError(
                f"LibreOffice convert Word→PDF quá {_SOFFICE_TIMEOUT}s, bỏ qua"
            ) from exc

        pdf_path = os.path.join(tmp_dir, "source.pdf")
        if proc.returncode != 0 or not os.path.exists(pdf_path):
            stderr = (proc.stderr or b"").decode("utf-8", "replace").strip()
            raise UnsupportedDocumentError(
                f"LibreOffice convert Word→PDF thất bại (rc={proc.returncode}): {stderr[:300]}"
            )

        with open(pdf_path, "rb") as fh:
            pdf_bytes = fh.read()

    logger.info(
        "[extract] Word→PDF qua LibreOffice: %d bytes Word → %d bytes PDF",
        len(file_bytes),
        len(pdf_bytes),
    )
    return pdf_bytes


def _extract_pdf_pages(file_bytes: bytes) -> list[ExtractedPage]:
    """Duyệt từng trang PDF: text-số trực tiếp; rỗng/quá ngắn → OCR Gemini riêng trang.

    Lỗi mở PDF (file hỏng/không phải PDF) → `UnsupportedDocumentError` để pipeline
    đánh FAILED đúng tài liệu này. Lỗi `extract_text()` của 1 trang chỉ làm trang
    đó coi như rỗng → rơi xuống nhánh OCR, không làm hỏng cả tài liệu.
    """
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception as exc:  # pypdf ném nhiều loại lỗi khác nhau cho PDF hỏng
        raise UnsupportedDocumentError(f"Không mở được PDF bằng pypdf: {exc}") from exc

    pages: list[ExtractedPage] = []
    ocr_count = 0
    for index, page in enumerate(reader.pages):
        page_number = index + 1
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            logger.warning("[extract] trang %d: pypdf extract_text lỗi, coi như rỗng", page_number)
            text = ""

        if len(text) < _MIN_PAGE_TEXT_CHARS:
            # Trang scan/ảnh (ít hoặc không có text-số) → OCR riêng trang qua Gemini.
            text = _ocr_pdf_page(reader, index).strip()
            ocr_count += 1

        pages.append(ExtractedPage(page=page_number, text=text))

    logger.info(
        "[extract] PDF %d trang (%d trang OCR scan, %d trang text-số)",
        len(pages),
        ocr_count,
        len(pages) - ocr_count,
    )
    return pages


def _ocr_pdf_page(reader: PdfReader, page_index: int) -> str:
    """Tách 1 trang thành PDF 1-trang (pypdf PdfWriter) rồi đưa bytes cho Gemini OCR."""
    writer = PdfWriter()
    writer.add_page(reader.pages[page_index])
    buffer = io.BytesIO()
    writer.write(buffer)
    return _extract_pdf(buffer.getvalue(), "application/pdf")


def _extract_pdf(
    file_bytes: bytes,
    mime_type: str | None,
) -> str:
    """Gửi bytes PDF cho Gemini, trả về text thô (có thể rỗng nếu model không đọc được)."""
    client = GeminiClient()
    part = types.Part.from_bytes(
        data=file_bytes,
        mime_type=mime_type or "application/pdf",
    )
    logger.info("[extract] Gemini model=%s, %d bytes PDF", client.extract_model, len(file_bytes))
    return client.generate_text([part, _EXTRACT_PROMPT], model=client.extract_model)
