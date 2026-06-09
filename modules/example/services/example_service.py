"""Service demo cho module Example — minh hoạ cách dùng `BaseService`.

Service chỉ nhận **DTO** (không biết tới HTTP/request) và trả về `Response` qua
các helper của `BaseService` để giữ nguyên shape FE của V1:

  - `response_success()` — wrap `{ data: { ..., success: 1 } }`.
  - `code_gone()`        — sugar raise 410 cho "resource không còn tồn tại".
"""

from __future__ import annotations

from rest_framework import status as http_status
from rest_framework.response import Response

from modules.base.services import BaseService

from ..models import Example
from ..requests import ExampleDTO
from ..serializers import ExampleSerializer


class ExampleService(BaseService):
    """Nghiệp vụ CRUD cho `Example` — tách khỏi view/validate."""

    def store(self, dto: ExampleDTO) -> Response:
        """Tạo mới từ DTO → 201 + bản ghi đã serialize."""
        example = Example.objects.create(
            name=dto.name,
            description=dto.description,
            is_active=dto.is_active,
        )
        return self.response_success(
            ExampleSerializer(example).data,
            status=http_status.HTTP_201_CREATED,
        )

    def update(self, example_id: int | str, dto: ExampleDTO) -> Response:
        """Cập nhật theo id; không thấy → 410 Gone (convention nội bộ của base)."""
        example = Example.objects.filter(pk=example_id).first()
        if example is None:
            self.code_gone("Example không tồn tại")  # NoReturn — dừng tại đây.
        example.name = dto.name
        example.description = dto.description
        example.is_active = dto.is_active
        # updated_at có auto_now=True → phải nằm trong update_fields mới được set.
        example.save(update_fields=["name", "description", "is_active", "updated_at"])
        return self.response_success(ExampleSerializer(example).data)

    def destroy(self, example_id: int | str) -> Response:
        """Xoá theo id; không thấy → 410 Gone."""
        example = Example.objects.filter(pk=example_id).first()
        if example is None:
            self.code_gone("Example không tồn tại")
        example.delete()
        return self.response_success({"id": int(example_id)})
