"""Tích hợp Google ADK (Agent Development Kit) cho luồng chat.

Thay vì gọi thẳng Gemini `generate_content_stream`, luồng chat chạy qua ADK:
  Agent (có tool RAG) + Runner (StreamingMode.SSE) + InMemorySessionService.

Khác ga-ai (chạy ASGI/async), ai-aio chạy WSGI/gunicorn (sync) nên dùng
`Runner.run()` (generator ĐỒNG BỘ) hợp với `StreamingHttpResponse`, và
`async_to_sync` cho thao tác session.
"""

from __future__ import annotations

import os

# ADK gọi tool (hàm sync) bên trong vòng lặp async của Runner. Nếu tool có chạm
# Django ORM, Django chặn truy cập DB trong async context trừ khi bật cờ này. Tool
# RAG ở đây chỉ gọi HTTP (OpenSearch/Gemini) nên thực ra an toàn, nhưng set sẵn cho
# nhất quán với ga-ai và phòng tool tương lai có chạm ORM.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
