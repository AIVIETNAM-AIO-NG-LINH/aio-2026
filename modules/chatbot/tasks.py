"""Celery task của module Chatbot — được `app.autodiscover_tasks()` nạp tự động.

Phase 1: `ingest_document` chạy pipeline RAG thật — tải file gốc từ S3, trích
text bằng Gemini, chunk + embed, rồi index parent-child vào OpenSearch. Toàn bộ
nghiệp vụ nằm ở `services.rag.pipeline`; task chỉ là vỏ Celery mỏng.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="chatbot.ingest_document")
def ingest_document(document_id: int) -> None:
    """Chạy pipeline RAG cho `document_id` (= chatbot_documents.id).

    Import pipeline bên trong task để tránh nạp Django model/app registry lúc
    module được autodiscover (task chạy trong worker, lúc đó Django đã sẵn sàng).
    Pipeline tự đánh status PENDING→READY/FAILED và nuốt lỗi (log) nên task không
    raise — phù hợp Phase 1 (chưa cấu hình retry).
    """
    from .services.rag.pipeline import run_ingest_pipeline

    logger.info("[ingest_document] nhận document_id=%s", document_id)
    run_ingest_pipeline(document_id)


@shared_task(name="chatbot.generate_conversation_title")
def generate_conversation_title(conversation_id: int, question: str, answer: str) -> None:
    """Sinh tiêu đề ngắn cho hội thoại từ câu hỏi + trả lời đầu tiên (Gemini Flash).

    Chỉ set khi `title` còn None (idempotent — chạy đua nhiều lượt vẫn an toàn).
    Fail-safe: lỗi LLM/DB chỉ log, không raise (tiêu đề là phụ trợ).
    """
    from .models import ChatConversation
    from .services.chat.config import ChatConfig
    from .services.chat.generator import generate_text
    from .services.rag.config import GeminiConfig

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
        title = generate_text(prompt, chat_config.title_model, GeminiConfig.from_env())
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
    from .services.chat.config import ChatConfig
    from .services.chat.ltm import ChatHistoryIndex
    from .services.rag.config import GeminiConfig, OpenSearchConfig

    chat_config = ChatConfig.from_env()
    if not chat_config.ltm_enabled:
        return
    try:
        ChatHistoryIndex(
            OpenSearchConfig.from_env(), GeminiConfig.from_env(), chat_config
        ).index_turn(conversation_id, user_id, question, answer)
    except Exception:
        logger.exception("[ltm] lỗi index lượt hội thoại conv=%s (bỏ qua)", conversation_id)
