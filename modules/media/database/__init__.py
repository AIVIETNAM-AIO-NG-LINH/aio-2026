"""Tầng database của module Media (kiểu Laravel `database/`).

Hiện chứa `migrations/` — Django được trỏ tới đây qua `MIGRATION_MODULES` trong
config/settings.py (mặc định Django tìm migrations ở `<app>/migrations/`). Model
`Media` là `managed=False` (bảng do api-aio sở hữu) nên gói này thường rỗng.
"""
