"""Khởi tạo + cache ADK Runner và session service dùng chung.

Runner bọc Agent + session service; cả hai stateless/đa-session-an-toàn nên cache 1
instance dùng chung cho mọi request đồng thời (mỗi request 1 session_id riêng).

ADK đọc API key từ env `GOOGLE_API_KEY`. Project này cấu hình `GEMINI_API_KEY`, nên
ta map sang `GOOGLE_API_KEY` (nếu chưa có) trước khi tạo Runner — giống ga-ai.
"""

from __future__ import annotations

import os

from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService, InMemorySessionService

from .agent import create_root_agent
from .constants import APP_NAME

# Session service dùng chung (in-memory). Mỗi lượt chat tạo 1 session riêng rồi
# inject lịch sử từ DB (chatbot_messages) — DB là nguồn sự thật, không phụ thuộc
# session bền vững (chạy đúng cả khi gunicorn nhiều worker).
_session_service: InMemorySessionService = InMemorySessionService()

_runner: Runner | None = None


def _ensure_google_api_key() -> None:
    """Map GEMINI_API_KEY → GOOGLE_API_KEY cho ADK (nếu GOOGLE_API_KEY chưa set)."""
    if not os.environ.get("GOOGLE_API_KEY"):
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key


def get_session_service() -> BaseSessionService:
    """Trả session service dùng chung."""
    return _session_service


def get_runner() -> Runner:
    """Lấy Runner (tạo lười, cache). An toàn gọi đồng thời với session_id khác nhau."""
    global _runner
    if _runner is None:
        _ensure_google_api_key()
        _runner = Runner(
            app_name=APP_NAME,
            agent=create_root_agent(),
            session_service=_session_service,
        )
    return _runner
