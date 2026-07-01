"""Routes CÔNG KHAI của module Chatbot (luồng chat người dùng cuối).

Nối vào config/urls.py dưới prefix `api/v1/chatbot/`, nên path đầy đủ:
  - POST  `/api/v1/chatbot/chat`                                 — hỏi đáp (SSE).
  - GET   `/api/v1/chatbot/conversations`                        — list hội thoại.
  - PATCH `/api/v1/chatbot/conversations/<id>`                   — đổi tên hội thoại.
  - DELETE `/api/v1/chatbot/conversations/<id>`                  — xoá (mềm) hội thoại.
  - GET   `/api/v1/chatbot/conversations/<id>/messages`          — list tin nhắn.

Cả nhóm là 1 ViewSet (`ChatController`) — mỗi path map vào 1 action qua
``as_view({method: action})``, method khác trên cùng path tự trả 405. Tất cả gắn
gate `ensure_authenticated` (kiểu route middleware Laravel): chặn 401 khi thiếu
`X-Auth-User-Id`, có thì populate ``CurrentUser`` cho action/service đọc.

KHÁC `internal.py` (nội bộ, prefix `/api/internal/v1/chatbot/`): nhóm này nginx verify
token user (qua api-aio) rồi forward `X-Auth-User-Id`; KHÔNG đi qua
`VerifyInternalToken`.
"""

from django.urls import path

from modules.base.app.middleware import ensure_authenticated

from ...app.http.controllers.v1 import ChatController

urlpatterns = [
    path(
        "chat",
        ensure_authenticated(ChatController.as_view({"post": "chat"})),
        name="chatbot-chat",
    ),
    path(
        "conversations",
        ensure_authenticated(ChatController.as_view({"get": "conversations"})),
        name="chatbot-conversation-list",
    ),
    path(
        "conversations/<int:conversation_id>",
        ensure_authenticated(
            ChatController.as_view({"patch": "rename", "delete": "destroy"})
        ),
        name="chatbot-conversation-update",
    ),
    path(
        "conversations/<int:conversation_id>/messages",
        ensure_authenticated(ChatController.as_view({"get": "messages"})),
        name="chatbot-message-list",
    ),
]
