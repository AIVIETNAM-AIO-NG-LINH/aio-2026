"""Contract cho `ChatbotDocumentRepository` — các truy vấn domain bắt buộc.

Khai báo "cái gì" (hợp đồng); implementation ở `repositories/`. Method CRUD nền
(`find`, `create`, ...) đã nằm ở `BaseRepository` nên không lặp lại ở đây.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models import ChatbotDocument


class ChatbotDocumentRepositoryInterface(ABC):
    """Hợp đồng truy vấn `chatbot_documents`."""

    @abstractmethod
    def exists(self, document_id: int) -> bool:
        """Bản ghi còn tồn tại (chưa xóa mềm) hay không."""
        ...

    @abstractmethod
    def find_with_media(self, document_id: int) -> ChatbotDocument | None:
        """Bản ghi kèm `media` (select_related) — cho pipeline ingest đọc file gốc."""
        ...

    @abstractmethod
    def set_status(self, document_id: int, status: str) -> bool:
        """Ghi cột `status` (value của `DocumentStatus`); False nếu bản ghi không tồn tại."""
        ...
