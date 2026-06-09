"""Base Request cho module mới — bản Django/DRF của `BaseFormDataRequestV2`.

Laravel `FormRequest` là tầng validate chạy trước controller; ở DRF vai trò đó là
**Serializer**. Nên đây là một base serializer giữ nguyên:
  - Shape lỗi 422 của V1 (để FE không phải đổi):
    `{ data: { status: 422, message, data: { field: first error } } }`
  - Các helper lặp lại: route_id / is_creating / is_updating / enum_or_null /
    decode_json_inputs.

Cung cấp 2 thứ:
  - `FormRequestMixin` — toàn bộ helper + override `is_valid()` để ném lỗi 422 shape V1.
    Trộn với `ModelSerializer` khi cần request gắn model.
  - `BaseFormRequest` = mixin + `serializers.Serializer` (request thường, không gắn model).

Cố ý KHÔNG port:
  - `authorize()` / `rules()` / `messages()`: DRF tách authz sang permission classes,
    còn "rules/messages" là field + error_messages của serializer.
  - `validateOrganizationAccessible()`: phụ thuộc module Organization + CurrentAdmin
    (chưa có ở project này) — không phải logic base-generic. Khi có module Organization
    thì đặt ở base request của module đó, không nhét vào base chung.

Convention subclass:
  - Khai báo field như rules(); set `error_messages` cho message tuỳ biến.
  - Cross-field/DB-touching validate: override `validate()` (≈ after()).
  - FE legacy stringify field array: override `to_internal_value()` rồi gọi
    `self.decode_json_inputs(data, [...])` trước `super().to_internal_value()`.
  - Có DTO: thêm method `to_dto()` đọc `validated_data`; Service chỉ nhận DTO.
"""

from __future__ import annotations

import enum
import json
from typing import TYPE_CHECKING, Any, Optional, Type, TypeVar

from rest_framework import serializers

from ..exceptions import RequestValidationException

TEnum = TypeVar("TEnum", bound=enum.Enum)

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView

    # CHỈ lúc type-check: coi mixin như một Serializer để `super().is_valid()`,
    # `self.errors`, `self.context`, `self.initial_data`, `self.validated_data`...
    # được nhận diện đúng kiểu (thay vì `Any`). Runtime base vẫn là `object` — class
    # con tự trộn `Serializer`/`ModelSerializer` thật nên không đụng metaclass/MRO.
    _SerializerBase = serializers.Serializer
else:
    _SerializerBase = object


class FormRequestMixin(_SerializerBase):
    """Helper + reshape lỗi 422 — trộn với bất kỳ Serializer/ModelSerializer nào."""

    #: Message cho lỗi 422 (override hoặc bọc gettext để i18n).
    invalid_data_message: str = "Invalid data transmission"

    def is_valid(self, *, raise_exception: bool = False) -> bool:
        """Như DRF nhưng khi fail + raise thì ném `RequestValidationException` (422 shape V1)."""
        valid: bool = super().is_valid(raise_exception=False)
        if not valid and raise_exception:
            raise RequestValidationException(
                fields=self._first_errors(),
                message=self.invalid_data_message,
            )
        return valid

    def _first_errors(self) -> dict[str, str]:
        """Lấy lỗi ĐẦU TIÊN mỗi field — mirror `$errors->get($key, [])[0]`."""
        out: dict[str, str] = {}
        for field, errs in self.errors.items():
            if isinstance(errs, list) and errs:
                out[field] = str(errs[0])
            else:
                out[field] = str(errs)
        return out

    # --- Helper ngữ cảnh HTTP (lấy từ serializer context) -------------------

    def route_id(self) -> int:
        """≈ `routeId()` — id resource từ URL; 0 nghĩa là create."""
        view: Optional[APIView] = self.context.get("view")
        if view is None:
            return 0
        # view.kwargs là `dict[str, Any]` (path param không có kiểu tĩnh). Coi value
        # là `object` để CHÍNH `.get()` được type-hint thành `object` (hết `Any`),
        # rồi narrow bằng isinstance trước khi int().
        kwargs: dict[str, object] = view.kwargs
        raw = kwargs.get("id", kwargs.get("pk"))
        if not isinstance(raw, (str, int)):
            return 0
        try:
            return int(raw)
        except ValueError:
            return 0

    def is_creating(self) -> bool:
        """≈ `isCreating()` — create = POST."""
        request: Optional[Request] = self.context.get("request")
        return bool(request and request.method == "POST")

    def is_updating(self) -> bool:
        """≈ `isUpdating()` — ngược của create (PUT/PATCH)."""
        return not self.is_creating()

    # --- Helper cast/normalize input ---------------------------------------

    def enum_or_null(self, key: str, enum_cls: Type[TEnum]) -> Optional[TEnum]:
        """≈ `enumOrNull()` — input → Enum theo value, hoặc None.

        None nếu field không gửi, rỗng, hoặc value không khớp member (≈ tryFrom).
        """
        data = getattr(self, "initial_data", {}) or {}
        if key not in data:
            return None
        value = data.get(key)
        if value is None or value == "":
            return None
        try:
            return enum_cls(value)
        except ValueError:
            return None

    @staticmethod
    def decode_json_inputs(data: Any, keys: list[str]) -> dict[str, Any]:
        """≈ `decodeJsonInputs()` — decode field gửi dạng stringified JSON về list/dict.

        Trả về dict mới: chỉ thay key khi decode ra list/dict; còn lại giữ nguyên
        để rule kiểu (`ListField`...) báo lỗi đúng field nếu FE gửi sai.
        """
        result = dict(data)
        for key in keys:
            value = result.get(key)
            if isinstance(value, str) and value != "":
                try:
                    decoded = json.loads(value)
                except (ValueError, TypeError):
                    continue
                if isinstance(decoded, (list, dict)):
                    result[key] = decoded
        return result


class BaseFormRequest(FormRequestMixin, serializers.Serializer):
    """Base request thường (không gắn model) — clone `BaseFormDataRequestV2`.

    Request gắn model: tự trộn `class XRequest(FormRequestMixin, serializers.ModelSerializer)`.
    """
