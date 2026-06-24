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

import logging
from collections.abc import Iterator

from asgiref.sync import async_to_sync
from django.db import transaction
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.sessions import BaseSessionService
from google.genai import types
from rest_framework import status as http_status
from rest_framework.response import Response

from modules.base.services import BaseService
from modules.base.supports import translate
from modules.base.transformers import TransformerService

from ...catalogs import ChatbotCatalog
from ...models import ChatConversation, ChatMessage
from ...repositories import ChatConversationRepository, ChatMessageRepository
from ...http.requests.v1 import ChatDTO
from ...transformers import ConversationTransformer, MessageTransformer
from ...adk.constants import APP_NAME
from ...adk.runner import get_runner, get_session_service
from ...adk.session import create_session_with_history
from ...adk.stream_handler import ADKStreamHandler, StreamChunk
from ...chat_pipeline.config import ChatConfig
from ...chat_pipeline.history import load_history_contents
from ...chat_pipeline.mind_map import generate_mind_map
from ...chat_pipeline.prompt import build_user_message
from ...chat_pipeline.sse import (
    delta_event,
    done_event,
    emit_chat_events,
    error_event,
    mindmap_event,
)
from ...chat_pipeline.token_quota import QuotaUnavailable, check_quota, record_usage
from ...chat_pipeline.usage import TokenUsage

logger = logging.getLogger(__name__)

# Trần ký tự transcript đưa vào Gemini khi sinh sơ đồ tư duy (giữ phần CUỐI nếu dài).
_TRANSCRIPT_MAX_CHARS = 16000


