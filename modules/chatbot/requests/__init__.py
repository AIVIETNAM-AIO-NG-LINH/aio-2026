"""Request layer của module Chatbot — re-export để view import gọn."""

from .ingest_document_request import IngestDocumentDTO, IngestDocumentRequest

__all__ = ["IngestDocumentDTO", "IngestDocumentRequest"]
