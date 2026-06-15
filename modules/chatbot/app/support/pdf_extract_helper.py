"""Helper trích text THEO TRANG từ PDF bằng pypdf + Gemini OCR.

Tách khỏi `extractor` để gom riêng phần đọc PDF cấp thấp: duyệt trang pypdf,
nhận diện trang scan/lai, và OCR cả trang qua Gemini multimodal khi cần.

Trang nào có sẵn text-số thì lấy thẳng (`page.extract_text()`); trang rỗng/quá
ngắn (scan) HOẶC có ảnh đáng kể (trang "lai": text + chart/ảnh chứa chữ) → tách
thành PDF 1-trang rồi đưa bytes cho Gemini OCR — Gemini đọc cả text-số lẫn chữ
trong ảnh nên không cần ghép 2 nguồn.
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass

from google.genai import types
from pypdf import PageObject, PdfReader, PdfWriter

from modules.base.clients.gemini_client import GeminiClient

from ..rag.exceptions import UnsupportedDocumentError

logger = logging.getLogger(__name__)

# Phase 4: trang PDF có ÍT HƠN ngưỡng này ký tự (sau strip) coi là trang scan/ảnh
# → OCR riêng trang đó qua Gemini. Chỉnh ngưỡng qua env MIN_PAGE_TEXT_CHARS.
_MIN_PAGE_TEXT_CHARS = int(os.getenv("MIN_PAGE_TEXT_CHARS", "20") or "20")
# Trang có ảnh với data (sau decode) >= ngưỡng byte này cũng được OCR dù đã đủ
# text-số — vá trường hợp trang lai làm mất chữ trong ảnh/chart. Ảnh nhỏ hơn coi
# là trang trí (logo, icon) để khỏi tốn call Gemini. Đặt giá trị âm để tắt hẳn
# việc OCR theo ảnh (quay về hành vi cũ: chỉ OCR trang scan).
_MIN_OCR_IMAGE_BYTES = int(os.getenv("MIN_OCR_IMAGE_BYTES", "5000") or "5000")

# Prompt trích text thô — ưu tiên giữ thứ tự đọc, không tự bịa nội dung.
_EXTRACT_PROMPT = (
    "Extract ALL readable text from this document as plain UTF-8 text. "
    "Preserve the natural reading order and paragraph breaks. "
    "Do not summarise, translate, or add commentary — return only the document's text."
)


@dataclass(frozen=True)
class ExtractedPage:
    """Một trang đã trích text. `page` đánh số từ 1 (như người đọc thấy)."""

    page: int
    text: str


def _page_has_significant_images(page: PageObject) -> bool:
    """Trang có ảnh đủ lớn (data decode >= `_MIN_OCR_IMAGE_BYTES`) đáng để OCR không.

    Lỗi khi liệt kê/decode ảnh (filter pypdf không hỗ trợ, PDF hỏng cục bộ) → coi
    là CÓ ảnh: thà tốn 1 call Gemini còn hơn bỏ sót chữ trong ảnh.
    """
    if _MIN_OCR_IMAGE_BYTES < 0:
        return False
    try:
        for image in page.images:
            if len(image.data) >= _MIN_OCR_IMAGE_BYTES:
                return True
    except Exception:
        return True
    return False


def extract_pdf_pages(file_bytes: bytes) -> list[ExtractedPage]:
    """Duyệt từng trang PDF: text-số trực tiếp; trang scan HOẶC có ảnh → OCR Gemini.

    Trang lai (đủ text-số nhưng kèm ảnh/chart) cũng OCR cả trang — Gemini đọc cả
    text-số lẫn chữ trong ảnh; OCR trả rỗng thì giữ lại text pypdf (fail-safe).
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

        if len(text) < _MIN_PAGE_TEXT_CHARS or _page_has_significant_images(page):
            # Trang scan hoặc trang lai có ảnh → OCR cả trang qua Gemini. OCR rỗng
            # (model không đọc được) thì giữ text pypdf đã có thay vì mất trắng.
            text = _ocr_pdf_page(reader, index).strip() or text
            ocr_count += 1

        if not text:
            logger.warning("[extract] trang %d: không trích được text (trang rỗng)", page_number)

        pages.append(ExtractedPage(page=page_number, text=text))

    logger.info(
        "[extract] PDF %d trang (%d trang OCR scan/có ảnh, %d trang text-số thuần)",
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
