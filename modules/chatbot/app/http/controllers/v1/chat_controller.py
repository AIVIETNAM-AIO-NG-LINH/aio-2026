"""Controller CÔNG KHAI của luồng chat (`/api/v1/chatbot/...`): chat SSE + hội thoại/tin nhắn.

Gộp 1 ViewSet nhiều action (kiểu controller Laravel) — urls/public.py map
từng path vào từng action qua ``ChatController.as_view({"post": "chat"})`` v.v.
APIView thường không gộp được vì 2 endpoint list đều là GET (chỉ khác URL).
"""

from __future__ import annotations

from django.http import StreamingHttpResponse
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.parsers import BaseParser
from rest_framework.renderers import BaseRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from modules.base.app.singletons import CurrentUser
from modules.base.app.supports import parse_pagination

from ...requests.v1 import ChatRequest, UpdateConversationRequest
from ....services import ChatService

# Instance dùng chung cho cả ViewSet — ChatService stateless (không giữ state theo
# request) nên share 1 instance là an toàn, khỏi khởi tạo lại mỗi request.
chat_service = ChatService()


class _IgnoreClientNegotiation(BaseContentNegotiation):
    """Bỏ qua header `Accept` của client — luôn chọn renderer đầu (JSONRenderer).

    Cần cho action chat: EventSource trình duyệt gửi `Accept: text/event-stream`,
    mà project chỉ cấu hình JSONRenderer → DRF sẽ 406 ngay ở content-negotiation.
    Thân SSE trả qua `StreamingHttpResponse` (không dùng renderer); response LỖI
    (422/409/404) vẫn render JSON đúng shape V1. Các action list trả JSON nên
    renderer đầu cũng là lựa chọn đúng — áp cho cả class vô hại.
    """

    def select_parser(self, request: Request, parsers: list[BaseParser]) -> BaseParser:
        return parsers[0]

    def select_renderer(
        self, request: Request, renderers: list[BaseRenderer], format_suffix: str | None = None
    ) -> tuple[BaseRenderer, str]:
        return (renderers[0], renderers[0].media_type)


class ChatController(ViewSet):
    """Cụm endpoint chat của người dùng cuối — 3 action trên 1 class.

    `user_id` mọi action lấy từ ``CurrentUser`` (gate `ensure_authenticated` ở urls
    populate, thiếu header đã 401 từ trước khi tới đây).
    """

    content_negotiation_class = _IgnoreClientNegotiation

    def chat(self, request: Request) -> StreamingHttpResponse:
        """POST `/api/v1/chatbot/chat` — hỏi đáp RAG, trả câu trả lời dạng SSE streaming.

        Body: `{ question, conversation_id?, top_k? }`. Chạy qua Google ADK
        (agent + tool RAG). Trả `text/event-stream`:
        meta (conversation_id + citations) → delta* → done | error.
        """
        user_id = CurrentUser().get_id()
        form = ChatRequest(data=request.data)
        form.is_valid(raise_exception=True)  # fail → 422 shape V1 qua exception handler.
        dto = form.to_dto(user_id)

        # prepare đồng bộ — lỗi nghiệp vụ (409/404) raise TRƯỚC khi phát header.
        conversation, user_message, assistant_message = chat_service.prepare(dto)

        response = StreamingHttpResponse(
            chat_service.stream(conversation, user_message, assistant_message, dto),
            content_type="text/event-stream",
        )
        # Tắt buffering (nginx + client) để token tới ngay khi sinh.
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    def conversations(self, request: Request) -> Response:
        """GET `/api/v1/chatbot/conversations` — danh sách hội thoại của user (phân trang).

        Nhận thêm query `max_id` (tuỳ chọn) làm anchor cursor để phân trang ổn định:
        FE bắt id lớn nhất ở lần load đầu rồi gửi kèm mọi trang sau, hội thoại mới
        tạo không đẩy lệch trang. `max_id` sai kiểu/không phải số dương → bỏ qua.

        Query `q` (tuỳ chọn) lọc theo từ khoá: khớp tiêu đề HOẶC nội dung tin nhắn;
        rỗng/chỉ khoảng trắng → bỏ qua (trả list thường).
        """
        user_id = CurrentUser().get_id()
        page, limit = parse_pagination(request)
        max_id = self._parse_max_id(request)
        q = (request.query_params.get("q") or "").strip() or None
        return chat_service.list_conversations(user_id, page, limit, max_id, q)

    @staticmethod
    def _parse_max_id(request: Request) -> int | None:
        """Đọc `max_id` từ query — số nguyên dương, ngược lại None (bỏ qua anchor)."""
        try:
            value = int(request.query_params.get("max_id", ""))
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def messages(self, request: Request, conversation_id: int) -> Response:
        """GET `/api/v1/chatbot/conversations/<id>/messages` — tin nhắn của 1 hội thoại (phân trang)."""
        user_id = CurrentUser().get_id()
        page, limit = parse_pagination(request)
        return chat_service.list_messages(user_id, conversation_id, page, limit)

    def rename(self, request: Request, conversation_id: int) -> Response:
        """PATCH `/api/v1/chatbot/conversations/<id>` — đổi tiêu đề hội thoại.

        Body `{ title }`. Sai shape → 422; không phải của user → 404 (đều shape V1).
        """
        user_id = CurrentUser().get_id()
        form = UpdateConversationRequest(data=request.data)
        form.is_valid(raise_exception=True)
        dto = form.to_dto()
        return chat_service.rename_conversation(user_id, conversation_id, dto.title)

    def destroy(self, request: Request, conversation_id: int) -> Response:
        """DELETE `/api/v1/chatbot/conversations/<id>` — xoá (mềm) hội thoại.

        Không phải của user → 404 (shape V1).
        """
        user_id = CurrentUser().get_id()
        return chat_service.delete_conversation(user_id, conversation_id)
