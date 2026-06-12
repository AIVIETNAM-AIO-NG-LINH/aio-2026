"""Chuyển Event của ADK Runner → các "mẩu" chuẩn hoá (`StreamChunk`) cho tầng SSE.

Mỗi `process(event)` yield 0..n `StreamChunk`, phân biệt qua `kind`:
  - "text"      → `chunk.text`       — mẩu câu trả lời (stream dần)
  - "thinking"  → `chunk.text`       — suy luận (nếu model bật thoughts)
  - "citations" → `chunk.citations`  — nguồn RAG, lấy từ function_response

ChatService dịch các kind này sang event SSE (delta / thinking / citations).

Lưu ý dedup giống ga-ai: ADK SSE phát các mẩu partial rồi 1 event cuối GỘP toàn bộ
câu trả lời — bỏ event cuối nếu đã stream để tránh lặp.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any, Literal

from google.adk.events import Event

from ..citations import normalize_citations
from .constants import SEARCH_TOOL_NAME

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StreamChunk:
    """1 mẩu chuẩn hoá bóc từ Event ADK — `kind` quyết định field nào có nghĩa.

    `kind` là Literal để consumer so sánh được type-check (gõ sai giá trị là
    Pylance báo ngay, không chờ tới runtime).
    """

    kind: Literal["text", "thinking", "citations"]
    text: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)


class ADKStreamHandler:
    """Bóc tách Event ADK thành mẩu text / thinking / citations."""

    def __init__(self) -> None:
        self._streamed_any_text = False

    def process(self, event: Event) -> Generator[StreamChunk, None, None]:
        if not event.content:
            return

        # Bỏ event cuối (không partial) nếu đã stream text — tránh nội dung trùng.
        if not event.partial and self._streamed_any_text:
            return

        for part in event.content.parts or []:
            # --- Suy luận (chain-of-thought) nếu model phát thoughts ---
            if getattr(part, "thought", None) and part.text:
                yield StreamChunk(kind="thinking", text=part.text)

            # --- Mẩu câu trả lời ---
            elif part.text:
                self._streamed_any_text = True
                yield StreamChunk(kind="text", text=part.text)

            # --- Kết quả tool: trích citations từ search_knowledge_base ---
            elif getattr(part, "function_response", None) is not None:
                func_resp = part.function_response
                if func_resp.name == SEARCH_TOOL_NAME:
                    citations = self._extract_citations(func_resp.response)
                    if citations:
                        yield StreamChunk(kind="citations", citations=citations)

    @staticmethod
    def _extract_citations(response: Any) -> list[dict[str, Any]]:
        """Lấy list chunk từ payload function_response của tool RAG, CHUẨN HOÁ
        về contract `Citation` trước khi trả.

        Tool trả `{"results": [...]}`; phòng trường hợp ADK bọc khác, thử vài key
        thông dụng. Không khớp → list rỗng. Payload thô KHÔNG được đẩy thẳng ra
        ngoài — shape FE nhận do `citations.Citation` quyết định, không phụ thuộc
        thư viện/pipeline.
        """
        if isinstance(response, dict):
            for key in ("results", "result"):
                value = response.get(key)
                if isinstance(value, list):
                    return normalize_citations(value)
        elif isinstance(response, list):
            return normalize_citations(response)
        return []
