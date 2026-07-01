"""Client S3 / object storage (MinIO-compatible) dùng chung ở base.

Một class tự quản trọn vòng đời: đọc cấu hình từ env (12-factor), khởi tạo
boto3 client, và expose thao tác đọc object. Bên ngoài KHÔNG tự dựng config
hay boto3 client — chỉ gọi method:

    from modules.base.app.clients.s3_client import S3Client
    file_bytes = S3Client().read_bytes(media.file_name)   # tải object (cần boto3)
    link = S3Client().public_url(media.file_name)         # dựng URL công khai (KHÔNG cần boto3)

`boto3` chỉ import + khởi tạo client LAZY ở lần `read_bytes()` đầu tiên — nên
`public_url()` (chỉ ghép chuỗi từ env) chạy được cả ở image slim (web/chat không
cài deps RAG). Worker ingest mới thực sự cần boto3.
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
        # Base URL công khai để dựng link (== `AWS_URL` của api-aio). Bỏ trống →
        # tự suy từ endpoint (MinIO/path-style) hoặc bucket+region (AWS virtual-host).
        self._public_base = _env("AWS_S3_URL")
        # boto3 client dựng lazy (lần read_bytes đầu) — public_url không kích hoạt.
        self._boto_client: BotoS3Client | None = None

    @property
    def _client(self) -> BotoS3Client:
        """boto3 client (lazy) — chỉ dựng khi thực sự cần đọc object."""
        if self._boto_client is None:
            self._boto_client = self._build_client()
        return self._boto_client

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

    def public_url(self, file_name: str) -> str | None:
        """URL công khai của object `{MEDIA_FOLDER}/{file_name}` (chỉ ghép chuỗi).

        Dựng để khớp link api-aio sinh (`Storage::disk('s3')->url()`), theo thứ tự:
          1) `AWS_S3_URL` đặt sẵn → `{AWS_S3_URL}/{key}` (đáng tin nhất — đặt = `AWS_URL`).
          2) Có `AWS_S3_ENDPOINT` (MinIO/S3-compatible) → `{endpoint}/{bucket}/{key}`.
          3) Còn lại (AWS thật) → virtual-host `https://{bucket}.s3.{region}.amazonaws.com/{key}`.
        Thiếu cấu hình để dựng (không có base/endpoint/bucket) → None.
        """
        if not file_name:
            return None
        key = self._object_key(file_name)

        if self._public_base:
            return f"{self._public_base.rstrip('/')}/{key}"
        if self._endpoint:
            return f"{self._endpoint.rstrip('/')}/{self._bucket}/{key}"
        if self._bucket and self._region:
            return f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{key}"
        return None

    def read_bytes(self, file_name: str) -> bytes:
        """Tải object `{MEDIA_FOLDER}/{file_name}` từ bucket, trả về bytes.

        Raise (botocore ClientError…) nếu object không tồn tại / lỗi quyền — caller
        bắt và tự xử lý (vd pipeline đánh document FAILED).
        """
        key = self._object_key(file_name)
        logger.info("[s3] GET s3://%s/%s", self._bucket, key)
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()
