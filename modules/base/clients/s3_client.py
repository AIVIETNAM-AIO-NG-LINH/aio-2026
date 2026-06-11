"""Client S3 / object storage (MinIO-compatible) dùng chung ở base.

Một class tự quản trọn vòng đời: đọc cấu hình từ env (12-factor), khởi tạo
boto3 client, và expose thao tác đọc object. Bên ngoài KHÔNG tự dựng config
hay boto3 client — chỉ gọi method:

    from modules.base.clients.s3_client import S3Client
    file_bytes = S3Client().read_bytes(media.file_name)

`boto3` import lazy bên trong class để module này an toàn với image slim
(web không cài deps RAG) — chỉ worker thực sự dùng mới cần boto3.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # stub `boto3-stubs[s3]` — chỉ tồn tại lúc type check
    from mypy_boto3_s3 import S3Client as BotoS3Client

logger = logging.getLogger(__name__)


def _env(name: str, default: str = "") -> str:
    """Đọc env, strip khoảng trắng; rỗng/không set → default."""
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


class S3Client:
    """Client mỏng quanh boto3 — tải object từ bucket cấu hình qua env `AWS_S3_*`."""

    def __init__(self) -> None:
        self._endpoint = _env("AWS_S3_ENDPOINT")
        self._region = _env("AWS_S3_REGION")
        self._bucket = _env("AWS_S3_BUCKET")
        self._access_key = _env("AWS_S3_ACCESS_KEY")
        self._secret_key = _env("AWS_S3_SECRET_KEY")
        self._use_path_style = _env("AWS_S3_USE_PATH_STYLE").lower() in {"1", "true", "yes", "on"}
        self._media_folder = _env("MEDIA_FOLDER", default="media")
        self._client: BotoS3Client = self._build_client()

    def _build_client(self) -> BotoS3Client:
        """Khởi tạo boto3 S3 client.

        `use_path_style` cần cho MinIO/S3-compatible (URL dạng endpoint/bucket/key
        thay vì virtual-host bucket.endpoint). Để boto3 tự lấy creds từ môi trường
        nếu access/secret key không set (rỗng → truyền None).
        """
        import boto3  # lazy import: image slim (web) không cài boto3
        from botocore.client import Config as BotoConfig

        addressing = "path" if self._use_path_style else "auto"
        return boto3.client(
            "s3",
            endpoint_url=self._endpoint or None,
            region_name=self._region or None,
            aws_access_key_id=self._access_key or None,
            aws_secret_access_key=self._secret_key or None,
            config=BotoConfig(s3={"addressing_style": addressing}),
        )

    def _object_key(self, file_name: str) -> str:
        """Object key trên bucket = f"{MEDIA_FOLDER}/{file_name}" (folder có thể rỗng)."""
        folder = self._media_folder.strip("/")
        return file_name if folder == "" else f"{folder}/{file_name}"

    def read_bytes(self, file_name: str) -> bytes:
        """Tải object `{MEDIA_FOLDER}/{file_name}` từ bucket, trả về bytes.

        Raise (botocore ClientError…) nếu object không tồn tại / lỗi quyền — caller
        bắt và tự xử lý (vd pipeline đánh document FAILED).
        """
        key = self._object_key(file_name)
        logger.info("[s3] GET s3://%s/%s", self._bucket, key)
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()
