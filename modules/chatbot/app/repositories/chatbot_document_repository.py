"""Repository cho `ChatbotDocument` — gom mọi truy vấn DB của bảng này một chỗ.

Request/Service không query model trực tiếp mà đi qua repository (mirror pattern
Laravel của dự án gốc). `query()` của base đã dùng manager mặc định nên bản ghi
soft-delete tự bị loại.
"""

from __future__ import annotations

from modules.base.app.repositories import BaseRepository

from ..contracts.repositories import ChatbotDocumentRepositoryInterface
from ..models import ChatbotDocument


class ChatbotDocumentRepository(
    BaseRepository[ChatbotDocument], ChatbotDocumentRepositoryInterface
):
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

    def update_progress(
        self,
        document_id: int,
        status: str | None = None,
        percent: int | None = None,
    ) -> ChatbotDocument | None:
        """Ghi gộp `status`/`indexed_percent` rồi đọc lại bản ghi mới (None nếu không tồn tại)."""
        fields: dict[str, object] = {}
        if status is not None:
            fields["status"] = status
        if percent is not None:
            fields["indexed_percent"] = max(0, min(100, percent))

        query = self.query().filter(pk=document_id)
        # Không có gì để ghi → chỉ đọc bản ghi hiện tại (vẫn trả state cho hook).
        if fields and not query.update(**fields):
            return None
        return self.query().filter(pk=document_id).first()
