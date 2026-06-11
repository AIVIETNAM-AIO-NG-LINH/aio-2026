"""Chuyển Event của ADK Runner → các "mẩu" chuẩn hoá cho tầng SSE.

Mỗi `process(event)` yield 0..n dict:
  {"kind": "text",      "text": str}            # mẩu câu trả lời (stream dần)
  {"kind": "thinking",  "text": str}            # suy luận (nếu model bật thoughts)
  {"kind": "citations", "citations": list}      # nguồn RAG, lấy từ function_response

ChatService dịch các kind này sang event SSE (delta / thinking / citations).

Lưu ý dedup giống ga-ai: ADK SSE phát các mẩu partial rồi 1 event cuối GỘP toàn bộ
câu trả lời — bỏ event cuối nếu đã stream để tránh lặp.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any

from google.adk.events import Event

from .constants import SEARCH_TOOL_NAME

logger = logging.getLogger(__name__)


class ADKStreamHandler:
    """Bóc tách Event ADK thành mẩu text / thinking / citations."""

    def __init__(self) -> None:
        self._streamed_any_text = False

    def process(self, event: Event) -> Generator[dict[str, Any], None, None]:
        if not event.content:
            return

        # Bỏ event cuối (không partial) nếu đã stream text — tránh nội dung trùng.
        if not event.partial and self._streamed_any_text:
            return

        for part in event.content.parts or []:
            # --- Suy luận (chain-of-thought) nếu model phát thoughts ---
            if getattr(part, "thought", None) and part.text:
                yield {"kind": "thinking", "text": part.text}

            # --- Mẩu câu trả lời ---
            elif part.text:
                self._streamed_any_text = True
                yield {"kind": "text", "text": part.text}

            # --- Kết quả tool: trích citations từ search_knowledge_base ---
            elif getattr(part, "function_response", None) is not None:
                func_resp = part.function_response
                if func_resp.name == SEARCH_TOOL_NAME:
                    citations = self._extract_citations(func_resp.response)
                    if citations:
                        yield {"kind": "citations", "citations": citations}

    @staticmethod
    def _extract_citations(response: Any) -> list[dict[str, Any]]:
        """Lấy list chunk từ payload function_response của tool RAG.

        Tool trả `{"results": [...]}`; phòng trường hợp ADK bọc khác, thử vài key
        thông dụng. Không khớp → list rỗng.
        """
        if isinstance(response, dict):
            for key in ("results", "result"):
                value = response.get(key)
                if isinstance(value, list):
                    return value
        elif isinstance(response, list):
            return response
        return []
