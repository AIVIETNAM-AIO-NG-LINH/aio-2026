"""Task ingest tài liệu — vỏ Celery mỏng quanh `pipelines.ingest`.

Phase 1: `ingest_document` chạy pipeline RAG thật — tải file gốc từ S3, trích
text bằng Gemini, chunk + embed, rồi index parent-child vào OpenSearch.
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

    Pipeline tự đánh status PENDING→READY/FAILED, chỉ try HẸP quanh các bước
    thật sự có thể hỏng (S3/Gemini/OpenSearch). Lỗi code ngoài các bước đó
    propagate đến đây — lưới an toàn CUỐI: log đủ traceback (chỉ rõ vị trí bug)
    + set FAILED để tài liệu không kẹt PENDING, và không raise lại để tránh
    worker retry vô hạn ở Phase 1 (chưa cấu hình retry).
    """
    from ..enums import DocumentStatus
    from ..pipelines.ingest import run_ingest_pipeline
    from ..repositories import ChatbotDocumentRepository

    logger.info("[ingest_document] nhận document_id=%s", document_id)
    try:
        run_ingest_pipeline(document_id)
    except Exception:
        logger.exception(
            "[ingest_document] document_id=%s lỗi bất ngờ ngoài các bước đã bọc -> FAILED",
            document_id,
        )
        try:
            ChatbotDocumentRepository().set_status(document_id, DocumentStatus.FAILED)
        except Exception:
            logger.exception(
                "[ingest_document] document_id=%s không set được FAILED", document_id
            )
