"""Service demo cho module Example — minh hoạ cách dùng `BaseService`.

Service chỉ nhận **DTO** (không biết tới HTTP/request) và trả về `Response` qua
các helper của `BaseService` để giữ nguyên shape FE của V1:

  - `response_success()` — wrap `{ data: { ..., success: 1 } }`.
  - `not_found()`        — sugar raise 404 cho "resource không tồn tại".
"""

from __future__ import annotations

from rest_framework import status as http_status
from rest_framework.response import Response

from modules.base.app.services import BaseService
from modules.base.app.supports import translate

from ..catalogs import ExampleCatalog
from ..models import Example
from ..http.requests import ExampleDTO
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
        """Cập nhật theo id; không thấy → 404 Not Found."""
        example = Example.objects.filter(pk=example_id).first()
        if example is None:
            # NoReturn — dừng tại đây.
            self.not_found(translate("Example không tồn tại", ExampleCatalog.NOT_FOUND))
        example.name = dto.name
        example.description = dto.description
        example.is_active = dto.is_active
        # updated_at có auto_now=True → phải nằm trong update_fields mới được set.
        example.save(update_fields=["name", "description", "is_active", "updated_at"])
        return self.response_success(ExampleSerializer(example).data)

    def destroy(self, example_id: int | str) -> Response:
        """Xoá theo id; không thấy → 404 Not Found."""
        example = Example.objects.filter(pk=example_id).first()
        if example is None:
            self.not_found(translate("Example không tồn tại", ExampleCatalog.NOT_FOUND))
        example.delete()
        return self.response_success({"id": int(example_id)})
