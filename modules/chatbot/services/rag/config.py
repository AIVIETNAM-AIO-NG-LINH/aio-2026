"""Cấu hình pipeline RAG — đọc TOÀN BỘ từ biến môi trường (12-factor).

Gom config rời rạc (S3, Gemini, chunking, OpenSearch) vào các dataclass nhỏ để
phần còn lại của pipeline nhận object đã parse sẵn thay vì gọi `os.getenv` rải rác.
Không đụng `config/settings.py` — RAG là tính năng nền của worker, giữ độc lập.
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
class S3Config:
    """Tham số kết nối S3 / object storage (MinIO-compatible)."""

    endpoint: str
    region: str
    bucket: str
    access_key: str
    secret_key: str
    use_path_style: bool
    media_folder: str

    @classmethod
    def from_env(cls) -> "S3Config":
        return cls(
            endpoint=_env("AWS_S3_ENDPOINT"),
            region=_env("AWS_S3_REGION"),
            bucket=_env("AWS_S3_BUCKET"),
            access_key=_env("AWS_S3_ACCESS_KEY"),
            secret_key=_env("AWS_S3_SECRET_KEY"),
            use_path_style=_env_bool("AWS_S3_USE_PATH_STYLE", default=False),
            media_folder=_env("MEDIA_FOLDER", default="media"),
        )

    def object_key(self, file_name: str) -> str:
        """Object key trên bucket = f"{MEDIA_FOLDER}/{file_name}" (folder có thể rỗng)."""
        folder = self.media_folder.strip("/")
        return file_name if folder == "" else f"{folder}/{file_name}"


@dataclass(frozen=True)
class GeminiConfig:
    """Tham số Google GenAI (Gemini) — extract text + embedding."""

    api_key: str
    embedding_model: str
    extract_model: str
    summary_model: str

    @classmethod
    def from_env(cls) -> "GeminiConfig":
        return cls(
            api_key=_env("GEMINI_API_KEY"),
            # gemini-embedding-001 ở 768 chiều (MRL); vector phải L2-normalize sau embed.
            embedding_model=_env("EMBEDDING_MODEL", default="gemini-embedding-001"),
            # Model multimodal đọc PDF → text. Override qua env nếu Google đổi tên.
            extract_model=_env("GEMINI_EXTRACT_MODEL", default="gemini-2.5-flash"),
            # Model Flash sinh tóm tắt (summary index) + trích entity (LightRAG).
            summary_model=_env("GEMINI_SUMMARY_MODEL", default="gemini-2.5-flash"),
        )


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
class OpenSearchConfig:
    """Tham số kết nối + index OpenSearch (kNN vector parent-child)."""

    url: str
    user: str
    password: str
    verify_certs: bool
    index: str
    summary_index: str
    vector_dims: int

    @classmethod
    def from_env(cls) -> "OpenSearchConfig":
        return cls(
            url=_env("OPENSEARCH_URL", default="http://opensearch:9200"),
            user=_env("OPENSEARCH_USER"),
            password=_env("OPENSEARCH_PASSWORD"),
            verify_certs=_env_bool("OPENSEARCH_VERIFY_CERTS", default=False),
            index=_env("OPENSEARCH_INDEX", default="rag-index"),
            # Index riêng 1-doc-mỗi-tài-liệu cho tóm tắt + vector (Phase 2).
            summary_index=_env("OPENSEARCH_SUMMARY_INDEX", default="document-summary-index"),
            vector_dims=_env_int("OPENSEARCH_VECTOR_DIMS", default=768),
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
