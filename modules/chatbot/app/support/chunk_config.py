"""Config chunking — tách từ `rag/config.py`, đặt ở `pipelines/` cạnh ingest.

Helper `_env_int` vẫn dùng chung từ `rag/config.py` (nơi giữ các config còn lại).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..rag.config import _env_int


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
