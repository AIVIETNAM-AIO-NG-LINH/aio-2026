"""Routes CÔNG KHAI của module Chatbot (luồng chat người dùng cuối).

Nối vào config/urls.py dưới prefix `api/chatbot/`, nên path đầy đủ:
  - POST `/api/chatbot/chat`                                  — hỏi đáp (SSE).
  - GET  `/api/chatbot/conversations`                        — list hội thoại.
  - GET  `/api/chatbot/conversations/<id>/messages`          — list tin nhắn.

KHÁC `internal.py` (nội bộ, prefix `/api/internal/chatbot/`): nhóm này nginx verify
token user (qua api-aio) rồi forward `X-Auth-User-Id`; KHÔNG đi qua
`VerifyInternalToken`.
"""

from django.urls import path

from ..views import ChatView, ConversationListView, MessageListView

urlpatterns = [
    path("chat", ChatView.as_view(), name="chatbot-chat"),
    path(
        "conversations",
        ConversationListView.as_view(),
        name="chatbot-conversation-list",
    ),
    path(
        "conversations/<int:conversation_id>/messages",
        MessageListView.as_view(),
        name="chatbot-message-list",
    ),
]
