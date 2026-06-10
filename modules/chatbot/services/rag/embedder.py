"""Sinh embedding cho từng chunk bằng Gemini embeddings (text-embedding-004).

Trả về cặp (chunk_text, vector). Chunk nào model không sinh đúng số chiều mong đợi
(mặc định 768) sẽ bị loại — index chỉ nhận vector đúng dimension.
"""

from __future__ import annotations

import logging

from .config import GeminiConfig
from .gemini_client import build_client

logger = logging.getLogger(__name__)

# Số chunk gửi mỗi lần gọi embed (tránh payload quá lớn).
_BATCH_SIZE = 50


def embed_chunks(
    chunks: list[str],
    expected_dims: int,
    config: GeminiConfig,
) -> list[tuple[str, list[float]]]:
    """Embed `chunks`, trả [(text, vector)] với vector đúng `expected_dims`.

    Bỏ qua (log warning) chunk nào ra sai số chiều. List rỗng nếu không có chunk.
    """
    if not chunks:
        return []

    client = build_client(config)
    results: list[tuple[str, list[float]]] = []

    for start in range(0, len(chunks), _BATCH_SIZE):
        batch = chunks[start : start + _BATCH_SIZE]
        response = client.models.embed_content(
            model=config.embedding_model,
            contents=batch,
        )
        embeddings = response.embeddings or []
        for text, embedding in zip(batch, embeddings):
            vector = list(embedding.values or [])
            if len(vector) != expected_dims:
                logger.warning(
                    "[embed] bỏ qua chunk sai chiều: got=%d expected=%d",
                    len(vector),
                    expected_dims,
                )
                continue
            results.append((text, vector))

    logger.info("[embed] %d/%d chunk ra vector hợp lệ", len(results), len(chunks))
    return results
