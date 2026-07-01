"""Factory chọn client embedding theo env `EMBEDDING_PROVIDER` (gemini|ollama).

Tách `embedder.py` khỏi việc phụ thuộc cứng vào `GeminiClient`: mọi client embedding
phải tuân CÙNG contract `embed(texts, dims, task_type) -> list[list[float]]` (đúng
signature của `GeminiClient.embed`) nên caller không cần biết provider cụ thể.

Provider mặc định là `gemini` → hành vi giữ NGUYÊN như cũ. Import client theo nhánh
(lazy) để image/luồng không dùng tới provider nào thì không phải cài SDK của nó.
"""

from __future__ import annotations

from .config import _env


def get_embedding_client():
    """Trả client embedding theo `EMBEDDING_PROVIDER` (mặc định 'gemini')."""
    provider = _env("EMBEDDING_PROVIDER", default="gemini").lower()
    if provider == "ollama":
        from modules.base.app.clients.ollama_client import OllamaClient

        return OllamaClient()
    from modules.base.app.clients.gemini_client import GeminiClient

    return GeminiClient()
