"""Đọc file gốc từ S3 / object storage bằng boto3.

Tách riêng phần I/O với object storage để pipeline chỉ cần `read_bytes(key)`.
Hỗ trợ S3-compatible (MinIO) qua endpoint custom + path-style addressing.
"""

from __future__ import annotations

import logging

import boto3
from botocore.client import Config as BotoConfig

from .config import S3Config

logger = logging.getLogger(__name__)


class S3Reader:
    """Client mỏng quanh boto3 — chỉ phục vụ tải object về dạng bytes."""

    def __init__(self, config: S3Config) -> None:
        self._config = config
        self._client = self._build_client(config)

    @staticmethod
    def _build_client(config: S3Config):
        """Khởi tạo boto3 S3 client từ cấu hình env.

        `use_path_style` cần cho MinIO/S3-compatible (URL dạng endpoint/bucket/key
        thay vì virtual-host bucket.endpoint). Để boto3 tự lấy creds từ môi trường
        nếu access/secret key không set (rỗng → truyền None).
        """
        addressing = "path" if config.use_path_style else "auto"
        return boto3.client(
            "s3",
            endpoint_url=config.endpoint or None,
            region_name=config.region or None,
            aws_access_key_id=config.access_key or None,
            aws_secret_access_key=config.secret_key or None,
            config=BotoConfig(s3={"addressing_style": addressing}),
        )

    def read_bytes(self, file_name: str) -> bytes:
        """Tải object `{MEDIA_FOLDER}/{file_name}` từ bucket, trả về bytes.

        Raise (botocore ClientError…) nếu object không tồn tại / lỗi quyền — caller
        (pipeline) bắt và đánh document FAILED.
        """
        key = self._config.object_key(file_name)
        logger.info("[s3] GET s3://%s/%s", self._config.bucket, key)
        response = self._client.get_object(Bucket=self._config.bucket, Key=key)
        return response["Body"].read()
