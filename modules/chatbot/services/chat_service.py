"""Nghiệp vụ luồng chat — chạy qua Google ADK (Agent + tool RAG) + lưu hội thoại.

Luồng 1 lượt chat (`prepare` đồng bộ → `stream` sinh SSE):
  prepare():  lấy/tạo conversation (theo user) → chặn lượt đang xử lý (409) →
              lưu message USER + tạo placeholder ASSISTANT (PROCESSING).
  stream():   LTM (fail-safe) → nạp lịch sử vào session ADK → chạy Runner (SSE):
              agent tự gọi tool `search_knowledge_base` để lấy ngữ cảnh → stream câu
              trả lời → cập nhật message ASSISTANT → enqueue Celery (tiêu đề + LTM).

Citations được GỘP vào event `meta` (giữ contract cũ): meta phát "lazy" ngay trước
mẩu output đầu — kèm citations nếu agent đã gọi tool. SSE: meta → delta* → done | error.

`prepare` raise `ApiException` cho lỗi nghiệp vụ (handler trả JSON đúng shape V1)
VÌ chạy TRƯỚC khi gửi header. Lỗi trong `stream` (đã gửi header) thì KHÔNG raise —
phát event `error` và đánh dấu message ERROR.

Ngoài ra: list hội thoại + list tin nhắn theo user (cho FE dựng lại lịch sử).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

from asgiref.sync import async_to_sync
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from rest_framework import status as http_status
from rest_framework.response import Response

from modules.base.services import BaseService

from ..enums import ConversationStatus, MessageRole, MessageStatus
from ..models import ChatConversation, ChatMessage
from ..requests import ChatDTO
from .chat.adk.constants import APP_NAME
from .chat.adk.runner import get_runner, get_session_service
from .chat.adk.session import create_session_with_history
from .chat.adk.stream_handler import ADKStreamHandler
from .chat.config import ChatConfig
from .chat.history import load_history_contents
from .chat.ltm import ChatHistoryIndex
from .chat.prompt import build_user_message

logger = logging.getLogger(__name__)


def _sse(event: dict) -> str:
    """Đóng gói 1 event thành dòng SSE (`data: <json>\\n\\n`), giữ Unicode."""
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"


def _fmt_dt(value) -> str | None:
    """Datetime → 'Y-m-d H:i:s' (đồng bộ DATETIME_FORMAT V1); None giữ None."""
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


class ChatService(BaseService):
    """Điều phối 1 lượt chat (stream) + các API đọc lịch sử hội thoại."""

    # --- Chuẩn bị (đồng bộ, có thể raise lỗi nghiệp vụ) --------------------
    def prepare(self, dto: ChatDTO) -> tuple[ChatConversation, ChatMessage, ChatMessage]:
        """Lấy/tạo hội thoại, chặn lượt trùng, lưu message user + placeholder bot."""
        conversation = self._resolve_conversation(dto)

        # Chặn gửi tiếp khi lượt trước của hội thoại còn đang xử lý (tránh đua).
        if ChatMessage.objects.filter(
            conversation_id=conversation.id, status=MessageStatus.PROCESSING
        ).exists():
            self.exception(
                "Hội thoại đang xử lý một câu hỏi khác, vui lòng đợi.",
                http_status.HTTP_409_CONFLICT,
            )

        user_message = ChatMessage.objects.create(
            conversation=conversation,
            role=MessageRole.USER,
            content=dto.question,
            status=MessageStatus.SUCCESS,
        )
        assistant_message = ChatMessage.objects.create(
            conversation=conversation,
            role=MessageRole.ASSISTANT,
            content="",
            status=MessageStatus.PROCESSING,
        )
        return conversation, user_message, assistant_message

    def _resolve_conversation(self, dto: ChatDTO) -> ChatConversation:
        """conversation_id có → tải & kiểm tra quyền sở hữu; không → tạo mới."""
        if dto.conversation_id is not None:
            conversation = ChatConversation.objects.filter(
                id=dto.conversation_id, user_id=dto.user_id
            ).first()
            if conversation is None:
                # 410 Gone: convention nội bộ cho "không tồn tại / không thuộc bạn".
                self.code_gone("Hội thoại không tồn tại")
            return conversation

        return ChatConversation.objects.create(
            user_id=dto.user_id,
            status=ConversationStatus.OPEN,
        )

    # --- Stream (sinh SSE; KHÔNG raise sau khi đã phát header) -------------
    def stream(
        self,
        conversation: ChatConversation,
        user_message: ChatMessage,
        assistant_message: ChatMessage,
        dto: ChatDTO,
    ) -> Iterator[str]:
        """Generator phát các event SSE: meta (kèm citations) → delta* → done | error.

        Citations được GỘP vào event `meta` (giữ contract cũ). Do agent tự quyết khi
        nào gọi tool, ta phát `meta` "lazy" — ngay TRƯỚC mẩu output đầu tiên: nếu tool
        đã chạy thì meta kèm citations, nếu agent trả lời thẳng (không search) thì meta
        có citations rỗng. Tool gọi lần 2+ (hiếm) phát thêm event `citations`.
        """
        chat_config = ChatConfig.from_env()

        answer_parts: list[str] = []
        citations: list[dict] = []
        meta_sent = False
        session_service = get_session_service()
        session = None
        user_id = str(conversation.user_id)

        def _meta_event() -> str:
            return _sse(
                {
                    "type": "meta",
                    "conversation_id": conversation.id,
                    "message_id": assistant_message.id,
                    "citations": citations,
                }
            )

        try:
            # 1) LTM — ngữ cảnh hội thoại cũ liên quan (fail-safe → rỗng).
            ltm_context = ""
            if chat_config.ltm_enabled:
                try:
                    ltm_context = ChatHistoryIndex(chat_config).search(
                        conversation.user_id, dto.question
                    )
                except Exception:
                    logger.exception("[chat] LTM search lỗi (bỏ qua)")

            # 2) Nạp lịch sử N lượt gần nhất vào session ADK (bỏ 2 message lượt này).
            history = load_history_contents(
                conversation,
                exclude_message_ids=[user_message.id, assistant_message.id],
                limit=chat_config.history_size,
            )
            session = create_session_with_history(session_service, user_id, history)

            # 3) Chạy ADK Runner (SSE) — agent tự gọi tool RAG khi cần.
            prompt = build_user_message(dto.question, ltm_context)
            new_message = types.Content(role="user", parts=[types.Part(text=prompt)])
            handler = ADKStreamHandler()
            for event in get_runner().run(
                user_id=user_id,
                session_id=session.id,
                new_message=new_message,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            ):
                for out in handler.process(event):
                    kind = out["kind"]
                    if kind == "citations":
                        citations = out["citations"]
                        # Lần đầu → gộp vào meta; lần sau → event citations riêng.
                        if not meta_sent:
                            yield _meta_event()
                            meta_sent = True
                        else:
                            yield _sse({"type": "citations", "citations": citations})
                    elif kind == "text":
                        if not meta_sent:  # meta LUÔN đứng trước delta đầu tiên.
                            yield _meta_event()
                            meta_sent = True
                        answer_parts.append(out["text"])
                        yield _sse({"type": "delta", "content": out["text"]})
                    elif kind == "thinking":
                        if not meta_sent:
                            yield _meta_event()
                            meta_sent = True
                        yield _sse({"type": "thinking", "content": out["text"]})

            answer = "".join(answer_parts).strip()
            if not answer:
                # Agent không trả về text (vd chỉ gọi tool rồi dừng) → coi là lỗi.
                raise RuntimeError("ADK agent không trả về câu trả lời")

            self._finalize_success(assistant_message, answer, citations)
            self._enqueue_background(conversation, dto.question, answer)

            yield _sse(
                {
                    "type": "done",
                    "status": "success",
                    "message_id": assistant_message.id,
                }
            )
        except Exception:
            logger.exception("[chat] lỗi khi sinh câu trả lời (conv=%s)", conversation.id)
            self._finalize_error(assistant_message, "".join(answer_parts))
            yield _sse(
                {
                    "type": "error",
                    "status": "error",
                    "message": "Có lỗi khi tạo câu trả lời. Vui lòng thử lại.",
                    "message_id": assistant_message.id,
                }
            )
        finally:
            # InMemorySessionService giữ session mãi → PHẢI xoá sau mỗi lượt (tránh rò bộ nhớ).
            if session is not None:
                self._delete_session_safe(session_service, user_id, session.id)

    # --- Session ADK ------------------------------------------------------
    @staticmethod
    def _delete_session_safe(session_service, user_id: str, session_id: str) -> None:
        """Xoá session ADK (best-effort) — nuốt lỗi để không phá luồng response."""
        try:
            async_to_sync(session_service.delete_session)(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )
        except Exception:
            logger.debug("[chat] xoá session ADK lỗi (bỏ qua)", exc_info=True)

    # --- Cập nhật message + enqueue nền -----------------------------------
    @staticmethod
    def _finalize_success(
        assistant_message: ChatMessage, answer: str, citations: list[dict]
    ) -> None:
        assistant_message.content = answer
        assistant_message.citations = citations
        assistant_message.status = MessageStatus.SUCCESS
        assistant_message.save(
            update_fields=["content", "citations", "status", "updated_at"]
        )

    @staticmethod
    def _finalize_error(assistant_message: ChatMessage, partial: str) -> None:
        assistant_message.content = partial
        assistant_message.status = MessageStatus.ERROR
        assistant_message.save(update_fields=["content", "status", "updated_at"])

    @staticmethod
    def _enqueue_background(
        conversation: ChatConversation, question: str, answer: str
    ) -> None:
        """Đẩy việc nền qua Celery: sinh tiêu đề (nếu chưa có) + lưu LTM.

        FAIL-SAFE: lỗi enqueue (vd broker redis chết) chỉ log — KHÔNG để nổi lên
        làm hỏng lượt chat đã sinh thành công (tránh đánh nhầm message thành ERROR).
        """
        if not answer:
            return
        try:
            from ..tasks import generate_conversation_title, index_chat_turn

            if conversation.title is None:
                generate_conversation_title.delay(conversation.id, question, answer)
            index_chat_turn.delay(
                conversation.id, conversation.user_id, question, answer
            )
        except Exception:
            logger.exception(
                "[chat] enqueue việc nền lỗi (conv=%s, bỏ qua)", conversation.id
            )

    # --- API đọc lịch sử ---------------------------------------------------
    def list_conversations(self, user_id: int, page: int, limit: int) -> Response:
        """Danh sách hội thoại của user (mới nhất trước), có phân trang."""
        qs = ChatConversation.objects.filter(user_id=user_id).order_by("-id")
        total = qs.count()
        offset = (page - 1) * limit
        items = [
            {
                "id": c.id,
                "title": c.title,
                "status": c.status,
                "created_at": _fmt_dt(c.created_at),
                "updated_at": _fmt_dt(c.updated_at),
            }
            for c in qs[offset : offset + limit]
        ]
        return self.response_success(
            {"page": page, "limit": limit, "total": total, "items": items}
        )

    def list_messages(
        self, user_id: int, conversation_id: int, page: int, limit: int
    ) -> Response:
        """Danh sách tin nhắn của 1 hội thoại (cũ → mới); kiểm tra quyền sở hữu."""
        conversation = ChatConversation.objects.filter(
            id=conversation_id, user_id=user_id
        ).first()
        if conversation is None:
            self.code_gone("Hội thoại không tồn tại")

        qs = ChatMessage.objects.filter(conversation_id=conversation.id).order_by("id")
        total = qs.count()
        offset = (page - 1) * limit
        items = [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "citations": m.citations,
                "status": m.status,
                "created_at": _fmt_dt(m.created_at),
            }
            for m in qs[offset : offset + limit]
        ]
        return self.response_success(
            {"page": page, "limit": limit, "total": total, "items": items}
        )
