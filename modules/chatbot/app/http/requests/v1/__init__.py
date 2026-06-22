"""Request schemas v1 của module Chatbot — re-export để view import gọn."""

from .chat_request import ChatDTO, ChatRequest
from .ingest_document_request import IngestDocumentDTO, IngestDocumentRequest
from .purge_document_request import PurgeDocumentDTO, PurgeDocumentRequest
from .update_conversation_request import (
    UpdateConversationDTO,
    UpdateConversationRequest,
)

__all__ = [
    "ChatDTO",
    "ChatRequest",
    "IngestDocumentDTO",
    "IngestDocumentRequest",
    "PurgeDocumentDTO",
    "PurgeDocumentRequest",
    "UpdateConversationDTO",
    "UpdateConversationRequest",
]
