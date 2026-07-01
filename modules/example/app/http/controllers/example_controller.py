"""Controller module Example — demo luồng Request → DTO → Service.

`list` / `retrieve` (đọc) dùng thẳng `ExampleSerializer` mặc định của
`ModelViewSet`. Các action ghi (`create` / `update` / `destroy`) được override để
đi qua tầng validate (`ExampleRequest`) và tầng nghiệp vụ (`ExampleService`),
giống cách Laravel inject `FormRequest` vào controller rồi gọi Service.

Lưu ý: `ExampleRequest` validate full payload (ngữ nghĩa PUT). PATCH
(`partial_update`) cũng route qua `update` nên cũng yêu cầu đủ field.
"""

from __future__ import annotations

from rest_framework import viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from ...models import Example
from ...serializers import ExampleSerializer
from ...services import ExampleService
from ..requests import ExampleRequest


class ExampleController(viewsets.ModelViewSet):
    """CRUD: list / create / retrieve / update / partial_update / destroy."""

    queryset = Example.objects.all()
    serializer_class = ExampleSerializer  # dùng cho list / retrieve (output).

    def create(self, request: Request, *args, **kwargs) -> Response:
        form = ExampleRequest(data=request.data, context=self.get_serializer_context())
        form.is_valid(raise_exception=True)  # fail → 422 shape V1 qua exception handler.
        return ExampleService().store(form.to_dto())

    def update(self, request: Request, *args, **kwargs) -> Response:
        form = ExampleRequest(data=request.data, context=self.get_serializer_context())
        form.is_valid(raise_exception=True)
        return ExampleService().update(kwargs["pk"], form.to_dto())

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        return ExampleService().destroy(kwargs["pk"])
