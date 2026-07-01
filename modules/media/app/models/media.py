"""Model `Media` — clone của `Modules\\Media\\Models\\Media` (api-aio).

Module này CHỈ đọc dữ liệu media từ bảng `media` (bảng do service api-aio sở hữu
và ghi). Không có tác vụ upload file ở đây — chỉ expose model + accessor để query.
"""

from __future__ import annotations

from django.db import models

from modules.base.app.models import SoftDeleteModel
from modules.media.app.enums import FileType

# Mime chuẩn của từng loại tài liệu — dùng cho `document_kind` (ưu tiên mime
# trước vì cột `file_type` do client khai, có thể sai/thiếu).
_PDF_MIMES = {"application/pdf"}
_WORD_MIMES = {
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class Media(SoftDeleteModel):
    """Bản ghi file media (read-only ở service này)."""

    TABLE = "media"

    COL_FILE_NAME = "file_name"
    COL_ORIGINAL_NAME = "original_name"
    COL_MIME_TYPE = "mime_type"
    COL_TYPE = "type"
    COL_FILE_TYPE = "file_type"
    COL_SIZE = "size"

    file_name = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=255, null=True, blank=True)
    file_type = models.CharField(max_length=20, choices=FileType.choices)
    # Dung lượng file, đơn vị MB (2 số sau dấu phẩy).
    size = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta(SoftDeleteModel.Meta):
        db_table = "media"  # = Media.TABLE (Meta lồng nhau không ref được const class)
        # Bảng `media` do service khác sở hữu/ghi — Django chỉ đọc, KHÔNG tạo/migrate.
        managed = False

    def __str__(self) -> str:
        return self.original_name

    @property
    def document_kind(self) -> str | None:
        """Loại tài liệu để ingest: "PDF" / "WORD" (value của `FileType`), hoặc
        `None` nếu không phải tài liệu hỗ trợ. Ưu tiên `mime_type`, fallback
        `file_type`."""
        mime = (self.mime_type or "").strip().lower()
        ftype = (self.file_type or "").strip().upper()

        if mime in _PDF_MIMES or ftype == FileType.PDF:
            return FileType.PDF.value
        if mime in _WORD_MIMES or ftype == FileType.WORD:
            return FileType.WORD.value
        return None

    @property
    def url(self) -> str | None:
        """URL công khai của file trên S3/object storage — dựng từ env `AWS_S3_*`
        qua {@link S3Client.public_url} (cùng nguồn object key với lúc ingest đọc
        file). Khớp link api-aio sinh ra. None nếu thiếu cấu hình S3 hoặc lỗi —
        caller tự xử fallback."""
        # Import cục bộ: tránh phụ thuộc boto3 lúc import model (public_url không
        # kích hoạt boto3 client — chỉ ghép chuỗi).
        from modules.base.app.clients.s3_client import S3Client

        try:
            return S3Client().public_url(self.file_name)
        except Exception:
            return None
