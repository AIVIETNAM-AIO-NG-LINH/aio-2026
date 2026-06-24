"""Routes nội bộ của module Chatbot.

Nối vào config/urls.py dưới prefix `api/internal/v1/chatbot/`, nên path đầy đủ là
`POST /api/internal/v1/chatbot/documents/ingest` và `.../documents/purge` (không
trailing slash — khớp đúng URL api-aio gọi sang).
"""
from django.urls import path

from ...app.http.controllers.v1 import (
    IngestDocumentController,
    PurgeDocumentController,
)

urlpatterns = [
    path("documents/ingest", IngestDocumentController.as_view(), name="chatbot-document-ingest"),
    path("documents/purge", PurgeDocumentController.as_view(), name="chatbot-document-purge"),
]
