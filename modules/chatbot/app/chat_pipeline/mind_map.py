"""Sinh + chuẩn hoá "sơ đồ tư duy" (mind map) cho 1 lượt chat.

Hai phần:
  1. `generate_mind_map()` — gọi Gemini structured-output (`response_schema`) để biến
     NỘI DUNG NGUỒN (do agent chọn qua tool `create_mind_map`, đúng phạm vi user yêu
     cầu; fallback transcript cả hội thoại nếu agent để trống) thành CÂY mind map dạng
     **node phẳng**: mỗi node trỏ cha qua `parent_id`, KHÔNG lồng đệ quy → né giới hạn
     độ sâu (~5 cấp) và bug schema đệ quy (`$ref`/RecursionError) của Gemini. FE dựng
     lại cây từ `parent_id`.
  2. `normalize_mind_map()` — ANTI-CORRUPTION LAYER (mirror `citations.py`): whitelist
     field, ép kiểu, chặn kích thước, đảm bảo `parent_id` hợp lệ + không vòng lặp
     TRƯỚC khi đẩy ra SSE / lưu `chat_messages.mind_map`.

Sơ đồ sinh THEO YÊU CẦU: agent gọi tool `create_mind_map` (xem `adk/tools.py`) →
`chat_service` gọi hàm ở đây SAU khi câu trả lời xong (token cộng vào lượt chat).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from google.genai import types

from modules.base.app.clients.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

# Trần kích thước (chống phình SSE/JSONField + sơ đồ vô nghĩa do model "đào" quá sâu).
_MAX_NODES = 200
_MAX_LABEL = 200
_MAX_NOTES = 1000

# Schema ép Gemini trả JSON node PHẲNG (không đệ quy → không dính bug nesting/$ref).
MINDMAP_RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "title": types.Schema(type=types.Type.STRING),
        "nodes": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "id": types.Schema(type=types.Type.STRING),
                    "parent_id": types.Schema(type=types.Type.STRING, nullable=True),
                    "label": types.Schema(type=types.Type.STRING),
                    "notes": types.Schema(type=types.Type.STRING, nullable=True),
                    "link": types.Schema(type=types.Type.STRING, nullable=True),
                    # Hướng toả của NHÁNH CẤP 1 (parent_id=null): "left" | "right".
                    # LLM tự quyết để cân bằng sơ đồ hai phía; node sâu hơn để null
                    # (FE cho theo phía của nhánh gốc). Xem normalize_mind_map.
                    "direction": types.Schema(
                        type=types.Type.STRING,
                        nullable=True,
                        enum=["left", "right"],
                    ),
                },
                required=["id", "label"],
            ),
        ),
    },
    required=["title", "nodes"],
)


def generate_mind_map(
    source_text: str, focus: str, model: str
) -> tuple[dict[str, Any] | None, Any]:
    """Nội dung nguồn → `(mind_map đã chuẩn hoá | None, usage_metadata | None)`.

    `source_text` là PHẠM VI sơ đồ do agent chọn qua tool `create_mind_map` (đúng điều
    user yêu cầu) — có thể là câu trả lời, ý chính 1 chủ đề, hoặc transcript cả hội
    thoại (fallback). Sơ đồ bám ĐÚNG nội dung này, không tự thêm ngoài.

    KHÔNG raise cho lỗi parse JSON (trả None + usage để vẫn tính token); lỗi gọi Gemini
    để PROPAGATE cho caller tự fail-safe (xem `chat_service._generate_mind_map_safe`).
    """
    prompt = _build_prompt(source_text, focus)
    raw_text, usage = GeminiClient().generate_json(
        [prompt], model=model, response_schema=MINDMAP_RESPONSE_SCHEMA
    )
    data: Any = None
    if raw_text:
        try:
            data = json.loads(raw_text)
        except (ValueError, TypeError):
            logger.warning("[mindmap] parse JSON lỗi (bỏ qua sơ đồ)")
    return normalize_mind_map(data), usage


def _build_prompt(source_text: str, focus: str) -> str:
    """Prompt sinh sơ đồ — grounded vào ĐÚNG nội dung nguồn, cùng ngôn ngữ, node ngắn gọn."""
    focus_line = (
        f"- Center the mind map on this focus: {focus}\n" if focus else ""
    )
    return (
        "Build a MIND MAP (so do tu duy) that organizes the CONTENT below into a clear "
        "hierarchy. The content is the exact material the user asked to visualize.\n"
        "Rules:\n"
        "- Use ONLY information that appears in the content below. Do NOT add outside "
        "knowledge, do NOT invent details, and do NOT pull in unrelated topics.\n"
        "- Write all labels and notes in the SAME language as the content.\n"
        "- Keep `label` short (a few words); put any longer detail in `notes`.\n"
        "- Build a hierarchy: a root `title`, then branches linked by `parent_id` "
        "(use null for top-level branches). Every `id` must be unique.\n"
        "- LAYOUT: the map is drawn around a CENTER root with branches on BOTH sides. "
        "For each TOP-LEVEL branch (a node whose `parent_id` is null), set `direction` "
        "to \"left\" or \"right\" so the two sides are roughly balanced (about half the "
        "branches on each side) and related branches sit on the same side. For all "
        "deeper nodes, leave `direction` null (they follow their branch's side).\n"
        "- Aim for 15-40 nodes, at most 4 levels deep. `notes`/`link` are optional "
        "(use null when not needed).\n"
        f"{focus_line}"
        "\nContent:\n"
        f"{source_text}"
    )


def normalize_mind_map(raw: Any) -> dict[str, Any] | None:
    """Dict thô (từ Gemini) → mind map đúng contract, hoặc None nếu không dựng được.

    - Bỏ node thiếu `id`/`label` hoặc trùng `id`.
    - Ép `parent_id` về None nếu trỏ id không tồn tại (chống node mồ côi).
    - Cắt vòng lặp cha-con (chống FE dựng cây vô hạn).
    - Giới hạn số node + độ dài chuỗi.
    """
    if not isinstance(raw, dict):
        return None
    title = _opt_str(raw.get("title"))
    raw_nodes = raw.get("nodes")
    if not title or not isinstance(raw_nodes, list):
        return None

    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_nodes:
        if not isinstance(item, dict):
            continue
        nid = _opt_str(item.get("id"))
        label = _opt_str(item.get("label"))
        if not nid or not label or nid in seen:
            continue
        seen.add(nid)
        nodes.append(
            {
                "id": nid,
                "parent_id": _opt_str(item.get("parent_id")),
                "label": label,
                "notes": _opt_str(item.get("notes"), _MAX_NOTES),
                "link": _opt_str(item.get("link")),
                "direction": _opt_dir(item.get("direction")),
            }
        )
        if len(nodes) >= _MAX_NODES:
            break
    if not nodes:
        return None

    _fix_parents(nodes)
    _fix_directions(nodes)
    return {"title": title, "nodes": nodes}


def _fix_parents(nodes: list[dict[str, Any]]) -> None:
    """Sửa `parent_id` TẠI CHỖ: trỏ id lạ/chính nó → None; cắt vòng lặp → None."""
    by_id = {node["id"]: node for node in nodes}
    for node in nodes:
        parent = node["parent_id"]
        if parent is not None and (parent == node["id"] or parent not in by_id):
            node["parent_id"] = None
    # Cắt chu trình: đi ngược lên cha; gặp lại id đã qua → tách node hiện tại về gốc.
    for node in nodes:
        seen: set[str] = {node["id"]}
        cursor = node
        while cursor["parent_id"] is not None:
            parent_id = cursor["parent_id"]
            if parent_id in seen:
                node["parent_id"] = None
                break
            seen.add(parent_id)
            cursor = by_id[parent_id]


def _fix_directions(nodes: list[dict[str, Any]]) -> None:
    """Chuẩn hoá `direction` TẠI CHỖ (gọi SAU `_fix_parents` để biết đúng nhánh gốc).

    - CHỈ nhánh cấp 1 (`parent_id is None`) mới mang hướng; node sâu hơn → None
      (FE cho theo phía của nhánh gốc).
    - Nhánh cấp 1 thiếu hướng hợp lệ → tự cân bằng: gán xen kẽ left/right, ưu tiên
      phía đang ít hơn để hai bên gần đều (LLM gán được bao nhiêu thì tôn trọng bấy nhiêu).
    """
    counts = {"left": 0, "right": 0}
    pending: list[dict[str, Any]] = []
    for node in nodes:
        if node["parent_id"] is not None:
            node["direction"] = None
            continue
        direction = node["direction"]
        if direction in counts:
            counts[direction] += 1
        else:
            pending.append(node)  # gán sau để cân theo số đã có.
    for node in pending:
        side = "left" if counts["left"] <= counts["right"] else "right"
        node["direction"] = side
        counts[side] += 1


def _opt_str(value: Any, maxlen: int = _MAX_LABEL) -> str | None:
    """Chuỗi tuỳ chọn đã strip + cắt độ dài; rỗng/None → None."""
    if value is None:
        return None
    text = str(value).strip()
    return text[:maxlen] if text else None


def _opt_dir(value: Any) -> str | None:
    """Hướng nhánh hợp lệ ("left"/"right") hoặc None (mọi giá trị khác)."""
    if isinstance(value, str) and value.strip().lower() in ("left", "right"):
        return value.strip().lower()
    return None
