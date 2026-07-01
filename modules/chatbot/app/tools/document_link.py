"""Tool lấy LINK công khai của tài liệu nguồn theo `media_id` — KHÔNG sinh câu trả lời.

Một function thuần `get_url()` (stateless): media_id → URL tải/preview file gốc.
Tách khỏi `knowledge_base.search` để LLM TỰ QUYẾT khi nào cần link (user hỏi link,
hoặc muốn dẫn nguồn bấm được) thay vì luôn gắn url vào mọi chunk. Dùng bởi ADK agent
qua `adk/tools.py` (`get_document_url`).

URL dựng từ env S3 qua `Media.url`, đi qua `MediaRepository` (KHÔNG query
`Media.objects` trực tiếp) theo convention module.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def get_url(media_id: int) -> dict | None:
    """media_id → {media_id, original_name, url} hoặc None nếu không tìm thấy.

    Fail-soft: lỗi DB/cấu hình → None (caller xử lý), KHÔNG raise giữa request chat.
    `url` có thể None nếu thiếu cấu hình S3.
    """
    try:
        from modules.media.app.repositories import MediaRepository

        media = MediaRepository().find(int(media_id))
    except (TypeError, ValueError):
        return None
    except Exception:
        logger.exception("[doc-link] resolve media lỗi (media_id=%s)", media_id)
        return None

    if media is None:
        return None

    return {
        "media_id": media.pk,
        "original_name": media.original_name,
        "url": media.url,
    }

