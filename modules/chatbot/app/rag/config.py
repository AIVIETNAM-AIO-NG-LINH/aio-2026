"""Cấu hình pipeline RAG — đọc TOÀN BỘ từ biến môi trường (12-factor).

Gom config rời rạc (chunking, rerank…) vào các dataclass nhỏ để phần còn
lại của pipeline nhận object đã parse sẵn thay vì gọi `os.getenv` rải rác.
Không đụng `config/settings.py` — RAG là tính năng nền của worker, giữ độc lập.
(S3/Gemini/OpenSearch/LightRAG không nằm đây — client ở `modules.base.clients`
tự quản: `S3Client`, `GeminiClient`, `BaseOpenSearchClient`, `BaseLightRagClient`.)
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
        # Fix cứng trong code (không đọc env) — chỉnh trực tiếp tại đây khi cần.
        return cls(
            top_k=5,    # số chunk trả về cuối cùng (sau rerank).
            top_n=30,   # số ứng viên lấy từ hybrid search để đưa vào rerank.
            rrf_k=60,   # hằng số RRF khi hợp nhất BM25 + kNN.
        )
