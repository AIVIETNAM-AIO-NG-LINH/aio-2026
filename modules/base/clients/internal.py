"""Client gọi service nội bộ qua reverse-proxy nginx:8080 (không ra internet).

Hàm dùng chung ở base — gọi api-aio (Laravel) từ bất kỳ module nào:
    from modules.base.clients.internal import call_api
    data = call_api("/api/internal/ping")

- Kết nối tới settings.INTERNAL_GATEWAY_URL (http://nginx-aio:8080).
- Định tuyến tới app đích bằng Host header (nginx route theo server_name).
- Xác thực bằng X-Internal-Token (secret dùng chung, không gắn user).
"""
from __future__ import annotations

from typing import Any

from django.conf import settings


def _headers(host: str) -> dict[str, str]:
    return {
        "Host": host,
        "X-Internal-Token": settings.INTERNAL_TOKEN,
        "Accept": "application/json",
    }


def call_api(path: str, method: str = "GET", *, json: Any = None, timeout: float = 5.0) -> Any:
    """Gọi sang api-aio (Laravel). `path` bắt đầu bằng /api/internal/ ."""
    import requests  # lazy import: chỉ cần khi thực sự gọi HTTP

    url = f"{settings.INTERNAL_GATEWAY_URL}{path}"
    resp = requests.request(
        method, url, json=json, headers=_headers(settings.INTERNAL_API_HOST), timeout=timeout
    )
    resp.raise_for_status()
    return resp.json() if resp.content else None
