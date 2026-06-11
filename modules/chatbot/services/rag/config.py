"""Cấu hình pipeline RAG — đọc TOÀN BỘ từ biến môi trường (12-factor).

Gom config rời rạc (chunking, rewrite, rerank…) vào các dataclass nhỏ để phần còn
lại của pipeline nhận object đã parse sẵn thay vì gọi `os.getenv` rải rác.
Không đụng `config/settings.py` — RAG là tính năng nền của worker, giữ độc lập.
(S3/Gemini/OpenSearch không nằm đây — client ở `modules.base.clients` tự quản:
`S3Client`, `GeminiClient`, `BaseOpenSearchClient`.)
"""

from __future__ import annotations

import os
from dataclasses import dataclass


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


@dataclass(frozen=True)
class ChunkConfig:
    """Tham số tách văn bản thành chunk."""

    chunk_size: int
    chunk_overlap: int

    @classmethod
    def from_env(cls) -> "ChunkConfig":
        return cls(
            chunk_size=_env_int("CHUNK_SIZE", default=800),
            chunk_overlap=_env_int("CHUNK_OVERLAP", default=120),
        )


@dataclass(frozen=True)
class ContextualHeaderConfig:
    """Header ngữ cảnh "light" gắn vào đầu MỖI chunk trước khi embed.

    Bản nhẹ theo khuyến nghị nghiên cứu: KHÔNG gọi LLM cho từng chunk, chỉ ghép
    metadata sẵn có (tên tài liệu, số trang, loại file) thành 1 dòng prefix để
    chunk tự đủ ngữ cảnh → tăng recall. `template` dùng placeholder `{name}`,
    `{page}`, `{kind}` (str.format). Tắt → quay về prefix cũ "File: {name}".
    """

    enabled: bool
    template: str

    # Prefix cũ (Phase 1-4) dùng khi tắt contextual header — giữ tương thích.
    legacy_prefix: str = "File: {name}"

    @classmethod
    def from_env(cls) -> "ContextualHeaderConfig":
        return cls(
            enabled=_env_bool("CONTEXTUAL_HEADER_ENABLED", default=True),
            template=_env(
                "CONTEXTUAL_HEADER_FORMAT",
                default="Tài liệu: {name} | Trang: {page} | Loại: {kind}",
            ),
        )


@dataclass(frozen=True)
class QueryRewriteConfig:
    """Viết lại / mở rộng truy vấn trước khi search (Gemini Flash, song ngữ Việt↔Anh).

    Chuẩn hoá câu hỏi + sinh thêm biến thể dịch/đồng nghĩa để tăng recall trên kho
    dữ liệu song ngữ. `enabled=False` hoặc lỗi gọi LLM → fallback chỉ dùng query gốc
    (fail-safe, xem `query_rewriter.py`). `max_variants` giới hạn TỔNG số truy vấn
    (gồm cả query gốc) đưa vào hybrid search để chặn chi phí.
    """

    enabled: bool
    model: str
    max_variants: int

    @classmethod
    def from_env(cls) -> "QueryRewriteConfig":
        return cls(
            enabled=_env_bool("QUERY_REWRITE_ENABLED", default=True),
            # Tái dùng Gemini Flash; tách env riêng để chỉnh độc lập với extract/summary.
            model=_env("QUERY_REWRITE_MODEL", default="gemini-2.5-flash"),
            max_variants=_env_int("QUERY_REWRITE_MAX_VARIANTS", default=3),
        )


@dataclass(frozen=True)
class RerankConfig:
    """Cross-encoder rerank top_n → top_k qua HTTP (PLUGGABLE, KHÔNG load model trong Django).

    Gọi 1 endpoint rerank ngoài (vd TEI/BGE, Jina, Cohere-compatible). `enabled=False`,
    thiếu `endpoint_url`, hoặc lỗi/timeout HTTP → bỏ rerank, giữ thứ hạng hybrid
    (fail-safe, xem `reranker_client.py`). `api_key` optional (Bearer nếu có).
    """

    enabled: bool
    endpoint_url: str
    model: str
    api_key: str
    timeout: int

    @classmethod
    def from_env(cls) -> "RerankConfig":
        return cls(
            enabled=_env_bool("RERANK_ENABLED", default=True),
            endpoint_url=_env("RERANK_ENDPOINT_URL"),
            model=_env("RERANK_MODEL", default="bge-reranker-v2-m3"),
            api_key=_env("RERANK_API_KEY"),
            timeout=_env_int("RERANK_TIMEOUT", default=15),
        )


@dataclass(frozen=True)
class RetrieveConfig:
    """Tham số truy hồi (hybrid search + xếp hạng) cho endpoint /retrieve."""

    top_k: int   # số chunk trả về cuối cùng (sau rerank).
    top_n: int   # số ứng viên lấy từ hybrid search để đưa vào rerank.
    rrf_k: int   # hằng số RRF (Reciprocal Rank Fusion) khi hợp nhất BM25 + kNN.

    @classmethod
    def from_env(cls) -> "RetrieveConfig":
        return cls(
            top_k=_env_int("RETRIEVE_TOP_K", default=5),
            top_n=_env_int("RETRIEVE_TOP_N", default=30),
            rrf_k=_env_int("RETRIEVE_RRF_K", default=60),
        )


@dataclass(frozen=True)
class LightRagConfig:
    """Tham số LightRAG (knowledge graph) — PG (KV/Vector/DocStatus) + Neo4j (graph).

    Mặc định `enabled=False` để pipeline bỏ qua hẳn KG khi chưa có hạ tầng PG/Neo4j.
    """

    enabled: bool
    pg_host: str
    pg_port: int
    pg_user: str
    pg_password: str
    pg_database: str
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str

    @classmethod
    def from_env(cls) -> "LightRagConfig":
        return cls(
            enabled=_env_bool("LIGHTRAG_ENABLED", default=False),
            pg_host=_env("LIGHTRAG_PG_HOST", default="postgres"),
            pg_port=_env_int("LIGHTRAG_PG_PORT", default=5432),
            pg_user=_env("LIGHTRAG_PG_USER", default="postgres"),
            pg_password=_env("LIGHTRAG_PG_PASSWORD"),
            pg_database=_env("LIGHTRAG_PG_DATABASE", default="lightrag"),
            neo4j_uri=_env("LIGHTRAG_NEO4J_URI", default="bolt://neo4j:7687"),
            neo4j_username=_env("LIGHTRAG_NEO4J_USERNAME", default="neo4j"),
            neo4j_password=_env("LIGHTRAG_NEO4J_PASSWORD"),
        )
