"""View của module Chatbot — mỗi view một file, re-export để urls import gọn.

Hai nhóm endpoint:
  - NỘI BỘ (`/api/internal/chatbot/...`): ingest + retrieve — gate bằng
    `VerifyInternalToken` (chỉ service trong hệ AIO gọi).
  - CÔNG KHAI (`/api/chatbot/...`): luồng chat của người dùng cuối. nginx đã
    verify token (qua api-aio) và forward danh tính user xuống header
    `X-Auth-User-Id`; view đọc header này để biết user là ai (không tự auth lại).
"""

from .chat_view import ChatView, ConversationListView, MessageListView
from .ingest_document_view import IngestDocumentView

__all__ = [
    "ChatView",
    "ConversationListView",
    "IngestDocumentView",
    "MessageListView",
]
