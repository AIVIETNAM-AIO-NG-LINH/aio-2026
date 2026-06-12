"""Contract `Citation` — cấu trúc nguồn trích dẫn BE cam kết với FE.

Đây là ANTI-CORRUPTION LAYER: payload thô đi qua tool RAG → ADK function_response
là chi tiết nội bộ, đổi theo thư viện/pipeline bất kỳ lúc nào. Mọi citation TRƯỚC
KHI đẩy ra ngoài (SSE meta/citations + lưu `chat_messages.citations`) phải qua
`normalize_citations()`: chỉ giữ đúng các field khai báo ở `Citation`, ép kiểu
từng field, field lạ bị BỎ, field thiếu về default — thư viện đổi shape thì FE
không vỡ ngầm.

Muốn thêm/bớt field cho FE: sửa `Citation` (một chỗ duy nhất), KHÔNG đổi gì ở
tầng tool/stream handler.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


def _to_int(value: Any) -> int | None:
    """Ép int an toàn — không ép được → None (không raise giữa stream)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any, default: float = 0.0) -> float:
    """Ép float an toàn — không ép được → default."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Citation:
    """1 nguồn trích dẫn trả cho FE — field ở đây là TOÀN BỘ contract."""

    chunk_text: str
    score: float
    document_id: int | None
    media_id: int | None
    original_name: str | None
    page: int | None

    @classmethod
    def from_chunk(cls, chunk: dict[str, Any]) -> "Citation":
        """Map 1 chunk thô từ retrieval/tool → Citation (whitelist + ép kiểu)."""
        original_name = chunk.get("original_name")
        return cls(
            chunk_text=str(chunk.get("chunk_text") or ""),
            score=_to_float(chunk.get("score")),
            document_id=_to_int(chunk.get("document_id")),
            media_id=_to_int(chunk.get("media_id")),
            original_name=str(original_name) if original_name is not None else None,
            page=_to_int(chunk.get("page")),
        )


def normalize_citations(raw: Any) -> list[dict[str, Any]]:
    """List chunk thô (từ function_response) → list dict đúng contract `Citation`.

    Fail-soft từng phần tử: item không phải dict thì bỏ qua — KHÔNG raise để không
    phá luồng stream đang chạy. Trả plain dict (json.dumps + JSONField dùng được).
    """
    if not isinstance(raw, list):
        return []
    return [asdict(Citation.from_chunk(item)) for item in raw if isinstance(item, dict)]
