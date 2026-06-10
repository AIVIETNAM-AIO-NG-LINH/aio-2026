"""Exception nội bộ của pipeline RAG.

Dùng để phân biệt lỗi "bỏ qua có chủ đích" (loại file chưa hỗ trợ) với lỗi hệ
thống. Pipeline bắt mọi lỗi và đánh document FAILED, nhưng tách kiểu giúp log rõ
nguyên nhân.
"""

from __future__ import annotations


class RagPipelineError(Exception):
    """Lỗi gốc của pipeline RAG."""


class UnsupportedDocumentError(RagPipelineError):
    """Loại tài liệu chưa hỗ trợ ở phase hiện tại (vd Word ở Phase 1)."""
