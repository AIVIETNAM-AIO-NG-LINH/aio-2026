"""Factory khởi tạo Google GenAI (Gemini) client dùng chung.

Extractor và Embedder đều cần một `genai.Client`; gom việc khởi tạo về một chỗ
để đọc API key nhất quán và dễ thay đổi cấu hình về sau.
"""

from __future__ import annotations

from google import genai

from .config import GeminiConfig


def build_client(config: GeminiConfig) -> genai.Client:
    """Tạo `genai.Client` từ `GEMINI_API_KEY`.

    Raise ValueError sớm nếu thiếu API key — rõ ràng hơn để lỗi xảy ra sâu trong
    SDK lúc gọi model.
    """
    if not config.api_key:
        raise ValueError("GEMINI_API_KEY chưa được cấu hình")
    return genai.Client(api_key=config.api_key)
