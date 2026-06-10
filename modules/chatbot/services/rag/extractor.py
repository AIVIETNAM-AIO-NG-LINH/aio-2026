"""Trích xuất text từ file gốc bằng Google GenAI (Gemini).

Phase 1: chỉ hỗ trợ PDF (gửi bytes cho model multimodal lấy text). Word được
nhận diện nhưng đánh FAILED (LibreOffice → PDF để Phase 2). Hàm `extract_text`
dispatch theo loại file nên Phase 2 chỉ cần bổ sung nhánh Word.
"""

from __future__ import annotations

import logging

from google.genai import types

from .config import GeminiConfig
from .exceptions import UnsupportedDocumentError
from .gemini_client import build_client

logger = logging.getLogger(__name__)

# Phân loại tài liệu sau khi soi mime_type/file_type.
KIND_PDF = "PDF"
KIND_WORD = "WORD"
KIND_OTHER = "OTHER"

_PDF_MIMES = {"application/pdf"}
_WORD_MIMES = {
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Prompt trích text thô — ưu tiên giữ thứ tự đọc, không tự bịa nội dung.
_EXTRACT_PROMPT = (
    "Extract ALL readable text from this document as plain UTF-8 text. "
    "Preserve the natural reading order and paragraph breaks. "
    "Do not summarise, translate, or add commentary — return only the document's text."
)


def detect_kind(mime_type: str | None, file_type: str | None) -> str:
    """Suy ra loại tài liệu (PDF/WORD/OTHER) từ mime_type rồi tới file_type."""
    mime = (mime_type or "").strip().lower()
    ftype = (file_type or "").strip().upper()

    if mime in _PDF_MIMES or ftype == KIND_PDF:
        return KIND_PDF
    if mime in _WORD_MIMES or ftype == KIND_WORD:
        return KIND_WORD
    return KIND_OTHER


def extract_text(
    file_bytes: bytes,
    kind: str,
    mime_type: str | None,
    config: GeminiConfig,
) -> str:
    """Trích text theo loại tài liệu.

    PDF  → gọi Gemini multimodal.
    WORD → chưa hỗ trợ ở Phase 1 (raise UnsupportedDocumentError → FAILED).
    khác → không nên tới đây (pipeline đã gate), nhưng vẫn raise cho chắc.
    """
    if kind == KIND_PDF:
        return _extract_pdf(file_bytes, mime_type, config)
    if kind == KIND_WORD:
        raise UnsupportedDocumentError(
            "Word chưa hỗ trợ ở Phase 1 (chuyển Office→PDF để Phase 2)"
        )
    raise UnsupportedDocumentError(f"Loại tài liệu không hỗ trợ: kind={kind!r}")


def _extract_pdf(
    file_bytes: bytes,
    mime_type: str | None,
    config: GeminiConfig,
) -> str:
    """Gửi bytes PDF cho Gemini, trả về text thô (có thể rỗng nếu model không đọc được)."""
    client = build_client(config)
    part = types.Part.from_bytes(
        data=file_bytes,
        mime_type=mime_type or "application/pdf",
    )
    logger.info("[extract] Gemini model=%s, %d bytes PDF", config.extract_model, len(file_bytes))
    response = client.models.generate_content(
        model=config.extract_model,
        contents=[part, _EXTRACT_PROMPT],
    )
    return (response.text or "").strip()
