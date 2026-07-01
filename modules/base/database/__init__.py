"""Tầng database của module Base (kiểu Laravel `database/`).

Hiện chứa `migrations/` — Django được trỏ tới đây qua `MIGRATION_MODULES` trong
config/settings.py (mặc định Django tìm migrations ở `<app>/migrations/`). Các model
của Base đều abstract nên gói này thường rỗng.
"""
