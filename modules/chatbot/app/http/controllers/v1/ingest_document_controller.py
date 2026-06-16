"""Controller ingest tài liệu (NỘI BỘ — `/api/internal/v1/chatbot/documents/ingest`)."""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ...requests.v1 import IngestDocumentRequest
from ....services import IngestDocumentService


class IngestDocumentController(APIView):
    """POST `/api/internal/v1/chatbot/documents/ingest` — nhận `{document_id}`, validate rồi enqueue ingest."""

    def post(self, request: Request, *args, **kwargs) -> Response:
        form = IngestDocumentRequest(data=request.data)
        form.is_valid(raise_exception=True)  # fail → 422 shape V1 qua exception handler.
        return IngestDocumentService().ingest(form.to_dto())
