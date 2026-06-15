"""Viết lại / mở rộng truy vấn trước hybrid search (Gemini Flash, song ngữ Việt↔Anh).

Kho dữ liệu song ngữ: câu hỏi tiếng Việt có thể cần khớp tài liệu tiếng Anh và
ngược lại. Bước này nhờ Gemini Flash chuẩn hoá câu hỏi + sinh thêm vài biến thể
(dịch sang ngôn ngữ còn lại, đồng nghĩa/diễn đạt khác) để tăng recall.

FAIL-SAFE tuyệt đối: tắt qua env, thiếu API key, hay BẤT KỲ lỗi nào khi gọi LLM
đều rơi về CHỈ dùng query gốc — truy hồi không bao giờ chết vì bước phụ này. Luôn
trả về list không rỗng và phần tử ĐẦU TIÊN luôn là query gốc (đã strip).
"""

from __future__ import annotations

import logging

from modules.base.clients.gemini_client import GeminiClient

from .config import QueryRewriteConfig

logger = logging.getLogger(__name__)

# Hướng dẫn model trả về mỗi biến thể trên 1 dòng, không đánh số/markdown để parse gọn.
_REWRITE_PROMPT = (
    "You rewrite a search query for a BILINGUAL (Vietnamese + English) document "
    "retrieval system. Given the user's query, produce up to {n} alternative search "
    "queries that improve recall: include a faithful translation into the OTHER "
    "language (Vietnamese<->English) and at most one paraphrase using synonyms or "
    "domain terms. Keep each variant short and keyword-focused. Do NOT answer the "
    "question. Return ONE variant per line, no numbering, no quotes, no extra text.\n\n"
    "QUERY: {query}"
)


def _parse_variants(raw: str) -> list[str]:
    """Tách output model thành các dòng sạch, bỏ bullet/đánh số đầu dòng."""
    variants: list[str] = []
    for line in (raw or "").splitlines():
        cleaned = line.strip().lstrip("-*0123456789.) ").strip()
        if cleaned:
            variants.append(cleaned)
    return variants


def rewrite_query(
    query: str,
    rewrite_config: QueryRewriteConfig,
) -> list[str]:
    """Trả danh sách truy vấn để search: [query_gốc, ...biến thể] (đã khử trùng lặp).

    Luôn có ít nhất 1 phần tử (query gốc). Tổng số bị chặn ở `max_variants`. Lỗi
    hoặc tắt → chỉ [query_gốc].
    """
    original = (query or "").strip()
    if not original:
        return []

    # Phần tử đầu LUÔN là query gốc — kể cả khi rewrite tắt/lỗi.
    variants: list[str] = [original]

    if not rewrite_config.enabled or rewrite_config.max_variants <= 1:
        return variants

    # Số biến thể thêm tối đa = max_variants - 1 (đã trừ query gốc).
    extra = rewrite_config.max_variants - 1
    try:
        prompt = _REWRITE_PROMPT.format(n=extra, query=original)
        raw = GeminiClient().generate_text([prompt], model=rewrite_config.model)
        for variant in _parse_variants(raw):
            if len(variants) >= rewrite_config.max_variants:
                break
            # Khử trùng lặp không phân biệt hoa thường (giữ bản xuất hiện trước).
            if variant.lower() not in {v.lower() for v in variants}:
                variants.append(variant)
        logger.info("[query_rewrite] %d biến thể (gồm query gốc)", len(variants))
    except Exception:
        # FAIL-SAFE: mọi lỗi → chỉ dùng query gốc.
        logger.exception("[query_rewrite] lỗi gọi LLM, fallback query gốc")
        return [original]

    return variants
