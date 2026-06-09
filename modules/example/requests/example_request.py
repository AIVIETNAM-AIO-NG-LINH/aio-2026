"""Request demo cho module Example — minh hoạ cách dùng `BaseFormRequest`.

Tách tầng **validate** (request này) khỏi tầng **output** (`ExampleSerializer`),
đúng như Laravel tách `FormRequest` khỏi `Resource`:

  - Khai báo field như `rules()`; set `error_messages` cho message tuỳ biến.
  - Field-level validate: `validate_<field>()` (≈ rule riêng từng field).
  - Cross-field / DB-touching validate: override `validate()` (≈ `after()`).
  - Có DTO: `to_dto()` đọc `validated_data` → DTO; Service chỉ nhận DTO (không
    biết tới HTTP/request).

Một class `ExampleRequest` xài chung cho **create (POST)** và **update (PUT)** —
phân nhánh bằng `is_creating()` / `is_updating()` / `route_id()` thừa hưởng từ
`FormRequestMixin`. Khi `is_valid(raise_exception=True)` fail, mixin ném
`RequestValidationException` → handler trả HTTP 422 shape V1 (FE không phải đổi).
"""

from __future__ import annotations

from dataclasses import dataclass

from rest_framework import serializers

from modules.base.requests import BaseFormRequest

from ..models import Example


@dataclass(frozen=True)
class ExampleDTO:
    """DTO bất biến truyền vào Service — Service không cần biết tới request/HTTP."""

    name: str
    description: str
    is_active: bool


class ExampleRequest(BaseFormRequest):
    """Validate payload tạo/sửa `Example`.

    `BaseFormRequest` = `FormRequestMixin` + `serializers.Serializer`, nên ở đây
    chỉ cần khai báo field + luật như bên Laravel `rules()`.
    """

    name = serializers.CharField(
        max_length=255,
        error_messages={
            "required": "Tên là bắt buộc",
            "blank": "Tên không được để trống",
            "max_length": "Tên tối đa 255 ký tự",
        },
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )
    is_active = serializers.BooleanField(required=False, default=True)

    # FE legacy gửi field array dạng chuỗi JSON? Override `to_internal_value` rồi
    # `decode_json_inputs` TRƯỚC khi gọi super (giữ lại làm mẫu — Example không có
    # field array nên hiện không cần):
    #
    #     def to_internal_value(self, data):
    #         data = self.decode_json_inputs(data, ["tag_ids"])
    #         return super().to_internal_value(data)

    def validate_name(self, value: str) -> str:
        """Field-level: trim 2 đầu và chặn chuỗi chỉ toàn khoảng trắng."""
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Tên không được để trống")
        return value

    def validate(self, attrs: dict) -> dict:
        """Cross-field / DB: tên không được trùng (loại chính nó khi update)."""
        qs = Example.objects.filter(name=attrs["name"])
        if self.is_updating():
            # route_id() lấy id từ URL — loại bản ghi đang sửa khỏi check trùng.
            qs = qs.exclude(pk=self.route_id())
        if qs.exists():
            raise serializers.ValidationError({"name": "Tên đã tồn tại"})
        return attrs

    def to_dto(self) -> ExampleDTO:
        """`validated_data` → DTO. Gọi SAU `is_valid()`."""
        data = self.validated_data
        return ExampleDTO(
            name=data["name"],
            description=data.get("description", ""),
            is_active=data.get("is_active", True),
        )
