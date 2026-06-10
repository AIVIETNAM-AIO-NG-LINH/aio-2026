"""View nội bộ của module Chatbot — Request → DTO → Service (như module example).

Endpoint nằm dưới prefix `/api/internal/` nên đã được `VerifyInternalToken`
gate sẵn (chỉ service trong hệ AIO gọi được); view không cần check token lại.
"""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .requests import IngestDocumentRequest, RetrieveRequest
from .services import IngestDocumentService, RetrieveService


class IngestDocumentView(APIView):
    """POST documents/ingest — nhận `{document_id}`, validate rồi enqueue ingest."""

    def post(self, request: Request, *args, **kwargs) -> Response:
        form = IngestDocumentRequest(data=request.data)
        form.is_valid(raise_exception=True)  # fail → 422 shape V1 qua exception handler.
        return IngestDocumentService().ingest(form.to_dto())


class RetrieveView(APIView):
    """POST retrieve — nhận `{query, top_k?, top_n?}`, trả top_k chunk đã xếp hạng.

    Truy hồi đồng bộ (hybrid + rerank), KHÔNG sinh câu trả lời LLM — caller tự sinh.
    """

    def post(self, request: Request, *args, **kwargs) -> Response:
        form = RetrieveRequest(data=request.data)
        form.is_valid(raise_exception=True)  # fail → 422 shape V1 qua exception handler.
        return RetrieveService().retrieve(form.to_dto())
