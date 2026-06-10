"""Request validate cho endpoint nội bộ truy hồi chunk chatbot.

Body: `{ "query": <str>, "top_k"?: <int>, "top_n"?: <int> }`. `top_k`/`top_n` tuỳ
chọn — vắng thì Service lấy default từ env (RETRIEVE_TOP_K / RETRIEVE_TOP_N). Tầng
này CHỈ validate dạng dữ liệu; logic search nằm ở `RetrieveService`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from rest_framework import serializers

from modules.base.requests import BaseFormRequest


@dataclass(frozen=True)
class RetrieveDTO:
    """DTO bất biến truyền vào Service. `top_k`/`top_n` None → Service dùng default env."""

    query: str
    top_k: Optional[int]
    top_n: Optional[int]


class RetrieveRequest(BaseFormRequest):
    """Validate payload `{ "query": <str>, "top_k"?: <int>, "top_n"?: <int> }`."""

    query = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            "required": "query là bắt buộc",
            "blank": "query không được rỗng",
        },
    )
    top_k = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=50,
        error_messages={
            "invalid": "top_k phải là số nguyên",
            "min_value": "top_k phải lớn hơn 0",
            "max_value": "top_k tối đa 50",
        },
    )
    top_n = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=200,
        error_messages={
            "invalid": "top_n phải là số nguyên",
            "min_value": "top_n phải lớn hơn 0",
            "max_value": "top_n tối đa 200",
        },
    )

    def to_dto(self) -> RetrieveDTO:
        """`validated_data` → DTO. Gọi SAU `is_valid()`."""
        return RetrieveDTO(
            query=self.validated_data["query"],
            top_k=self.validated_data.get("top_k"),
            top_n=self.validated_data.get("top_n"),
        )
