"""View CÔNG KHAI của luồng chat (`/api/chatbot/...`): chat SSE + hội thoại/tin nhắn."""

from __future__ import annotations

from django.http import StreamingHttpResponse
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..requests import ChatRequest
from ..services import ChatService
from ._helpers import parse_pagination, resolve_user_id


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


class ChatView(APIView):
    """POST chat — hỏi đáp RAG, trả câu trả lời dạng SSE streaming.

    Body: `{ question, conversation_id?, top_k? }`. `user_id` lấy từ header. Chạy
    qua Google ADK (agent + tool RAG). Trả `text/event-stream`:
    meta (conversation_id + citations) → delta* → done | error.
    """

    content_negotiation_class = _IgnoreClientNegotiation

    def post(self, request: Request, *args, **kwargs) -> StreamingHttpResponse:
        user_id = resolve_user_id(request)
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
        user_id = resolve_user_id(request)
        page, limit = parse_pagination(request)
        return ChatService().list_conversations(user_id, page, limit)


class MessageListView(APIView):
    """GET conversations/<id>/messages — tin nhắn của 1 hội thoại (phân trang)."""

    def get(self, request: Request, conversation_id: int, *args, **kwargs) -> Response:
        user_id = resolve_user_id(request)
        page, limit = parse_pagination(request)
        return ChatService().list_messages(user_id, conversation_id, page, limit)
