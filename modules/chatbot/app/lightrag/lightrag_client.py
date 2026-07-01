"""Thao tác LightRAG (knowledge graph) của chatbot — fail-safe, tắt mặc định.

Hai class domain:
  * `LightRagIndexer` — lúc ingest, nạp text tài liệu vào KG (entity/relation).
  * `LightRagQuerier` — lúc chat, truy hồi ngữ cảnh thô từ KG cho agent ADK.

Toàn bộ phần hạ tầng (env `LIGHTRAG_*`, dựng LightRAG instance PG/Neo4j + Gemini,
vòng đời storages) do `BaseLightRagClient` ở base tự quản — file này chỉ còn
thao tác domain.

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

from modules.base.app.clients.lightrag_client import BaseLightRagClient

if TYPE_CHECKING:
    from lightrag import LightRAG

logger = logging.getLogger(__name__)


def _run_coro_blocking(coro_factory):
    """Chạy coroutine đến khi xong, AN TOÀN cả khi đang ở trong event loop đang chạy.

    ADK runner sync (`get_runner().run()`) giữ một event loop đang chạy khi nó gọi
    tool sync; lúc đó `asyncio.run()` sẽ ném 'cannot be called from a running event
    loop'. Khi phát hiện đã có loop, ta chạy trong một thread riêng (loop riêng) để
    không đụng loop của agent. Mỗi lần tạo LightRAG mới nên thread+loop riêng là an toàn.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())  # không có loop → chạy trực tiếp (Celery/CLI)

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro_factory())).result()


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

    def delete_document(self, document_id: int) -> bool:
        """Sync wrapper fail-safe: xoá tài liệu khỏi KG khi gỡ khỏi kho.

        Trả True nếu xoá thành công; False nếu KG tắt / lỗi (đã log). KHÔNG raise:
        KG là nguồn phụ, lỗi xoá chỉ log (task purge vẫn dọn rag-index + summary).
        """
        if not self.enabled:
            logger.info("[lightrag] LIGHTRAG_ENABLED=false, bỏ qua xoá document_id=%s", document_id)
            return False

        try:
            return asyncio.run(self._adelete_document(document_id))
        except Exception:
            logger.exception("[lightrag] document_id=%s lỗi xoá KG (bỏ qua)", document_id)
            return False

    async def _adelete_document(self, document_id: int) -> bool:
        """Xoá doc khỏi KG theo doc_id `chatbot_{document_id}` (no-op nếu chưa có)."""
        doc_id = f"chatbot_{document_id}"

        async def action(rag: LightRAG) -> bool:
            try:
                await rag.adelete_by_doc_id(doc_id)
            except Exception:
                logger.warning(
                    "[lightrag] adelete_by_doc_id(%s) bỏ qua (có thể chưa tồn tại)", doc_id
                )
            logger.info("[lightrag] document_id=%s đã xoá khỏi KG (doc_id=%s)", document_id, doc_id)
            return True

        return await self._run_with_rag(action)


class LightRagQuerier(BaseLightRagClient):
    """Truy vấn knowledge graph lúc chat — trả CONTEXT thô (không sinh câu trả lời).

    Dùng `only_need_context=True` nên LightRAG chỉ truy hồi ngữ cảnh (entity/relation
    + đoạn liên quan) chứ KHÔNG gọi LLM sinh câu trả lời — giữ đúng vai trò "tool truy
    hồi" như `tools.knowledge_base.search()`; việc tổng hợp/trả lời là của agent ADK.
    """

    #: mode "mix" = gộp truy hồi vector (đoạn) + graph (entity/relation) — hợp nhất
    #: thế mạnh cả hai cho câu hỏi vừa tra cứu vừa bắc cầu quan hệ.
    _QUERY_MODE = "mix"

    def query(self, question: str) -> str:
        """Sync wrapper fail-safe: trả context string cho agent, "" nếu tắt/rỗng/lỗi.

        KHÔNG raise: KG là nguồn phụ, lỗi chỉ log để agent vẫn trả lời được bằng
        `search_knowledge_base`. Dùng `_run_coro_blocking` để chạy được CẢ khi ADK
        runner sync đang giữ một event loop (gọi trong thread riêng để tránh xung đột).
        """
        if not self.enabled:
            logger.info("[lightrag] LIGHTRAG_ENABLED=false, bỏ qua truy vấn KG")
            return ""
        if not question or not question.strip():
            return ""

        try:
            return _run_coro_blocking(lambda: self._aquery(question.strip())) or ""
        except Exception:
            logger.exception("[lightrag] lỗi truy vấn KG (trả rỗng)")
            return ""

    async def _aquery(self, question: str) -> str:
        """Gọi `aquery` với `only_need_context=True` → trả ngữ cảnh thô (string)."""

        async def action(rag: LightRAG) -> str:
            from lightrag import QueryParam

            result = await rag.aquery(
                question,
                param=QueryParam(mode=self._QUERY_MODE, only_need_context=True),
            )
            # `aquery` có thể trả str (context) hoặc cấu trúc khác tuỳ phiên bản —
            # ép về str cho chắc; rỗng/None → "".
            context = result if isinstance(result, str) else (str(result) if result else "")
            logger.info("[lightrag] truy vấn KG question=%r → %d ký tự ngữ cảnh",
                        question, len(context))
            return context

        return await self._run_with_rag(action)
