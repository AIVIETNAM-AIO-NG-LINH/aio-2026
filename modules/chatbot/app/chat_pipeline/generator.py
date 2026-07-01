"""Gọi Gemini non-stream — chỉ còn dùng cho sinh tiêu đề hội thoại.

Luồng chat chính đã chuyển sang ADK (xem `adk/`), không gọi `generate_content_stream`
trực tiếp nữa. Sinh tiêu đề là tác vụ ngắn, 1 lượt, nên giữ gọi trực tiếp cho gọn.
"""

from __future__ import annotations

from modules.base.app.clients.gemini_client import GeminiClient


def generate_text(prompt: str, model: str) -> str:
    """Gọi Gemini non-stream, trả text đã strip (dùng cho sinh tiêu đề hội thoại)."""
    return GeminiClient().generate_text([prompt], model=model)
