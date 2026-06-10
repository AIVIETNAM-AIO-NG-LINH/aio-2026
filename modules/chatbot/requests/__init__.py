"""Request layer của module Chatbot — re-export để view import gọn."""

from .ingest_document_request import IngestDocumentDTO, IngestDocumentRequest
from .retrieve_request import RetrieveDTO, RetrieveRequest

__all__ = [
    "IngestDocumentDTO",
    "IngestDocumentRequest",
    "RetrieveDTO",
    "RetrieveRequest",
]
