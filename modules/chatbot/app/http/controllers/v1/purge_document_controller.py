"""Controller purge tài liệu (NỘI BỘ — `/api/internal/v1/chatbot/documents/purge`)."""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ...requests.v1 import PurgeDocumentRequest
from ....services import PurgeDocumentService


class PurgeDocumentController(APIView):
    """POST `/api/internal/v1/chatbot/documents/purge` — nhận `{document_id}`, validate rồi enqueue purge."""

    def post(self, request: Request, *args, **kwargs) -> Response:
        form = PurgeDocumentRequest(data=request.data)
        form.is_valid(raise_exception=True)  # fail → 422 shape V1 qua exception handler.
        return PurgeDocumentService().purge(form.to_dto())
