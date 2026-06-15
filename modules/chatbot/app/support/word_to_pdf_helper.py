"""Helper convert Word (.doc/.docx) → PDF bằng LibreOffice headless.

Tách khỏi `extractor` vì đây là khâu hạ tầng riêng (gọi binary ngoài), không
dính logic trích text. Mọi lỗi (thiếu binary, convert fail, timeout, không ra
file) đều gói thành `UnsupportedDocumentError` để pipeline đánh FAILED đúng tài
liệu này mà không làm hỏng các bước khác.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile

from ..rag.exceptions import UnsupportedDocumentError

logger = logging.getLogger(__name__)

# Binary LibreOffice headless — override qua env nếu image cài tên khác.
_SOFFICE_BIN = os.getenv("LIBREOFFICE_BIN", "soffice").strip() or "soffice"
# Timeout (giây) cho 1 lần convert — tránh treo worker nếu LibreOffice kẹt.
_SOFFICE_TIMEOUT = int(os.getenv("LIBREOFFICE_TIMEOUT", "120") or "120")


def _word_suffix(mime_type: str | None) -> str:
    """Đoán đuôi file Word từ mime_type (mặc định .docx) cho LibreOffice nhận dạng."""
    mime = (mime_type or "").strip().lower()
    return ".doc" if mime == "application/msword" else ".docx"


def word_to_pdf(file_bytes: bytes, mime_type: str | None) -> bytes:
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
