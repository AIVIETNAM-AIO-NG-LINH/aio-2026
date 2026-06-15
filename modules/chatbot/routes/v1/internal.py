"""Routes nội bộ của module Chatbot.

Nối vào config/urls.py dưới prefix `api/internal/chatbot/`, nên path đầy đủ là
`POST /api/internal/chatbot/documents/ingest` (không trailing slash — khớp đúng
URL api-aio gọi sang).
"""
from django.urls import path

from ...app.http.controllers.v1 import IngestDocumentController

urlpatterns = [
    path("documents/ingest", IngestDocumentController.as_view(), name="chatbot-document-ingest"),
]
