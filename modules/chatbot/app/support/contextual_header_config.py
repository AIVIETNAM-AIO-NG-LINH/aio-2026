"""Config contextual header — tách từ `rag/config.py`, đặt ở `pipelines/` cạnh ingest.

Helper `_env`/`_env_bool` vẫn dùng chung từ `rag/config.py` (nơi giữ các config còn lại).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..rag.config import _env, _env_bool


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
                default="Document: {name} | Page: {page} | Type: {kind}",
            ),
        )
