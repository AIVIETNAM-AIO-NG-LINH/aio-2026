"""Client realtime — publish event xuống Redis cho node-aio đẩy ra WebSocket.

Cặp đôi với service `node-aio`: node-aio subscribe các channel `aio:user:<id>` và
`aio:broadcast` trên Redis dùng chung, rồi forward mọi message xuống FE đang mở
`ws://<host>/ws`. Phía Django chỉ cần PUBLISH đúng channel (cùng prefix `aio:`)
với payload envelope `{type, data}` — node-aio trải phẳng thành `{channel, type,
data}` cho FE.

    from modules.base.clients.realtime_client import RealtimeClient
    RealtimeClient().broadcast("chatbot.document.progress", {...})  # tất cả user
    RealtimeClient().to_user(5, "notify", {...})                    # 1 user

`redis` import lazy bên trong để module an toàn với image slim. Publish KHÔNG bao
giờ raise lên caller (lỗi Redis chỉ log) — realtime là phụ trợ, không được làm
hỏng luồng nghiệp vụ đang gọi.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


def _env(name: str, default: str = "") -> str:
    """Đọc env, strip khoảng trắng; rỗng/không set → default."""
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


class RealtimeClient:
    """Client mỏng quanh Redis pub/sub — publish event cho node-aio đẩy realtime.

    `prefix` mặc định `aio` PHẢI khớp `CHANNEL_PREFIX` của node-aio, nếu không FE
    sẽ không nhận được. Pub/sub của Redis không phân theo DB nên dùng chung URL
    với Celery broker là an toàn.
    """

    def __init__(self) -> None:
        self._url = _env(
            "REALTIME_REDIS_URL",
            default=_env("CELERY_BROKER_URL", default="redis://redis:6379/0"),
        )
        self._prefix = _env("REALTIME_CHANNEL_PREFIX", default="aio")
        self._client: Any = None  # lazy: chỉ kết nối khi publish lần đầu

    def _redis(self) -> Any:
        import redis  # lazy import: image slim không cần khi không publish

        if self._client is None:
            self._client = redis.Redis.from_url(self._url)
        return self._client

    def _channel(self, name: str) -> str:
        """Gắn prefix namespace, vd "broadcast" → "aio:broadcast"."""
        return f"{self._prefix}:{name}"

    def publish(self, channel: str, type: str, data: Any = None) -> int:
        """Publish envelope `{type, data}` (JSON) lên `aio:<channel>`.

        Trả số subscriber đã nhận (0 nếu node-aio chưa subscribe / không user nào
        online). Mọi lỗi Redis bị nuốt (log) → trả 0, không raise lên caller.
        """
        envelope = json.dumps({"type": type, "data": data}, default=str)
        ch = self._channel(channel)
        try:
            receivers = int(self._redis().publish(ch, envelope))
            logger.info("[realtime] publish %s -> %d subscriber", ch, receivers)
            return receivers
        except Exception:
            logger.exception("[realtime] lỗi publish %s (bỏ qua)", ch)
            return 0

    def broadcast(self, type: str, data: Any = None) -> int:
        """Push cho TOÀN BỘ user đang connect (channel `aio:broadcast`)."""
        return self.publish("broadcast", type, data)

    def to_user(self, user_id: Any, type: str, data: Any = None) -> int:
        """Push cho 1 user theo id (channel `aio:user:<id>`)."""
        return self.publish(f"user:{user_id}", type, data)


@lru_cache(maxsize=1)
def realtime_client() -> RealtimeClient:
    """Trả về `RealtimeClient` dùng chung cả process (1 connection pool).

    redis-py khuyến nghị tái dùng MỘT client thay vì dựng lại mỗi lần publish —
    client tự quản connection pool bên trong. Cache theo process nên an toàn với
    Celery (mỗi worker fork khởi tạo client riêng ở lần publish đầu, sau fork).

        from modules.base.clients.realtime_client import realtime_client
        realtime_client().broadcast("...", {...})
    """
    return RealtimeClient()
