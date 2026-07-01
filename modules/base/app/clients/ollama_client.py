"""Client Ollama (local) — cùng interface embed() như GeminiClient.

Ollama KHÔNG có task_type bất đối xứng (RETRIEVAL_DOCUMENT/QUERY) như gemini-embedding-001
→ embed index lẫn query cùng một cách, bỏ qua tham số task_type (giữ signature để tương thích).
Trả vector THÔ, KHÔNG normalize ở đây — embedder.py tự L2-normalize (khớp cosinesimil).
"""

from __future__ import annotations

import os

import requests


def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v.strip() if v and v.strip() else default


class OllamaClient:
    def __init__(self) -> None:
        self.api_base = _env("OLLAMA_API_BASE", default="http://ollama:11434").rstrip(
            "/"
        )
        self.embedding_model = _env(
            "OLLAMA_EMBEDDING_MODEL", default="nomic-embed-text"
        )

    def embed(self, texts: list[str], dims: int, task_type: str) -> list[list[float]]:
        # task_type bị bỏ qua (Ollama embedding đối xứng). `dims` để caller kiểm tra.
        resp = requests.post(
            f"{self.api_base}/api/embed",
            json={"model": self.embedding_model, "input": texts},
            timeout=60,
        )
        resp.raise_for_status()
        return [list(v) for v in resp.json().get("embeddings", [])]
