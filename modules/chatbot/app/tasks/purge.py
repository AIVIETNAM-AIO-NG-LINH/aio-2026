"""Task purge tài liệu — dọn sạch dấu vết OpenSearch/KG của tài liệu đã gỡ.

api-aio xoá (soft-delete) bản ghi `chatbot_documents` rồi báo sang đây để purge.
KHÁC ingest (đọc DB + tải file): purge chỉ cần `document_id` — mọi index đều
khoá theo document_id nên không cần đọc lại DB (bản ghi đã soft-delete).

Dọn 3 nơi, mỗi nơi try ĐỘC LẬP để 1 chỗ hỏng không chặn các chỗ còn lại:
  1) rag-index    — QUAN TRỌNG NHẤT: nếu còn, chatbot vẫn truy hồi nội dung
                    tài liệu đã xoá (lỗi đúng/riêng tư). `_retry_transient`
                    trong indexer tự thử lại lỗi tạm thời; thất bại cuối → log.
  2) summary index — fail-safe, có thể chưa từng index (ignore 404).
  3) LightRAG KG   — fail-safe, tự bỏ qua nếu LIGHTRAG_ENABLED=false.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="chatbot.purge_document")
def purge_document(document_id: int) -> None:
    """Xoá mọi dấu vết của `document_id` khỏi OpenSearch (rag + summary) + KG.

    Import client bên trong task (Django app registry đã sẵn sàng trong worker).
    Best-effort, không raise lại: tài liệu đã bị gỡ ở DB, lỗi dọn index chỉ log
    (chưa cấu hình retry ở Phase 1 — tránh worker retry vô hạn).
    """
    from ..lightrag.lightrag_client import LightRagIndexer
    from ..opensearch import OpenSearchIndexer, SummaryIndexer

    logger.info("[purge_document] nhận document_id=%s", document_id)

    # 1) rag-index — quan trọng nhất (chống chatbot truy hồi tài liệu đã xoá).
    try:
        OpenSearchIndexer().delete_document(document_id)
    except Exception:
        logger.exception(
            "[purge_document] document_id=%s lỗi purge rag-index (tài liệu có thể "
            "vẫn truy hồi được cho tới lần purge sau)",
            document_id,
        )

    # 2) summary index — fail-safe.
    try:
        SummaryIndexer().delete_summary(document_id)
    except Exception:
        logger.exception(
            "[purge_document] document_id=%s lỗi purge summary index (bỏ qua)", document_id
        )

    # 3) LightRAG KG — đã fail-safe nội bộ (no-op nếu tắt), không raise.
    LightRagIndexer().delete_document(document_id)
