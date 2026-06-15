"""Celery app cho ai-aio — worker nền cho pipeline ingest tài liệu chatbot.

Pattern chuẩn Django + Celery:
  - Đọc cấu hình từ `django.conf:settings`, chỉ lấy các key prefix `CELERY_`
    (namespace="CELERY") — broker/result backend khai báo ở settings.py.
  - `autodiscover_tasks()` import module `tasks` trong từng app ở INSTALLED_APPS
    (vd package `modules.chatbot.app.tasks`) — task mới chỉ cần được re-export ở
    `tasks/__init__.py` là được nạp.

Khởi động worker:  celery -A config worker --loglevel=info
"""
from __future__ import annotations

import os

from celery import Celery

# Để Celery (chạy ngoài `manage.py`) biết settings module.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("ai_aio")

# Mọi key `CELERY_*` trong settings.py trở thành config của Celery.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Tự tìm modules/<app>/tasks.py trong các app đã cài.
app.autodiscover_tasks()
