"""Task phụ trợ sau mỗi lượt chat — chạy nền, fail-safe (lỗi chỉ log).

- `generate_conversation_title` — sinh tiêu đề ngắn cho hội thoại đầu tiên.
- `index_chat_turn`             — lưu lượt hỏi-đáp vào LTM (OpenSearch).
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="chatbot.generate_conversation_title")
def generate_conversation_title(conversation_id: int, question: str, answer: str) -> None:
    """Sinh tiêu đề ngắn cho hội thoại từ câu hỏi + trả lời đầu tiên (Gemini Flash).

    Chỉ set khi `title` còn None (idempotent — chạy đua nhiều lượt vẫn an toàn).
    Fail-safe: lỗi LLM/DB chỉ log, không raise (tiêu đề là phụ trợ).
    """
    from ..repositories import ChatConversationRepository
    from ..chat_pipeline.config import ChatConfig
    from ..chat_pipeline.generator import generate_text

    chat_config = ChatConfig.from_env()
    if not chat_config.title_enabled:
        return

    conversations = ChatConversationRepository()
    conversation = conversations.find(conversation_id)
    if conversation is None or conversation.title is not None:
        return

    prompt = (
        "Write a SHORT title (max 60 characters) for the following conversation. "
        "Return ONLY the title - no quotes, no explanation. "
        "Use the same language as the user's question.\n\n"
        f"User: {question}\nAssistant: {answer}"
    )
    try:
        title = generate_text(prompt, chat_config.title_model)
    except Exception:
        logger.exception("[title] lỗi sinh tiêu đề conv=%s (bỏ qua)", conversation_id)
        return

    title = title.strip().strip('"').strip()[:255]
    if not title:
        return
    # Set có điều kiện để không đè nếu lượt khác vừa ghi xong (idempotent).
    won = conversations.set_title_if_empty(conversation_id, title)
    logger.info("[title] conv=%s → %r (won=%s)", conversation_id, title, won)

    # CHỈ lượt thắng ghi DB mới đẩy realtime (tránh push trùng khi nhiều lượt đua).
    # Push riêng cho chủ hội thoại → FE cập nhật tiêu đề ở sidebar tức thì, khỏi poll.
    # Fail-safe: RealtimeClient tự nuốt lỗi, không raise lên task.
    if won:
        from modules.base.clients.realtime_client import realtime_client
        from ..enums.realtime_event import RealtimeEvent

        realtime_client().to_user(
            conversation.user_id,
            RealtimeEvent.CONVERSATION_TITLE.value,
            {"id": conversation_id, "title": title},
        )


@shared_task(name="chatbot.index_chat_turn")
def index_chat_turn(
    conversation_id: int, user_id: int, question: str, answer: str
) -> None:
    """Lưu 1 lượt hỏi-đáp vào LTM (OpenSearch) để truy hồi ở các hội thoại sau.

    Fail-safe: lỗi embed/OpenSearch chỉ log, không raise (LTM là phụ trợ).
    """
    from ..chat_pipeline.config import ChatConfig
    from ..opensearch import ChatHistoryIndex

    chat_config = ChatConfig.from_env()
    if not chat_config.ltm_enabled:
        return
    try:
        ChatHistoryIndex(chat_config).index_turn(
            conversation_id, user_id, question, answer
        )
    except Exception:
        logger.exception("[ltm] lỗi index lượt hội thoại conv=%s (bỏ qua)", conversation_id)
