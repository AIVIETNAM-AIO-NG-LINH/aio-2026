"""View của module Chatbot.

Hai nhóm endpoint:
  - NỘI BỘ (`/api/internal/chatbot/...`): ingest + retrieve — gate bằng
    `VerifyInternalToken` (chỉ service trong hệ AIO gọi).
  - CÔNG KHAI (`/api/chatbot/...`): luồng chat của người dùng cuối. nginx đã
    verify token (qua api-aio) và forward danh tính user xuống header
    `X-Auth-User-Id`; view đọc header này để biết user là ai (không tự auth lại).
"""

from __future__ import annotations

from django.http import StreamingHttpResponse
from rest_framework import status as http_status
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.base.exceptions import ApiException


class _IgnoreClientNegotiation(BaseContentNegotiation):
    """Bỏ qua header `Accept` của client — luôn chọn renderer đầu (JSONRenderer).

    Cần cho endpoint chat: EventSource trình duyệt gửi `Accept: text/event-stream`,
    mà project chỉ cấu hình JSONRenderer → DRF sẽ 406 ngay ở content-negotiation.
    Thân SSE trả qua `StreamingHttpResponse` (không dùng renderer); response LỖI
    (422/409/410) vẫn render JSON đúng shape V1.
    """

    def select_parser(self, request, parsers):
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix=None):
        return (renderers[0], renderers[0].media_type)

from .requests import ChatRequest, IngestDocumentRequest, RetrieveRequest
from .services import ChatService, IngestDocumentService, RetrieveService


def _resolve_user_id(request: Request) -> int:
    """Lấy user_id từ header `X-Auth-User-Id` (nginx set). Thiếu/sai → 401."""
    raw = request.headers.get("X-Auth-User-Id")
    if not raw:
        raise ApiException(
            "Thiếu danh tính người dùng (X-Auth-User-Id).",
            http_status.HTTP_401_UNAUTHORIZED,
        )
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ApiException(
            "X-Auth-User-Id không hợp lệ.", http_status.HTTP_401_UNAUTHORIZED
        )


def _parse_pagination(request: Request) -> tuple[int, int]:
    """Đọc `page`/`limit` từ query (default 1/20, limit tối đa 100)."""

    def _int(name: str, default: int) -> int:
        try:
            return int(request.query_params.get(name, default))
        except (TypeError, ValueError):
            return default

    page = max(1, _int("page", 1))
    limit = max(1, min(_int("limit", 20), 100))
    return page, limit


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


class ChatView(APIView):
    """POST chat — hỏi đáp RAG, trả câu trả lời dạng SSE streaming.

    Body: `{ question, conversation_id?, top_k? }`. `user_id` lấy từ header. Chạy
    qua Google ADK (agent + tool RAG). Trả `text/event-stream`:
    meta (conversation_id + citations) → delta* → done | error.
    """

    content_negotiation_class = _IgnoreClientNegotiation

    def post(self, request: Request, *args, **kwargs) -> StreamingHttpResponse:
        user_id = _resolve_user_id(request)
        form = ChatRequest(data=request.data)
        form.is_valid(raise_exception=True)  # fail → 422 shape V1 qua exception handler.
        dto = form.to_dto(user_id)

        service = ChatService()
        # prepare đồng bộ — lỗi nghiệp vụ (409/410) raise TRƯỚC khi phát header.
        conversation, user_message, assistant_message = service.prepare(dto)

        response = StreamingHttpResponse(
            service.stream(conversation, user_message, assistant_message, dto),
            content_type="text/event-stream",
        )
        # Tắt buffering (nginx + client) để token tới ngay khi sinh.
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class ConversationListView(APIView):
    """GET conversations — danh sách hội thoại của user (phân trang)."""

    def get(self, request: Request, *args, **kwargs) -> Response:
        user_id = _resolve_user_id(request)
        page, limit = _parse_pagination(request)
        return ChatService().list_conversations(user_id, page, limit)


class MessageListView(APIView):
    """GET conversations/<id>/messages — tin nhắn của 1 hội thoại (phân trang)."""

    def get(self, request: Request, conversation_id: int, *args, **kwargs) -> Response:
        user_id = _resolve_user_id(request)
        page, limit = _parse_pagination(request)
        return ChatService().list_messages(user_id, conversation_id, page, limit)
