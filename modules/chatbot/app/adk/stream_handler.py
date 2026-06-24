"""Chuyển Event của ADK Runner → các "mẩu" chuẩn hoá (`StreamChunk`) cho tầng SSE.

Mỗi `process(event)` yield 0..n `StreamChunk`, phân biệt qua `kind`:
  - "text"      → `chunk.text`       — mẩu câu trả lời (stream dần)
  - "thinking"  → `chunk.text`       — suy luận (nếu model bật thoughts)
  - "citations" → `chunk.citations`  — nguồn RAG, lấy từ function_response
  - "mindmap"   → `chunk.content`/`chunk.focus` — tín hiệu user yêu cầu vẽ sơ đồ + nội
                    dung agent chọn để vẽ (tool create_mind_map)

ChatService dịch các kind này sang event SSE (delta / thinking / citations); riêng
"mindmap" chỉ là TÍN HIỆU — sơ đồ được sinh & phát sau lượt trả lời (chat_service).

Lưu ý dedup giống ga-ai: ADK SSE phát các mẩu partial rồi 1 event cuối GỘP toàn bộ
câu trả lời — bỏ event cuối nếu đã stream để tránh lặp.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any, Literal

from google.adk.events import Event

from ..chat_pipeline.citations import normalize_citations
from .constants import MINDMAP_TOOL_NAME, SEARCH_TOOL_NAME

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StreamChunk:
    """1 mẩu chuẩn hoá bóc từ Event ADK — `kind` quyết định field nào có nghĩa.

    `kind` là Literal để consumer so sánh được type-check (gõ sai giá trị là
    Pylance báo ngay, không chờ tới runtime).
    """

    kind: Literal["text", "thinking", "citations", "mindmap"]
    text: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    # Chỉ có nghĩa với kind="mindmap":
    #   - `content`: nội dung agent chọn để vẽ sơ đồ ("" = fallback cả hội thoại).
    #   - `focus`: chủ đề user muốn tập trung (dùng cho tiêu đề/nhấn mạnh).
    content: str = ""
    focus: str = ""


class ADKStreamHandler:
    """Bóc tách Event ADK thành mẩu text / thinking / citations."""

    def __init__(self) -> None:
        self._streamed_any_text = False

    def process(self, event: Event) -> Generator[StreamChunk, None, None]:
        if not event.content:
            return

        # Event cuối (không partial) sau khi đã stream text LẶP LẠI toàn bộ text → bỏ
        # phần text/thinking để khỏi trùng. NHƯNG function_response VẪN phải xử lý: tool
        # có thể được gọi SAU khi text đã stream (vd `create_mind_map`), nếu return sớm
        # cả event sẽ nuốt mất tín hiệu tool.
        skip_text = not event.partial and self._streamed_any_text

        for part in event.content.parts or []:
            # --- Kết quả tool (LUÔN xử lý, kể cả ở event cuối) ---
            if getattr(part, "function_response", None) is not None:
                yield from self._from_function_response(part.function_response)

            elif skip_text:
                continue

            # --- Suy luận (chain-of-thought) nếu model phát thoughts ---
            elif getattr(part, "thought", None) and part.text:
                yield StreamChunk(kind="thinking", text=part.text)

            # --- Mẩu câu trả lời ---
            elif part.text:
                self._streamed_any_text = True
                yield StreamChunk(kind="text", text=part.text)

    def _from_function_response(
        self, func_resp: Any
    ) -> Generator[StreamChunk, None, None]:
        """Tool result → chunk: citations (search) hoặc tín hiệu mindmap (create_mind_map).

        Tool khác (vd get_document_url) không sinh chunk — chỉ phục vụ model nội bộ.
        """
        if func_resp.name == SEARCH_TOOL_NAME:
            citations = self._extract_citations(func_resp.response)
            if citations:
                yield StreamChunk(kind="citations", citations=citations)
        elif func_resp.name == MINDMAP_TOOL_NAME:
            response = func_resp.response
            is_dict = isinstance(response, dict)
            content = str(response.get("content") or "") if is_dict else ""
            focus = str(response.get("focus") or "") if is_dict else ""
            yield StreamChunk(kind="mindmap", content=content, focus=focus)

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
