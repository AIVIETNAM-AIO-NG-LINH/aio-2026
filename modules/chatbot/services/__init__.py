"""Service layer của module Chatbot — re-export để view import gọn."""

from .ingest_service import IngestDocumentService

__all__ = ["IngestDocumentService"]
