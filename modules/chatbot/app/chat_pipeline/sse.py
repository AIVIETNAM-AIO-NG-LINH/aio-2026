"""Contract SSE của luồng chat — TOÀN BỘ cấu trúc event đẩy về FE nằm ở file này.

Nguyên tắc: shape dữ liệu FE nhận do BE quyết định TẠI ĐÂY, không tầng nào khác
(ADK/tool/retrieval chỉ là nguồn dữ liệu, đã chuẩn hoá qua `StreamChunk` +
`citations.Citation` trước khi tới đây). `chat_service` KHÔNG tự build dict event
— chỉ gọi các builder bên dưới; đổi contract với FE thì sửa đúng file này.

Wire format: mỗi event 1 dòng `data: <json>\n\n` (không dùng field `event:`/`id:`).
Thứ tự đảm bảo cho FE:

    meta → (delta | thinking | citations)* → mindmap? → done | error

  - `meta`      {type, conversation_id, message_id, citations}  — đầu tiên, 1 lần
  - `delta`     {type, content}                                 — mẩu câu trả lời
  - `thinking`  {type, content}                                 — mẩu suy luận
  - `citations` {type, citations}                               — tool gọi lần 2+
  - `mindmap`   {type, mind_map}                                — sơ đồ tư duy (nếu user yêu cầu)
  - `done`      {type, status: "success", message_id, total_tokens} — kết thúc OK
  - `error`     {type, status: "error", message, message_id}    — kết thúc lỗi

`mindmap` (tuỳ chọn) phát SAU mẩu trả lời cuối và TRƯỚC `done`. Mỗi phần tử trong
`citations` theo contract `citations.Citation`; `mind_map` theo `mind_map.normalize_mind_map`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..adk.stream_handler import StreamChunk


@dataclass
class EmitResult:
    """Kết quả phụ sau khi điều phối stream — caller dùng để lưu message + sinh sơ đồ.

    `citations` là nguồn RAG cuối cùng (lưu `chat_messages.citations`). `mindmap_*` cho
    biết user có yêu cầu vẽ sơ đồ trong lượt này không (qua tool `create_mind_map`) +
    chủ đề tập trung — chat_service sinh sơ đồ SAU khi có câu trả lời.
    """

    citations: list[dict[str, Any]] = field(default_factory=list)
    mindmap_requested: bool = False
    mindmap_focus: str = ""


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


def mindmap_event(mind_map: dict[str, Any]) -> str:
    """Sơ đồ tư duy (mind map) trọn gói — phát SAU mẩu trả lời cuối, TRƯỚC `done`.

    `mind_map`: {title, nodes: [{id, parent_id, label, notes, link}, ...]} (node phẳng,
    đã qua `mind_map.normalize_mind_map`). FE dựng cây từ `parent_id` rồi render (markmap).
    """
    return _sse({"type": "mindmap", "mind_map": mind_map})


def done_event(message_id: int, total_tokens: int = 0) -> str:
    """Kết thúc thành công — event cuối cùng của stream.

    `total_tokens`: tổng token LLM tiêu cho lượt này (prompt + thinking + output,
    cộng dồn qua các lần gọi model) — FE dùng để hiển thị/đối soát hạn mức.
    """
    return _sse(
        {
            "type": "done",
            "status": "success",
            "message_id": message_id,
            "total_tokens": total_tokens,
        }
    )


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


def emit_chat_events(
    chunks: Iterable[StreamChunk],
    *,
    conversation_id: int,
    message_id: int,
    answer_parts: list[str],
    thinking_parts: list[str],
) -> Iterator[str]:
    """Điều phối THỨ TỰ event SSE từ luồng StreamChunk đã chuẩn hoá.

    Mỗi `chunk` có `.kind` ∈ {"citations","text","thinking","mindmap"}. `meta` phát
    "lazy" — ngay TRƯỚC mẩu output đầu tiên: nếu tool đã chạy thì meta kèm citations,
    nếu agent trả thẳng thì meta có citations rỗng. Tool gọi lần 2+ phát thêm event
    `citations`. Chunk "mindmap" KHÔNG phát event ở đây (chỉ ghi nhận YÊU CẦU — sơ đồ
    sinh & phát sau, ở chat_service) nhưng vẫn ép `meta` ra trước để giữ "meta đứng đầu".

    `answer_parts` và `thinking_parts` do CALLER sở hữu & truyền vào (generator chỉ
    append) — để caller lưu được câu trả lời + reasoning kể cả khi lỗi giữa chừng.
    Trả `EmitResult` (citations + cờ yêu cầu sơ đồ) qua `yield from`:

        emit = yield from emit_chat_events(
            chunks, conversation_id=..., message_id=...,
            answer_parts=answer_parts, thinking_parts=thinking_parts,
        )
    """
    citations: list[dict[str, Any]] = []
    mindmap_requested = False
    mindmap_focus = ""
    meta_sent = False

    def _meta() -> str:  # đọc `citations` tại thời điểm gọi (đã/ chưa có tool).
        return meta_event(conversation_id, message_id, citations)

    for out in chunks:
        if out.kind == "citations":
            citations = out.citations
            # Lần đầu → gộp vào meta; lần sau → event citations riêng.
            if not meta_sent:
                yield _meta()
                meta_sent = True
            else:
                yield citations_event(citations)
        elif out.kind == "text":
            if not meta_sent:  # meta LUÔN đứng trước delta đầu tiên.
                yield _meta()
                meta_sent = True
            answer_parts.append(out.text)
            yield delta_event(out.text)
        elif out.kind == "thinking":
            if not meta_sent:
                yield _meta()
                meta_sent = True
            thinking_parts.append(out.text)
            yield thinking_event(out.text)
        elif out.kind == "mindmap":
            # Tool vẽ sơ đồ được gọi → đảm bảo meta đã phát (sơ đồ + done sẽ ra sau),
            # ghi nhận yêu cầu + chủ đề; KHÔNG phát event sơ đồ ở đây.
            if not meta_sent:
                yield _meta()
                meta_sent = True
            mindmap_requested = True
            mindmap_focus = out.focus or mindmap_focus

    # Giữ contract "meta đứng đầu" KỂ CẢ khi stream không có chunk nào (agent im lặng):
    # caller sẽ phát `error`/`done` sau — phải có `meta` trước đó để FE gắn message_id.
    if not meta_sent:
        yield _meta()

    return EmitResult(
        citations=citations,
        mindmap_requested=mindmap_requested,
        mindmap_focus=mindmap_focus,
    )
