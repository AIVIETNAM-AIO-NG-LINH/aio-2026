"""Tích hợp LightRAG (knowledge graph) — fail-safe, tắt mặc định.

Sau khi rag-index chính xong, bước này nạp text tài liệu vào LightRAG để dựng
knowledge graph (entity/relation). Storage: PostgreSQL cho KV/Vector/DocStatus,
Neo4j cho graph. LLM trích entity = Gemini Flash, embedding = gemini-embedding-001
768 chiều (MRL, L2-normalize) — dùng `GeminiClient` của base (bản async).

NGUYÊN TẮC:
  * `LIGHTRAG_ENABLED=false` (mặc định) → bỏ qua hoàn toàn, không import lightrag.
  * Mọi lỗi bị nuốt (log) — KHÔNG bao giờ đổi status tài liệu sang FAILED.
  * Chạy async bằng `asyncio.run()` vì Celery worker là sync (không cần
    thread-event-loop như server async).

Import lightrag/numpy được hoãn vào trong hàm để module pipeline vẫn import được
khi chưa cài lightrag-hku hoặc KG đang tắt.
"""

from __future__ import annotations

import asyncio
import logging
import os

from modules.base.clients.gemini_client import GeminiClient

from .config import LightRagConfig

logger = logging.getLogger(__name__)

# working_dir cục bộ cho LightRAG (cache/khoá nội bộ). PG/Neo4j giữ dữ liệu thật.
_WORKING_DIR = "/tmp/lightrag/chatbot"

# Embedding gemini-embedding-001 @768 chiều (MRL), ngữ cảnh tối đa ~2048 token.
_EMBEDDING_DIM = 768
_EMBEDDING_MAX_TOKENS = 2048
# task_type cho lúc INDEX tài liệu vào KG (đồng bộ với embedder chính).
_TASK_TYPE_DOCUMENT = "RETRIEVAL_DOCUMENT"


def index_lightrag(
    document_id: int,
    text: str,
    lightrag_config: LightRagConfig,
) -> bool:
    """Re-index 1 tài liệu vào LightRAG (sync wrapper, fail-safe).

    Trả True nếu nạp thành công; False nếu KG tắt / text rỗng / lỗi (đã log).
    KHÔNG raise: pipeline gọi hàm này sau khi đã READY, lỗi KG chỉ là phụ.
    """
    if not lightrag_config.enabled:
        logger.info("[lightrag] LIGHTRAG_ENABLED=false, bỏ qua document_id=%s", document_id)
        return False
    if not text or not text.strip():
        logger.warning("[lightrag] document_id=%s text rỗng, bỏ qua", document_id)
        return False

    try:
        return asyncio.run(_aindex_document(document_id, text, lightrag_config))
    except Exception:
        logger.exception("[lightrag] document_id=%s lỗi index KG (bỏ qua)", document_id)
        return False


def _export_storage_env(config: LightRagConfig) -> None:
    """Map env riêng của ai-aio → env mà LightRAG storage backend mong đợi.

    PGKVStorage/PGVectorStorage/PGDocStatusStorage đọc POSTGRES_*; Neo4JStorage
    đọc NEO4J_*. Set trong process worker ngay trước khi khởi tạo LightRAG.
    """
    os.environ["POSTGRES_HOST"] = config.pg_host
    os.environ["POSTGRES_PORT"] = str(config.pg_port)
    os.environ["POSTGRES_USER"] = config.pg_user
    os.environ["POSTGRES_PASSWORD"] = config.pg_password
    os.environ["POSTGRES_DATABASE"] = config.pg_database
    os.environ["NEO4J_URI"] = config.neo4j_uri
    os.environ["NEO4J_USERNAME"] = config.neo4j_username
    os.environ["NEO4J_PASSWORD"] = config.neo4j_password


def _build_llm_func(client: GeminiClient):
    """Async LLM func cho LightRAG: trích entity bằng Gemini Flash."""

    async def llm_model_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list | None = None,
        keyword_extraction: bool = False,
        **kwargs,
    ) -> str:
        # Gộp system_prompt + history + prompt thành một contents đơn giản; Gemini
        # Flash xử lý tốt prompt trích entity của LightRAG mà không cần role riêng.
        parts: list[str] = []
        if system_prompt:
            parts.append(system_prompt)
        for msg in history_messages or []:
            content = msg.get("content") if isinstance(msg, dict) else str(msg)
            if content:
                parts.append(content)
        parts.append(prompt)
        return await client.agenerate_text(
            ["\n\n".join(parts)], model=client.summary_model
        )

    return llm_model_func


def _build_embedding_func(client: GeminiClient):
    """Async embedding func (gemini-embedding-001 @768 chiều, MRL) trả numpy array.

    gemini-embedding-001 ở <3072 chiều KHÔNG normalize sẵn → tự L2-normalize từng
    vector (giống embedder chính) để LightRAG/PGVector tính cosine đúng.
    """
    import numpy as np

    async def embedding_func(texts: list[str]):
        vectors = await client.aembed(texts, _EMBEDDING_DIM, _TASK_TYPE_DOCUMENT)
        arr = np.array(vectors, dtype=np.float32)
        # L2-normalize theo hàng; tránh chia 0 cho vector toàn 0.
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return arr / norms

    return embedding_func


async def _aindex_document(
    document_id: int,
    text: str,
    lightrag_config: LightRagConfig,
) -> bool:
    """Khởi tạo LightRAG (PG + Neo4j) và re-index 1 tài liệu (delete → insert)."""
    from lightrag import LightRAG
    from lightrag.kg.shared_storage import initialize_pipeline_status
    from lightrag.utils import EmbeddingFunc

    _export_storage_env(lightrag_config)
    os.makedirs(_WORKING_DIR, exist_ok=True)

    gemini = GeminiClient()
    rag = LightRAG(
        working_dir=_WORKING_DIR,
        llm_model_func=_build_llm_func(gemini),
        embedding_func=EmbeddingFunc(
            embedding_dim=_EMBEDDING_DIM,
            max_token_size=_EMBEDDING_MAX_TOKENS,
            func=_build_embedding_func(gemini),
        ),
        kv_storage="PGKVStorage",
        vector_storage="PGVectorStorage",
        doc_status_storage="PGDocStatusStorage",
        graph_storage="Neo4JStorage",
    )

    doc_id = f"chatbot_{document_id}"
    try:
        await rag.initialize_storages()
        await initialize_pipeline_status()

        # Re-index sạch: xoá doc cũ (no-op nếu chưa có) rồi nạp lại text mới.
        try:
            await rag.adelete_by_doc_id(doc_id)
        except Exception:
            logger.warning("[lightrag] adelete_by_doc_id(%s) bỏ qua (có thể chưa tồn tại)", doc_id)

        await rag.ainsert(text, ids=doc_id)
        logger.info("[lightrag] document_id=%s đã nạp KG (doc_id=%s)", document_id, doc_id)
        return True
    finally:
        # Đóng kết nối PG/Neo4j của lần chạy này (worker sync, không tái dùng pool).
        try:
            await rag.finalize_storages()
        except Exception:
            logger.warning("[lightrag] finalize_storages lỗi (bỏ qua) doc_id=%s", doc_id)
