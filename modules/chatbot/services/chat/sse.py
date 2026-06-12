"""Contract SSE của luồng chat — TOÀN BỘ cấu trúc event đẩy về FE nằm ở file này.

Nguyên tắc: shape dữ liệu FE nhận do BE quyết định TẠI ĐÂY, không tầng nào khác
(ADK/tool/retrieval chỉ là nguồn dữ liệu, đã chuẩn hoá qua `StreamChunk` +
`citations.Citation` trước khi tới đây). `chat_service` KHÔNG tự build dict event
— chỉ gọi các builder bên dưới; đổi contract với FE thì sửa đúng file này.

Wire format: mỗi event 1 dòng `data: <json>\n\n` (không dùng field `event:`/`id:`).
Thứ tự đảm bảo cho FE:

    meta → (delta | thinking | citations)* → done | error

  - `meta`      {type, conversation_id, message_id, citations}  — đầu tiên, 1 lần
  - `delta`     {type, content}                                 — mẩu câu trả lời
  - `thinking`  {type, content}                                 — mẩu suy luận
  - `citations` {type, citations}                               — tool gọi lần 2+
  - `done`      {type, status: "success", message_id}           — kết thúc OK
  - `error`     {type, status: "error", message, message_id}    — kết thúc lỗi

Mỗi phần tử trong `citations` theo contract `citations.Citation`.
"""

from __future__ import annotations

import json
from typing import Any


def _sse(payload: dict[str, Any]) -> str:
    """Đóng gói 1 event thành dòng SSE (`data: <json>\\n\\n`), giữ Unicode."""
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


def meta_event(
    conversation_id: int, message_id: int, citations: list[dict[str, Any]]
) -> str:
    """Event mở đầu — FE dựng bubble + citations từ đây. LUÔN đứng trước delta."""
    return _sse(
        {
            "type": "meta",
            "conversation_id": conversation_id,
            "message_id": message_id,
            "citations": citations,
        }
    )


def delta_event(content: str) -> str:
    """1 mẩu câu trả lời — FE append dần."""
    return _sse({"type": "delta", "content": content})


def thinking_event(content: str) -> str:
    """1 mẩu suy luận (model bật thoughts) — FE tuỳ chọn hiển thị."""
    return _sse({"type": "thinking", "content": content})


def citations_event(citations: list[dict[str, Any]]) -> str:
    """Citations bổ sung khi tool RAG chạy lần 2+ (lần đầu đã gộp vào meta)."""
    return _sse({"type": "citations", "citations": citations})


def done_event(message_id: int) -> str:
    """Kết thúc thành công — event cuối cùng của stream."""
    return _sse({"type": "done", "status": "success", "message_id": message_id})


def error_event(message: str, message_id: int) -> str:
    """Kết thúc lỗi (status 200 đã gửi nên lỗi đi qua event, không qua HTTP code)."""
    return _sse(
        {
            "type": "error",
            "status": "error",
            "message": message,
            "message_id": message_id,
        }
    )
