"""Repository cho `ChatbotDocument` — gom mọi truy vấn DB của bảng này một chỗ.

Request/Service không query model trực tiếp mà đi qua repository (mirror pattern
Laravel của dự án gốc). `query()` của base đã dùng manager mặc định nên bản ghi
soft-delete tự bị loại.
"""

from __future__ import annotations

from modules.base.repositories import BaseRepository

from ..models import ChatbotDocument


class ChatbotDocumentRepository(BaseRepository[ChatbotDocument]):
    """Truy vấn `chatbot_documents` (bảng dùng chung, managed=False — chỉ đọc/ghi DATA)."""

    model = ChatbotDocument

    def exists(self, document_id: int) -> bool:
        """Bản ghi còn tồn tại (chưa xóa mềm) hay không."""
        return self.query().filter(pk=document_id).exists()

    def find_with_media(self, document_id: int) -> ChatbotDocument | None:
        """Bản ghi kèm `media` (select_related) — cho pipeline ingest đọc file gốc."""
        return self.query().select_related("media").filter(pk=document_id).first()

    def set_status(self, document_id: int, status: str) -> bool:
        """Ghi cột `status` (value của `DocumentStatus`); False nếu bản ghi không tồn tại."""
        return bool(self.query().filter(pk=document_id).update(status=status))
