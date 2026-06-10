"""Nạp Celery app khi Django khởi động để `@shared_task` dùng chung 1 app.

Import này phải chạy lúc Python load package `config`, nên đặt ở __init__.py
(theo pattern chuẩn của Django + Celery).
"""
from .celery import app as celery_app

__all__ = ("celery_app",)
