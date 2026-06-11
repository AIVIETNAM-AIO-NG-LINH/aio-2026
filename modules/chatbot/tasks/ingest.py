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
    Pipeline tự đánh status PENDING→READY/FAILED và nuốt lỗi (log) nên task không
    raise — phù hợp Phase 1 (chưa cấu hình retry).
    """
    from ..pipelines.ingest import run_ingest_pipeline

    logger.info("[ingest_document] nhận document_id=%s", document_id)
    run_ingest_pipeline(document_id)
