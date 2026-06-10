"""Trích xuất text từ file gốc bằng Google GenAI (Gemini).

PDF được gửi thẳng bytes cho model multimodal lấy text. Word (.doc/.docx) ở
Phase 2 được convert sang PDF bằng LibreOffice headless rồi extract như PDF — lỗi
convert chỉ làm FAILED đúng file đó (raise `UnsupportedDocumentError`). Hàm
`extract_text` dispatch theo loại file nên mỗi loại là một nhánh độc lập.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile

from google.genai import types

from .config import GeminiConfig
from .exceptions import UnsupportedDocumentError
from .gemini_client import build_client

logger = logging.getLogger(__name__)

# Binary LibreOffice headless — override qua env nếu image cài tên khác.
_SOFFICE_BIN = os.getenv("LIBREOFFICE_BIN", "soffice").strip() or "soffice"
# Timeout (giây) cho 1 lần convert — tránh treo worker nếu LibreOffice kẹt.
_SOFFICE_TIMEOUT = int(os.getenv("LIBREOFFICE_TIMEOUT", "120") or "120")

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
    WORD → convert .doc/.docx → PDF (LibreOffice headless) rồi extract như PDF.
    khác → không nên tới đây (pipeline đã gate), nhưng vẫn raise cho chắc.
    """
    if kind == KIND_PDF:
        return _extract_pdf(file_bytes, mime_type, config)
    if kind == KIND_WORD:
        pdf_bytes = _word_to_pdf(file_bytes, mime_type)
        return _extract_pdf(pdf_bytes, "application/pdf", config)
    raise UnsupportedDocumentError(f"Loại tài liệu không hỗ trợ: kind={kind!r}")


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
