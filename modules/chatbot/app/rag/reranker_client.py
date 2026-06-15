"""Rerank ứng viên hybrid bằng cross-encoder QUA HTTP (pluggable, không load model).

Django/worker KHÔNG nạp model nặng — chỉ POST (query, [chunk_text]) tới một endpoint
rerank ngoài cấu hình bằng env và nhận điểm liên quan để xếp lại. Tương thích các
schema phổ biến (TEI/BGE rerank, Jina, Cohere-style):

  Request : {"model": <model>, "query": <q>, "documents": [<text>, ...]}
  Response: [{"index": i, "score": s}, ...]            (TEI / BGE rerank server)
       hoặc {"results": [{"index": i, "relevance_score": s}, ...]}  (Jina/Cohere)

FAIL-SAFE: tắt qua env, thiếu endpoint, hay BẤT KỲ lỗi/timeout HTTP nào → trả lại
NGUYÊN danh sách ứng viên theo thứ hạng hybrid (không ném lỗi ra ngoài).
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from .config import RerankConfig

logger = logging.getLogger(__name__)


def _parse_scores(payload: Any, count: int) -> list[float] | None:
    """Chuẩn hoá nhiều schema response → list điểm theo ĐÚNG thứ tự documents gửi đi.

    Trả None nếu không nhận dạng được (caller fallback giữ thứ hạng hybrid).
    """
    # Cohere/Jina: {"results": [{"index": i, "relevance_score": s}]}
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        items = payload["results"]
    # TEI/BGE rerank: [{"index": i, "score": s}]
    elif isinstance(payload, list):
        items = payload
    else:
        return None

    scores = [None] * count
    for item in items:
        if not isinstance(item, dict):
            return None
        idx = item.get("index")
        score = item.get("score", item.get("relevance_score"))
        if not isinstance(idx, int) or not (0 <= idx < count) or score is None:
            continue
        scores[idx] = float(score)
    # Cần đủ điểm cho mọi document mới rerank được; thiếu → fallback.
    if any(s is None for s in scores):
        return None
    return scores  # type: ignore[return-value]


def rerank(
    query: str,
    candidates: list[dict[str, Any]],
    config: RerankConfig,
) -> list[dict[str, Any]]:
    """Xếp lại `candidates` theo điểm cross-encoder; gắn `rerank_score` vào mỗi item.

    `candidates` là list dict có khoá `chunk_text`. Trả về list ĐÃ xếp lại (giảm dần).
    Tắt / chưa cấu hình / lỗi → trả nguyên thứ tự đầu vào (fail-safe).
    """
    if not config.enabled or not config.endpoint_url or not candidates:
        return candidates

    documents = [c.get("chunk_text", "") for c in candidates]
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    try:
        response = requests.post(
            config.endpoint_url,
            json={"model": config.model, "query": query, "documents": documents},
            headers=headers,
            timeout=config.timeout,
        )
        response.raise_for_status()
        scores = _parse_scores(response.json(), len(candidates))
    except Exception:
        logger.exception("[rerank] lỗi gọi endpoint, giữ thứ hạng hybrid")
        return candidates

    if scores is None:
        logger.warning("[rerank] response không nhận dạng được schema, giữ thứ hạng hybrid")
        return candidates

    ranked = [
        {**candidate, "rerank_score": score}
        for candidate, score in zip(candidates, scores)
    ]
    ranked.sort(key=lambda c: c["rerank_score"], reverse=True)
    logger.info("[rerank] đã rerank %d ứng viên", len(ranked))
    return ranked
