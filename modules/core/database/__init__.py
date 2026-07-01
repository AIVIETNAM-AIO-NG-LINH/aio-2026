"""Tầng database của module Core (kiểu Laravel `database/`).

Hiện chứa `migrations/` — Django được trỏ tới đây qua `MIGRATION_MODULES` trong
config/settings.py (mặc định Django tìm migrations ở `<app>/migrations/`). Core
chưa có model riêng nên gói này thường rỗng.
"""
