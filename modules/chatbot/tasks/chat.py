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
    from ..models import ChatConversation
    from ..services.chat.config import ChatConfig
    from ..services.chat.generator import generate_text

    chat_config = ChatConfig.from_env()
    if not chat_config.title_enabled:
        return

    conversation = ChatConversation.objects.filter(id=conversation_id).first()
    if conversation is None or conversation.title is not None:
        return

    prompt = (
        "Đặt một tiêu đề NGẮN (tối đa 60 ký tự) cho cuộc hội thoại sau. "
        "Chỉ trả về tiêu đề, không thêm dấu ngoặc hay giải thích. "
        "Dùng cùng ngôn ngữ với câu hỏi.\n\n"
        f"Người dùng: {question}\nTrợ lý: {answer}"
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
    ChatConversation.objects.filter(id=conversation_id, title__isnull=True).update(
        title=title
    )
    logger.info("[title] conv=%s → %r", conversation_id, title)


@shared_task(name="chatbot.index_chat_turn")
def index_chat_turn(
    conversation_id: int, user_id: int, question: str, answer: str
) -> None:
    """Lưu 1 lượt hỏi-đáp vào LTM (OpenSearch) để truy hồi ở các hội thoại sau.

    Fail-safe: lỗi embed/OpenSearch chỉ log, không raise (LTM là phụ trợ).
    """
    from ..services.chat.config import ChatConfig
    from ..services.chat.ltm import ChatHistoryIndex

    chat_config = ChatConfig.from_env()
    if not chat_config.ltm_enabled:
        return
    try:
        ChatHistoryIndex(chat_config).index_turn(
            conversation_id, user_id, question, answer
        )
    except Exception:
        logger.exception("[ltm] lỗi index lượt hội thoại conv=%s (bỏ qua)", conversation_id)
