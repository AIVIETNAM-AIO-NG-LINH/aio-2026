"""Controllers v1 của module Chatbot — mỗi controller một file, re-export để urls import gọn.

Hai nhóm endpoint:
  - NỘI BỘ (`/api/internal/v1/chatbot/...`): ingest — gate bằng
    `VerifyInternalToken` (chỉ service trong hệ AIO gọi).
  - CÔNG KHAI (`/api/v1/chatbot/...`): luồng chat của người dùng cuối, gộp 1 ViewSet.
    nginx đã verify token (qua api-aio) và forward danh tính user xuống header
    `X-Auth-User-Id`; gate `ensure_authenticated` đọc header này populate
    ``CurrentUser`` (không tự auth lại).
"""

from .chat_controller import ChatController
from .ingest_document_controller import IngestDocumentController

__all__ = [
    "ChatController",
    "IngestDocumentController",
]
