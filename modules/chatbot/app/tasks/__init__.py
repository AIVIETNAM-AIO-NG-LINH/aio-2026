"""Celery task của module Chatbot — tách theo mảng nghiệp vụ, mỗi mảng 1 file.

- `ingest.py` — pipeline ingest tài liệu RAG (nặng, chạy nền).
- `purge.py`  — dọn OpenSearch/KG khi tài liệu bị gỡ khỏi kho.
- `chat.py`   — task phụ trợ sau mỗi lượt chat (auto-title, index LTM).

`app.autodiscover_tasks()` import package này; import các submodule dưới đây
để decorator `@shared_task` chạy và đăng ký task với Celery. Service bên ngoài
vẫn import như cũ: `from ..tasks import ingest_document`.
"""

from .chat import generate_conversation_title, index_chat_turn
from .ingest import ingest_document
from .purge import purge_document

__all__ = [
    "generate_conversation_title",
    "index_chat_turn",
    "ingest_document",
    "purge_document",
]
