"""Base class cho mọi class thao tác LightRAG (knowledge graph) — tự quản config + instance.

Giống `BaseOpenSearchClient` (khác `S3Client`/`GeminiClient` là client độc lập),
LightRAG sẽ có nhiều class domain (indexer lúc ingest, querier cho chat…) — nên
đây là BASE CLASS để kế thừa:

    from modules.base.clients.lightrag_client import BaseLightRagClient

    class MyIndexer(BaseLightRagClient):
        async def do_something(self):
            return await self._run_with_rag(lambda rag: rag.ainsert(...))

Base tự đọc env `LIGHTRAG_*` (12-factor); subclass kiểm tra `self.enabled` rồi
thao tác qua `self._run_with_rag(...)` — KHÔNG tự parse env hay dựng LightRAG.

Storage: PostgreSQL cho KV/Vector/DocStatus, Neo4j cho graph. LLM trích entity =
Gemini Flash, embedding = gemini-embedding-001 768 chiều (MRL, L2-normalize) —
dùng `GeminiClient` của base (bản async). Import lightrag/numpy được hoãn vào
trong method để module vẫn import được khi chưa cài lightrag-hku hoặc KG tắt.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Awaitable, Callable, TypeVar

from .gemini_client import GeminiClient

if TYPE_CHECKING:
    from lightrag import LightRAG

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Embedding gemini-embedding-001 @768 chiều (MRL), ngữ cảnh tối đa ~2048 token.
_EMBEDDING_DIM = 768
_EMBEDDING_MAX_TOKENS = 2048
# task_type cho lúc INDEX tài liệu vào KG (đồng bộ với embedder chính).
_TASK_TYPE_DOCUMENT = "RETRIEVAL_DOCUMENT"


def _env(name: str, default: str = "") -> str:
    """Đọc env, strip khoảng trắng; rỗng/không set → default."""
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse env dạng bool ('1/true/yes/on' → True)."""
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    """Parse env dạng int; lỗi/không set → default."""
    raw = _env(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


class BaseLightRagClient:
    """Base kết nối LightRAG qua env — subclass thao tác qua `self._run_with_rag`."""

    def __init__(self) -> None:
        #: Mặc định False để bỏ qua hẳn KG khi chưa có hạ tầng PG/Neo4j.
        self.enabled = _env_bool("LIGHTRAG_ENABLED", default=False)
        # working_dir cục bộ (cache/khoá nội bộ). PG/Neo4j giữ dữ liệu thật.
        self._working_dir = _env("LIGHTRAG_WORKING_DIR", default="/tmp/lightrag/chatbot")
        self._pg_host = _env("LIGHTRAG_PG_HOST", default="postgres")
        self._pg_port = _env_int("LIGHTRAG_PG_PORT", default=5432)
        self._pg_user = _env("LIGHTRAG_PG_USER", default="postgres")
        self._pg_password = _env("LIGHTRAG_PG_PASSWORD")
        self._pg_database = _env("LIGHTRAG_PG_DATABASE", default="lightrag")
        self._neo4j_uri = _env("LIGHTRAG_NEO4J_URI", default="bolt://neo4j:7687")
        self._neo4j_username = _env("LIGHTRAG_NEO4J_USERNAME", default="neo4j")
        self._neo4j_password = _env("LIGHTRAG_NEO4J_PASSWORD")

    # --- Khởi tạo LightRAG ---------------------------------------------------
    def _export_storage_env(self) -> None:
        """Map env riêng của ai-aio → env mà LightRAG storage backend mong đợi.

        PGKVStorage/PGVectorStorage/PGDocStatusStorage đọc POSTGRES_*; Neo4JStorage
        đọc NEO4J_*. Set trong process worker ngay trước khi khởi tạo LightRAG.
        """
        os.environ["POSTGRES_HOST"] = self._pg_host
        os.environ["POSTGRES_PORT"] = str(self._pg_port)
        os.environ["POSTGRES_USER"] = self._pg_user
        os.environ["POSTGRES_PASSWORD"] = self._pg_password
        os.environ["POSTGRES_DATABASE"] = self._pg_database
        os.environ["NEO4J_URI"] = self._neo4j_uri
        os.environ["NEO4J_USERNAME"] = self._neo4j_username
        os.environ["NEO4J_PASSWORD"] = self._neo4j_password

    @staticmethod
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

    @staticmethod
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

    def _build_rag(self) -> "LightRAG":
        """Dựng LightRAG instance (PG + Neo4j, LLM/embedding = Gemini)."""
        from lightrag import LightRAG
        from lightrag.utils import EmbeddingFunc

        self._export_storage_env()
        os.makedirs(self._working_dir, exist_ok=True)

        gemini = GeminiClient()
        return LightRAG(
            working_dir=self._working_dir,
            llm_model_func=self._build_llm_func(gemini),
            embedding_func=EmbeddingFunc(
                embedding_dim=_EMBEDDING_DIM,
                max_token_size=_EMBEDDING_MAX_TOKENS,
                func=self._build_embedding_func(gemini),
            ),
            kv_storage="PGKVStorage",
            vector_storage="PGVectorStorage",
            doc_status_storage="PGDocStatusStorage",
            graph_storage="Neo4JStorage",
        )

    # --- Vòng đời ------------------------------------------------------------
    async def _run_with_rag(self, action: Callable[["LightRAG"], Awaitable[T]]) -> T:
        """Dựng LightRAG, mở storages, chạy `action(rag)` rồi LUÔN đóng kết nối.

        Bọc trọn vòng đời initialize → action → finalize để subclass chỉ viết
        phần thao tác domain; worker sync không tái dùng pool PG/Neo4j.
        """
        from lightrag.kg.shared_storage import initialize_pipeline_status

        rag = self._build_rag()
        try:
            await rag.initialize_storages()
            await initialize_pipeline_status()
            return await action(rag)
        finally:
            # Đóng kết nối PG/Neo4j của lần chạy này.
            try:
                await rag.finalize_storages()
            except Exception:
                logger.warning("[lightrag] finalize_storages lỗi (bỏ qua)")
