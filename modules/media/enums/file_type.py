"""Phân loại media — clone của `Modules\\Media\\Enums\\V1\\FileType` (api-aio)."""

from __future__ import annotations

from django.db import models


class FileType(models.TextChoices):
    """Phân loại media thành 8 nhóm display, lưu ở cột `media.file_type`.

    PDF | EXCEL | WORD | POWERPOINT | IMAGE | VIDEO | ZIP | FILE.

    Chỉ dùng để cast/đọc giá trị cột `file_type` ra enum — việc phân loại tại
    upload time nằm ở service api-aio, module này không xử lý upload.
    """

    PDF = "PDF"
    EXCEL = "EXCEL"
    WORD = "WORD"
    POWERPOINT = "POWERPOINT"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    ZIP = "ZIP"
    FILE = "FILE"
