"""Sinh embedding cho từng chunk bằng Gemini embeddings (gemini-embedding-001).

Trả về cặp (chunk_text, vector). Chunk nào model không sinh đúng số chiều mong đợi
(mặc định 768) sẽ bị loại — index chỉ nhận vector đúng dimension.

LƯU Ý gemini-embedding-001: khi yêu cầu số chiều < 3072 (ở đây 768 qua Matryoshka/
MRL `output_dimensionality`), vector trả về KHÔNG được chuẩn hoá sẵn → phải tự
L2-normalize trước khi index để cosine / HNSW `cosinesimil` cho kết quả đúng.
"""

from __future__ import annotations

import logging
import math

from google.genai import types

from .config import GeminiConfig
from .gemini_client import build_client

logger = logging.getLogger(__name__)

# Số chunk gửi mỗi lần gọi embed (tránh payload quá lớn).
_BATCH_SIZE = 50

# task_type cho lúc INDEX tài liệu. Phía query sau này nên dùng "RETRIEVAL_QUERY".
_TASK_TYPE_DOCUMENT = "RETRIEVAL_DOCUMENT"


def _l2_normalize(vector: list[float]) -> list[float]:
    """Chuẩn hoá L2 một vector. Vector toàn 0 (norm=0) giữ nguyên để tránh chia 0."""
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def embed_chunks(
    chunks: list[str],
    expected_dims: int,
    config: GeminiConfig,
) -> list[tuple[str, list[float]]]:
    """Embed `chunks`, trả [(text, vector)] với vector đúng `expected_dims`.

    Vector được yêu cầu đúng `expected_dims` chiều (MRL) và L2-normalize sau khi nhận.
    Bỏ qua (log warning) chunk nào ra sai số chiều. List rỗng nếu không có chunk.
    """
    if not chunks:
        return []

    client = build_client(config)
    results: list[tuple[str, list[float]]] = []

    embed_config = types.EmbedContentConfig(
        output_dimensionality=expected_dims,
        task_type=_TASK_TYPE_DOCUMENT,
    )

    for start in range(0, len(chunks), _BATCH_SIZE):
        batch = chunks[start : start + _BATCH_SIZE]
        response = client.models.embed_content(
            model=config.embedding_model,
            contents=batch,
            config=embed_config,
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
            # gemini-embedding-001 ở <3072 chiều KHÔNG normalize sẵn → tự L2-normalize.
            results.append((text, _l2_normalize(vector)))

    logger.info("[embed] %d/%d chunk ra vector hợp lệ", len(results), len(chunks))
    return results
