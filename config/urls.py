"""Root URL configuration.

Mỗi module trong modules/ tự khai báo urls.py riêng và được nối vào đây.
Thêm module mới: copy modules/example, rồi thêm 1 dòng include() bên dưới.
"""
from django.urls import include, path

urlpatterns = [
    path("api/", include("modules.core.routes.public")),  # /api/health/
    path("api/", include("modules.example.routes.public")),  # /api/examples/
    # Chatbot công khai (luồng chat user) — nginx verify token, forward X-Auth-User-Id.
    path("api/v1/chatbot/", include("modules.chatbot.routes.v1.public")),  # chat / conversations
    # Nội bộ (service-to-service) — đã được VerifyInternalToken gate ở prefix.
    path("api/internal/v1/chatbot/", include("modules.chatbot.routes.v1.internal")),  # .../documents/ingest
]
