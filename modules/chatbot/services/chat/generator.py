"""Gọi Gemini non-stream — chỉ còn dùng cho sinh tiêu đề hội thoại.

Luồng chat chính đã chuyển sang ADK (xem `adk/`), không gọi `generate_content_stream`
trực tiếp nữa. Sinh tiêu đề là tác vụ ngắn, 1 lượt, nên giữ gọi trực tiếp cho gọn.
"""

from __future__ import annotations

from ..rag.config import GeminiConfig
from ..rag.gemini_client import build_client


def generate_text(prompt: str, model: str, gemini_config: GeminiConfig) -> str:
    """Gọi Gemini non-stream, trả text đã strip (dùng cho sinh tiêu đề hội thoại)."""
    client = build_client(gemini_config)
    response = client.models.generate_content(model=model, contents=[prompt])
    return (response.text or "").strip()
