"""Interface cho service layer v1 của Chatbot — re-export để import gọn."""

from .ingest_service import IngestDocumentServiceInterface
from .purge_service import PurgeDocumentServiceInterface

__all__ = ["IngestDocumentServiceInterface", "PurgeDocumentServiceInterface"]
