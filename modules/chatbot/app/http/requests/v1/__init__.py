"""Request schemas v1 của module Chatbot — re-export để view import gọn."""

from .chat_request import ChatDTO, ChatRequest
from .ingest_document_request import IngestDocumentDTO, IngestDocumentRequest

__all__ = [
    "ChatDTO",
    "ChatRequest",
    "IngestDocumentDTO",
    "IngestDocumentRequest",
]