class ChatService(BaseService):
    """Điều phối 1 lượt chat (stream) + các API đọc lịch sử hội thoại."""

    def __init__(self) -> None:
        super().__init__()
        # Repo stateless → giữ làm thuộc tính của service (cũng stateless) là an toàn.
        self.conversations = ChatConversationRepository()
        self.messages = ChatMessageRepository()

    # --- Chuẩn bị (đồng bộ, có thể raise lỗi nghiệp vụ) --------------------
    def prepare(self, dto: ChatDTO) -> tuple[ChatConversation, ChatMessage, ChatMessage]:
        """Lấy/tạo hội thoại, chặn lượt trùng, lưu message user + placeholder bot.

        Toàn bộ chạy trong 1 transaction: với hội thoại có sẵn, hàng được KHOÁ
        (`SELECT ... FOR UPDATE`) nên check `has_processing` + tạo 2 message là
        atomic — hai request song song cùng hội thoại xếp hàng, không lọt 2 lượt
        xử lý song song và không để lại message USER mồ côi khi lỗi giữa chừng.
        """
        # Kiểm hạn mức token TRƯỚC khi tạo message & gọi LLM (ngoài transaction —
        # tránh giữ DB lock trong lúc gọi HTTP sang api-aio). KHÔNG tạo message mồ côi
        # khi bị chặn. Fail-CLOSED: không xác nhận được hạn mức → chặn 503 (khác hẳn
        # "hết hạn mức" 429 để FE xử lý đúng: 503 cho retry, 429 báo hết quota).
        # Ollama là LLM local (miễn phí) → KHÔNG tính hạn mức, bỏ qua check (khớp bỏ
        # record_usage ở stream()).
        if ChatConfig.from_env().llm_provider != "ollama":
            try:
                allowed = check_quota(dto.user_id)
            except QuotaUnavailable:
                self.exception(
                    translate(
                        "Hiện chưa kiểm tra được hạn mức chat. Vui lòng thử lại sau.",
                        ChatbotCatalog.TOKEN_QUOTA_UNAVAILABLE,
                    ),
                    http_status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            if not allowed:
                self.exception(
                    translate(
                        "Bạn đã dùng hết hạn mức token chat trong hôm nay. "
                        "Vui lòng thử lại vào ngày mai.",
                        ChatbotCatalog.TOKEN_QUOTA_EXCEEDED,
                    ),
                    http_status.HTTP_429_TOO_MANY_REQUESTS,
                )

        with transaction.atomic():
            conversation = self._resolve_conversation(dto)

            # Chặn gửi tiếp khi lượt trước của hội thoại còn đang xử lý (tránh đua).
            if self.messages.has_processing(conversation.id):
                self.exception(
                    translate(
                        "Hội thoại đang xử lý một câu hỏi khác, vui lòng đợi.",
                        ChatbotCatalog.CONVERSATION_PROCESSING,
                    ),
                    http_status.HTTP_409_CONFLICT,
                )

            user_message = self.messages.add_user_message(conversation, dto.question)
            assistant_message = self.messages.add_assistant_placeholder(conversation)
        return conversation, user_message, assistant_message

    def _resolve_conversation(self, dto: ChatDTO) -> ChatConversation:
        """conversation_id có → tải (khoá hàng) & kiểm tra quyền sở hữu; không → tạo mới.

        Gọi BÊN TRONG `transaction.atomic()` của `prepare` để `select_for_update`
        có hiệu lực.
        """
        if dto.conversation_id is not None:
            conversation = self.conversations.find_owned_locked(
                dto.conversation_id, dto.user_id
            )
            if conversation is None:
                # 404: "không tồn tại / không thuộc bạn" (không lộ resource của user khác).
                self.not_found(
                    translate(
                        "Hội thoại không tồn tại", ChatbotCatalog.CONVERSATION_NOT_FOUND
                    )
                )
            return conversation

        return self.conversations.create_open(dto.user_id)

    # --- Stream (sinh SSE; KHÔNG raise sau khi đã phát header) -------------
    def stream(
        self,
        conversation: ChatConversation,
        user_message: ChatMessage,
        assistant_message: ChatMessage,
        dto: ChatDTO,
    ) -> Iterator[str]:
        """Generator phát các event SSE: meta (kèm citations) → delta* → done | error.

        Shape từng event do `chat_pipeline/sse.py` quyết định (contract với FE) — ở đây chỉ
        điều phối THỨ TỰ. Citations được GỘP vào event `meta` (giữ contract cũ). Do
        agent tự quyết khi nào gọi tool, ta phát `meta` "lazy" — ngay TRƯỚC mẩu
        output đầu tiên: nếu tool đã chạy thì meta kèm citations, nếu agent trả lời
        thẳng (không search) thì meta có citations rỗng. Tool gọi lần 2+ (hiếm)
        phát thêm event `citations`.
        """
        chat_config = ChatConfig.from_env()

        answer_parts: list[str] = []
        # Reasoning (thoughts) gom song song answer — lưu vào message để FE dựng lại
        # khối thinking khi mở lại hội thoại. Khai báo NGOÀI try như answer_parts.
        thinking_parts: list[str] = []
        # Cộng dồn token cả lượt (qua mọi lần gọi LLM). Khai báo NGOÀI try để nhánh
        # except vẫn log được phần đã tiêu khi lỗi giữa chừng.
        token_usage = TokenUsage()
        session_service = get_session_service()
        session = None
        user_id = str(conversation.user_id)

        try:
            # 1) LTM — ngữ cảnh hội thoại cũ liên quan. Tự fail-safe ở tầng dưới:
            # `embed_query` nuốt lỗi gọi Gemini → None, `search()` nuốt lỗi query → "".
            ltm_context = ""
            if chat_config.ltm_enabled:
                # Lazy import — tránh circular import với services/__init__.
                from ...opensearch import ChatHistoryIndex

                ltm_context = ChatHistoryIndex(chat_config).search(
                    conversation.user_id, dto.question
                )

            # 2) Nạp lịch sử N lượt gần nhất vào session ADK (bỏ 2 message lượt này).
            history = load_history_contents(
                conversation,
                exclude_message_ids=[user_message.id, assistant_message.id],
                limit=chat_config.history_size,
            )
            session = create_session_with_history(session_service, user_id, history)

            # 2b) Đính kèm file user upload cho lượt này (đẩy media lên Gemini Files API).
            #     Fail-safe: lỗi đẩy file KHÔNG làm hỏng lượt chat (chỉ mất phần đính kèm).
            attachment_parts, attached_names = self._attach_files(
                conversation, user_message, dto.media_ids
            )

            # 3) Chạy ADK Runner (SSE) — agent tự gọi tool RAG khi cần. File đính kèm
            #    đi cùng Content dưới dạng Part (Gemini đọc native); tên file vào prompt.
            prompt = build_user_message(dto.question, ltm_context, attached_names)
            new_message = types.Content(
                role="user", parts=[types.Part(text=prompt), *attachment_parts]
            )
            handler = ADKStreamHandler()

            def _chunks() -> Iterator[StreamChunk]:
                # Gom token rồi mới bóc thành StreamChunk (handler bỏ qua usage).
                # CHỈ cộng usage ở event FINAL của mỗi lần gọi LLM (`partial` False/None):
                # event partial (mẩu stream) mang `usage_metadata` CUMULATIVE — cộng cả
                # partial sẽ đếm lặp, tổng phồng vài lần. Event final mang đúng tổng cả
                # lần gọi đó, nên cộng các final = tổng cả lượt (qua mọi vòng tool).
                for event in get_runner().run(
                    user_id=user_id,
                    session_id=session.id,
                    new_message=new_message,
                    run_config=RunConfig(streaming_mode=StreamingMode.SSE),
                ):
                    if not event.partial:
                        token_usage.add(event.usage_metadata)
                    yield from handler.process(event)

            chunks = _chunks()
            # Điều phối thứ tự SSE nằm trong chat/sse.py (giữ trọn contract 1 chỗ);
            # ở đây chỉ lấy citations cuối về để lưu message. `answer_parts` do ta sở
            # hữu nên lỗi giữa chừng vẫn lưu được phần dở ở nhánh except.
            emit = yield from emit_chat_events(
                chunks,
                conversation_id=conversation.id,
                message_id=assistant_message.id,
                answer_parts=answer_parts,
                thinking_parts=thinking_parts,
            )
            citations = emit.citations
            answer = "".join(answer_parts).strip()
            reasoning = "".join(thinking_parts).strip()

            if not answer:
                if emit.mindmap_requested:
                    # Model chỉ gọi tool vẽ sơ đồ mà quên trả lời → dùng câu xác nhận
                    # mặc định, stream luôn cho FE (live + lịch sử khớp nhau).
                    answer = (
                        "Mình đã vẽ sơ đồ tư duy cho cuộc trò chuyện này — "
                        "bạn xem ở phần sơ đồ nhé."
                    )
                    # Append vào answer_parts để nhánh except (mark_error) cũng giữ được
                    # nội dung này nếu mark_success lỗi giữa chừng (live == DB).
                    answer_parts.append(answer)
                    yield delta_event(answer)
                else:
                    # Agent không trả về text (vd chỉ gọi tool rồi dừng) → coi là lỗi.
                    raise RuntimeError("ADK agent không trả về câu trả lời")

            # Sơ đồ tư duy: sinh THEO YÊU CẦU sau khi đã có câu trả lời (token cộng vào
            # lượt qua `token_usage`). Fail-safe — lỗi sinh sơ đồ KHÔNG làm hỏng câu trả
            # lời đã xong (chỉ là thiếu sơ đồ). Phát SAU mẩu trả lời cuối, TRƯỚC `done`.
            mind_map = None
            if emit.mindmap_requested and chat_config.mindmap_enabled:
                mind_map = self._generate_mind_map_safe(
                    history,
                    dto.question,
                    answer,
                    emit.mindmap_focus,
                    chat_config,
                    token_usage,
                )
                if mind_map is not None:
                    yield mindmap_event(mind_map)

            self.messages.mark_success(
                assistant_message, answer, citations, reasoning, mind_map
            )
            self._enqueue_background(conversation, dto.question, answer)

            yield done_event(assistant_message.id, token_usage.total_tokens)
        except Exception:
            logger.exception("[chat] lỗi khi sinh câu trả lời (conv=%s)", conversation.id)
            self.messages.mark_error(
                assistant_message, "".join(answer_parts), "".join(thinking_parts).strip()
            )
            yield error_event(
                translate(
                    "Có lỗi khi tạo câu trả lời. Vui lòng thử lại.",
                    ChatbotCatalog.ANSWER_GENERATION_FAILED,
                ),
                assistant_message.id,
            )
        finally:
            # Log tổng token cả lượt (cả khi lỗi giữa chừng vẫn ra phần đã tiêu).
            logger.info(
                "[chat] token usage (conv=%s msg=%s): %s",
                conversation.id,
                assistant_message.id,
                token_usage.summary(),
            )
            # Ghi nhận token thực đã tiêu về api-aio (cộng hạn mức ngày). Đặt ở finally
            # để token vẫn được tính kể cả khi lỗi giữa chừng (LLM đã chạy là đã tốn).
            # Fail-safe sẵn trong record_usage; bỏ qua nếu chưa tiêu token nào.
            # Ollama là LLM local (miễn phí) → KHÔNG tính hạn mức (khớp bỏ check ở prepare()).
            if chat_config.llm_provider != "ollama":
                record_usage(int(conversation.user_id), token_usage.total_tokens)
            # InMemorySessionService giữ session mãi → PHẢI xoá sau mỗi lượt (tránh rò bộ nhớ).
            if session is not None:
                self._delete_session_safe(session_service, user_id, session.id)

    # --- Đính kèm file ----------------------------------------------------
    @staticmethod
    def _attach_files(
        conversation: ChatConversation,
        user_message: ChatMessage,
        media_ids: tuple[int, ...],
    ) -> tuple[list[types.Part], list[str]]:
        """Đẩy media đính kèm lên Gemini + trả `(parts, tên_file)`. FAIL-SAFE toàn cục.

        Lỗi bất kỳ (import/DB/S3/Gemini) → trả rỗng để lượt chat vẫn chạy bình thường
        (chỉ thiếu file). Fail-safe theo TỪNG file đã nằm sẵn trong `ChatAttachments`.
        """
        if not media_ids:
            return [], []
        try:
            from ...support.chat_attachments import ChatAttachments

            return ChatAttachments().attach_to_turn(
                conversation, user_message, media_ids
            )
        except Exception:
            logger.exception(
                "[chat] đính kèm file lỗi (conv=%s, bỏ qua)", conversation.id
            )
            return [], []

    # --- Sơ đồ tư duy ------------------------------------------------------
    @staticmethod
    def _generate_mind_map_safe(
        history: list[types.Content],
        question: str,
        answer: str,
        focus: str,
        chat_config: ChatConfig,
        token_usage: TokenUsage,
    ) -> dict | None:
        """Sinh sơ đồ tư duy (FAIL-SAFE) + cộng token vào lượt. Lỗi → None.

        Gọi Gemini structured-output là 1 lần gọi LLM RIÊNG (ADK không đếm) → cộng tay
        `usage` vào `token_usage` để tính đúng hạn mức (record_usage ở `finally`).
        """
        try:
            transcript = ChatService._build_transcript(history, question, answer)
            mind_map, usage = generate_mind_map(
                transcript, focus, chat_config.mindmap_model
            )
            token_usage.add(usage)  # add() bỏ qua nếu usage None.
            return mind_map
        except Exception:
            logger.exception("[chat] sinh sơ đồ tư duy lỗi (bỏ qua)")
            return None

    @staticmethod
    def _build_transcript(
        history: list[types.Content], question: str, answer: str
    ) -> str:
        """Ghép lịch sử + lượt hiện tại thành transcript text cho Gemini sinh sơ đồ."""
        lines: list[str] = []
        for content in history:
            text = " ".join(
                part.text
                for part in (content.parts or [])
                if getattr(part, "text", None)
            ).strip()
            if not text:
                continue
            role = "User" if content.role == "user" else "Assistant"
            lines.append(f"{role}: {text}")
        lines.append(f"User: {question}")
        lines.append(f"Assistant: {answer}")
        transcript = "\n".join(lines)
        # Quá dài → giữ phần CUỐI (bám lượt gần hiện tại nhất).
        if len(transcript) > _TRANSCRIPT_MAX_CHARS:
            transcript = transcript[-_TRANSCRIPT_MAX_CHARS:]
        return transcript

    # --- Session ADK ------------------------------------------------------
    @staticmethod
    def _delete_session_safe(
        session_service: BaseSessionService, user_id: str, session_id: str
    ) -> None:
        """Xoá session ADK (best-effort) — nuốt lỗi để không phá luồng response."""
        try:
            async_to_sync(session_service.delete_session)(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )
        except Exception:
            logger.debug("[chat] xoá session ADK lỗi (bỏ qua)", exc_info=True)

    # --- Enqueue nền --------------------------------------------------------
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
            from ...tasks import generate_conversation_title, index_chat_turn

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
    def list_conversations(
        self,
        user_id: int,
        page: int,
        limit: int,
        max_id: int | None = None,
        q: str | None = None,
    ) -> Response:
        """Danh sách hội thoại của user (mới nhất trước), có phân trang.

        Shape Fractal (khớp API list bên Laravel): `{data: [...], meta: {pagination}}`.
        `max_id` chốt anchor cursor để FE phân trang ổn định (xem repository).
        `q` (tuỳ chọn) lọc theo từ khoá: khớp tiêu đề HOẶC nội dung tin nhắn.
        """
        total, conversations = self.conversations.paginate_for_user(
            user_id, page, limit, max_id, q
        )
        data = TransformerService.paginator(
            TransformerService.make_paginator(conversations, total, limit, page),
            ConversationTransformer(),
        )
        return self.response_success(data)

    def rename_conversation(
        self, user_id: int, conversation_id: int, title: str
    ) -> Response:
        """Đổi tiêu đề một hội thoại của user; kiểm tra quyền sở hữu.

        Trả về hội thoại sau khi cập nhật (shape `ConversationTransformer`, envelope
        GA `{data: {...}}`). Không phải của user / không tồn tại → 404 shape V1.
        """
        conversation = self.conversations.find_owned(conversation_id, user_id)
        if conversation is None:
            self.not_found(
                translate("Hội thoại không tồn tại", ChatbotCatalog.CONVERSATION_NOT_FOUND)
            )

        conversation = self.conversations.update_model(conversation, {"title": title})
        # Khớp envelope Laravel V1 (xem DocumentService::reindex): bọc item trong
        # key `data` + kèm `message` → FE nhận `{data: {data: {...}, message, success: 1}}`.
        data = TransformerService.item(conversation, ConversationTransformer())
        return self.response_success(
            {
                "data": data,
                "message": translate(
                    "Đổi tên hội thoại thành công", ChatbotCatalog.RENAME_SUCCESS
                ),
            }
        )

    def delete_conversation(self, user_id: int, conversation_id: int) -> Response:
        """Xoá (mềm) một hội thoại của user; kiểm tra quyền sở hữu.

        Soft delete (`deleted_at`) — message con vẫn còn trong DB nhưng hội thoại
        biến mất khỏi list. Không phải của user / không tồn tại → 404 shape V1.
        """
        conversation = self.conversations.find_owned(conversation_id, user_id)
        if conversation is None:
            self.not_found(
                translate("Hội thoại không tồn tại", ChatbotCatalog.CONVERSATION_NOT_FOUND)
            )

        self.conversations.delete_model(conversation)
        return self.response_success(
            {
                "message": translate(
                    "Đã xoá hội thoại", ChatbotCatalog.DELETE_SUCCESS
                ),
            }
        )

    def list_messages(
        self, user_id: int, conversation_id: int, page: int, limit: int
    ) -> Response:
        """Danh sách tin nhắn của 1 hội thoại (cũ → mới); kiểm tra quyền sở hữu.

        Shape Fractal (khớp API list bên Laravel): `{data: [...], meta: {pagination}}`.
        """
        conversation = self.conversations.find_owned(conversation_id, user_id)
        if conversation is None:
            self.not_found(
                translate("Hội thoại không tồn tại", ChatbotCatalog.CONVERSATION_NOT_FOUND)
            )

        total, messages = self.messages.paginate_for_conversation(
            conversation.id, page, limit
        )
        data = TransformerService.paginator(
            TransformerService.make_paginator(messages, total, limit, page),
            MessageTransformer(),
        )
        return self.response_success(data)
