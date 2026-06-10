"""Celery task của module Chatbot — được `app.autodiscover_tasks()` nạp tự động.

Phase 0: `ingest_document` mới chỉ DỰNG ĐƯỜNG ỐNG — nhận id, đánh dấu tài liệu
`PENDING` (chờ xử lý) và log chỗ sẽ chạy pipeline RAG ở Phase sau. CHƯA parse/
chunk/embed gì cả.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="chatbot.ingest_document")
def ingest_document(document_id: int) -> None:
    """STUB pipeline ingest: set status='PENDING' rồi nhường cho Phase sau.

    Import model bên trong task để tránh nạp Django app registry lúc module được
    autodiscover (task chạy trong worker, lúc đó Django đã sẵn sàng).
    """
    # Import nội bộ: chỉ cần khi task thực sự chạy (worker đã bootstrap Django).
    from .enums import DocumentStatus
    from .models import ChatbotDocument

    logger.info("[ingest_document] nhận document_id=%s", document_id)

    # `managed = False` ở model nhưng ai-aio ĐƯỢC phép ghi DATA lên bảng dùng chung.
    updated = ChatbotDocument.objects.filter(pk=document_id).update(
        status=DocumentStatus.PENDING,
    )
    if not updated:
        # Có thể đã bị xoá sau khi enqueue — không raise, chỉ cảnh báo.
        logger.warning(
            "[ingest_document] document_id=%s không còn tồn tại, bỏ qua", document_id
        )
        return

    logger.info(
        "[ingest_document] document_id=%s -> PENDING. TODO: chạy pipeline RAG (Phase 1)",
        document_id,
    )
