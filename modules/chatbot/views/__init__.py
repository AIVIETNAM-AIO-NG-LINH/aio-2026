"""View của module Chatbot — mỗi view một file, re-export để urls import gọn.

Hai nhóm endpoint:
  - NỘI BỘ (`/api/internal/chatbot/...`): ingest — gate bằng
    `VerifyInternalToken` (chỉ service trong hệ AIO gọi).
  - CÔNG KHAI (`/api/chatbot/...`): luồng chat của người dùng cuối, gộp 1 ViewSet.
    nginx đã verify token (qua api-aio) và forward danh tính user xuống header
    `X-Auth-User-Id`; gate `ensure_authenticated` đọc header này populate
    ``CurrentUser`` (không tự auth lại).
"""

from .chat_view import ChatViewSet
from .ingest_document_view import IngestDocumentView

__all__ = [
    "ChatViewSet",
    "IngestDocumentView",
]
