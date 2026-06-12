"""Tạo session ADK cho 1 lượt chat và inject lịch sử hội thoại từ DB.

Session service của ADK là async; ở WSGI (sync) ta gói toàn bộ phần chuẩn bị
session vào MỘT coroutine rồi chạy qua `async_to_sync` đúng một lần (tránh tạo/huỷ
event loop nhiều lần). Lịch sử (STM) lấy từ bảng `chatbot_messages` được nạp dưới
dạng Event user/model vào session, giống cách ga-ai inject history.
"""

from __future__ import annotations

from asgiref.sync import async_to_sync
from google.adk.events import Event, EventActions
from google.adk.sessions import BaseSessionService, Session
from google.genai import types

from .constants import APP_NAME, ROOT_AGENT_NAME


async def _create_session_with_history(
    session_service: BaseSessionService,
    user_id: str,
    history_contents: list[types.Content],
) -> Session:
    """Tạo session mới rồi append từng Content lịch sử thành Event (cũ → mới)."""
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
    )
    for content in history_contents:
        author = "user" if content.role == "user" else ROOT_AGENT_NAME
        await session_service.append_event(
            session,
            Event(content=content, author=author, actions=EventActions()),
        )
    return session


def create_session_with_history(
    session_service: BaseSessionService,
    user_id: str,
    history_contents: list[types.Content],
) -> Session:
    """Bản sync của `_create_session_with_history` (dùng trong view WSGI)."""
    return async_to_sync(_create_session_with_history)(
        session_service, user_id, history_contents
    )
