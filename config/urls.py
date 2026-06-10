"""Root URL configuration.

Mỗi module trong modules/ tự khai báo urls.py riêng và được nối vào đây.
Thêm module mới: copy modules/example, rồi thêm 1 dòng include() bên dưới.
"""
from django.urls import include, path

urlpatterns = [
    path("api/", include("modules.core.urls")),       # /api/health/
    path("api/", include("modules.example.urls")),    # /api/examples/
    # Nội bộ (service-to-service) — đã được VerifyInternalToken gate ở prefix.
    path("api/internal/chatbot/", include("modules.chatbot.urls")),  # .../documents/ingest
]
