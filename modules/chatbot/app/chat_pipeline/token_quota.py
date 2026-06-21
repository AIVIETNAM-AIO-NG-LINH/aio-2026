"""Client hạn mức TOKEN chat của member — gọi api-aio (service-to-service).

api-aio giữ hạn mức token/ngày của member, expose 2 endpoint NỘI BỘ (gate
`X-Internal-Token`, route qua nginx-aio — xem `modules.base.clients.internal`):

  - POST /api/internal/v1/chatbot/tokens/check   {user_id}
        → {allowed, unlimited, limit, used, remaining}   (KHÔNG trừ)
  - POST /api/internal/v1/chatbot/tokens/record  {user_id, tokens}
        → {unlimited, limit, used, remaining}            (cộng token thực)

Token KHÔNG biết trước nên tách 2 bước: `check_quota` TRƯỚC khi gọi LLM (còn
budget không), `record_usage` SAU khi LLM trả lời (cộng tổng token thực đã tiêu).
"""

from __future__ import annotations

import logging

from modules.base.clients.internal import call_api

logger = logging.getLogger(__name__)

_CHECK_PATH = "/api/internal/v1/chatbot/tokens/check"
_RECORD_PATH = "/api/internal/v1/chatbot/tokens/record"


class QuotaUnavailable(Exception):
    """Không XÁC NHẬN được hạn mức (api-aio lỗi/404/shape lạ).

    Khác với "hết hạn mức" (xác nhận được, `allowed=false`): đây là chưa biết còn
    budget hay không. Caller fail-CLOSED — chặn chat (503), không cho qua, để hạn
    mức không bị bỏ lọt khi api-aio chập chờn.
    """


def check_quota(user_id: int) -> bool:
    """Hỏi api-aio member còn budget token hôm nay không → True nếu được phép chat.

    FAIL-CLOSED: không gọi/parse được api-aio (lỗi mạng/5xx, 404 user, shape lạ) →
    raise `QuotaUnavailable` để caller CHẶN chat (không đoán bừa là còn budget).
    Chỉ trả True/False khi api-aio xác nhận rõ qua field `allowed`.
    """
    try:
        data = call_api(_CHECK_PATH, "POST", json={"user_id": user_id})
    except Exception as exc:
        logger.warning(
            "[chat] check token quota lỗi (user=%s) → chặn", user_id, exc_info=True
        )
        raise QuotaUnavailable(str(exc)) from exc
    if not isinstance(data, dict) or "allowed" not in data:
        logger.warning("[chat] check token quota shape lạ (user=%s): %r", user_id, data)
        raise QuotaUnavailable("phản hồi api-aio thiếu field 'allowed'")
    return bool(data["allowed"])


def record_usage(user_id: int, tokens: int) -> None:
    """Ghi nhận `tokens` member vừa tiêu (cộng vào hạn mức ngày bên api-aio).

    FAIL-SAFE: lỗi gọi service chỉ log — KHÔNG để nổi lên làm hỏng lượt chat đã
    sinh xong. Bỏ qua khi `tokens <= 0` (không có gì để cộng).
    """
    if tokens <= 0:
        return
    try:
        call_api(_RECORD_PATH, "POST", json={"user_id": user_id, "tokens": tokens})
    except Exception:
        logger.warning(
            "[chat] record token usage lỗi (user=%s tokens=%s)",
            user_id,
            tokens,
            exc_info=True,
        )
