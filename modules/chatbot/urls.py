"""Routes nội bộ của module Chatbot.

Nối vào config/urls.py dưới prefix `api/internal/chatbot/`, nên path đầy đủ là
`POST /api/internal/chatbot/documents/ingest` (không trailing slash — khớp đúng
URL api-aio gọi sang).
"""
from django.urls import path

from .views import IngestDocumentView, RetrieveView

urlpatterns = [
    path("documents/ingest", IngestDocumentView.as_view(), name="chatbot-document-ingest"),
    # POST /api/internal/chatbot/retrieve — truy hồi chunk (hybrid + rerank), không sinh LLM.
    path("retrieve", RetrieveView.as_view(), name="chatbot-retrieve"),
]
