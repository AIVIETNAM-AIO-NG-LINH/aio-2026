"""Service layer của module Chatbot — re-export để view import gọn.

(Truy hồi chunk đã chuyển sang `app/tools/` thành function `knowledge_base.search()`
— là công cụ, không phải orchestration. Import `from ..tools import knowledge_base`.)
"""

from .v1 import ChatService, IngestDocumentService

__all__ = ["ChatService", "IngestDocumentService"]
