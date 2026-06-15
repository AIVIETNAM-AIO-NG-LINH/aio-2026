"""Cấu hình pipeline RAG — đọc TOÀN BỘ từ biến môi trường (12-factor).

Gom config rời rạc (chunking, rewrite, rerank…) vào các dataclass nhỏ để phần còn
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
