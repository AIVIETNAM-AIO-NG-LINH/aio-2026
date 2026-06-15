"""Index tài liệu chatbot vào LightRAG (knowledge graph) — fail-safe, tắt mặc định.

Sau khi rag-index chính xong, bước này nạp text tài liệu vào LightRAG để dựng
knowledge graph (entity/relation). Toàn bộ phần hạ tầng (env `LIGHTRAG_*`, dựng
LightRAG instance PG/Neo4j + Gemini, vòng đời storages) do `BaseLightRagClient`
ở base tự quản — file này chỉ còn thao tác domain: re-index 1 tài liệu.

NGUYÊN TẮC:
  * `LIGHTRAG_ENABLED=false` (mặc định) → bỏ qua hoàn toàn, không import lightrag.
  * Mọi lỗi bị nuốt (log) — KHÔNG bao giờ đổi status tài liệu sang FAILED.
  * Chạy async bằng `asyncio.run()` vì Celery worker là sync (không cần
    thread-event-loop như server async).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from modules.base.clients.lightrag_client import BaseLightRagClient

if TYPE_CHECKING:
    from lightrag import LightRAG

logger = logging.getLogger(__name__)


class LightRagIndexer(BaseLightRagClient):
    """Re-index 1 tài liệu chatbot vào KG (delete → insert, idempotent theo doc_id)."""

    def index_document(self, document_id: int, text: str) -> bool:
        """Sync wrapper fail-safe cho pipeline ingest.

        Trả True nếu nạp thành công; False nếu KG tắt / text rỗng / lỗi (đã log).
        KHÔNG raise: pipeline gọi hàm này sau khi đã READY, lỗi KG chỉ là phụ.
        """
        if not self.enabled:
            logger.info("[lightrag] LIGHTRAG_ENABLED=false, bỏ qua document_id=%s", document_id)
            return False
        if not text or not text.strip():
            logger.warning("[lightrag] document_id=%s text rỗng, bỏ qua", document_id)
            return False

        try:
            return asyncio.run(self._aindex_document(document_id, text))
        except Exception:
            logger.exception("[lightrag] document_id=%s lỗi index KG (bỏ qua)", document_id)
            return False

    async def _aindex_document(self, document_id: int, text: str) -> bool:
        """Re-index sạch: xoá doc cũ (no-op nếu chưa có) rồi nạp lại text mới."""
        doc_id = f"chatbot_{document_id}"

        async def action(rag: LightRAG) -> bool:
            try:
                await rag.adelete_by_doc_id(doc_id)
            except Exception:
                logger.warning(
                    "[lightrag] adelete_by_doc_id(%s) bỏ qua (có thể chưa tồn tại)", doc_id
                )
            await rag.ainsert(text, ids=doc_id)
            logger.info("[lightrag] document_id=%s đã nạp KG (doc_id=%s)", document_id, doc_id)
            return True

        return await self._run_with_rag(action)
