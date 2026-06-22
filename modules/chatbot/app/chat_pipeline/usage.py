"""Gom token usage của 1 lượt chat (cộng dồn qua các lần gọi LLM).

Một lượt chat ADK có thể gọi model NHIỀU lần (vòng lặp tool: lần quyết định gọi
tool, lần sinh câu trả lời...). Mỗi lần gọi, event cuối mang `usage_metadata`
(chuẩn google-genai). Class này cộng dồn các con số đó để ra TỔNG cho cả lượt.

Tách riêng (không nhét vào ChatService) để sau này tái dùng: đẩy ra SSE `done`,
lưu DB, hay tính chi phí — chỉ cần đọc các thuộc tính dưới đây.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.genai.types import GenerateContentResponseUsageMetadata


@dataclass
class TokenUsage:
    """Tổng token cộng dồn cho 1 lượt chat. Đơn vị: token.

    - `prompt_tokens`   : token đầu vào (prompt + lịch sử + kết quả tool).
    - `thinking_tokens` : token suy luận (chain-of-thought) nếu bật thoughts.
    - `output_tokens`   : token câu trả lời hiển thị (candidates).
    - `total_tokens`    : tổng do model báo (nguồn chuẩn để tính chi phí).
    - `llm_calls`       : số lần gọi model trong lượt (để soi vòng lặp tool).
    """

    prompt_tokens: int = 0
    thinking_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    llm_calls: int = 0

    def add(
        self, usage_metadata: GenerateContentResponseUsageMetadata | None
    ) -> None:
        """Cộng dồn `usage_metadata` của 1 event ADK (bỏ qua nếu None/rỗng).

        CHỈ gọi cho event FINAL của mỗi lần gọi model (`event.partial` False/None) —
        xem `chat_service._chunks`. Event partial (mẩu stream) CŨNG mang
        `usage_metadata` nhưng là CUMULATIVE (cộng dồn trong cùng lần gọi), nên nếu
        gọi `add` cho cả partial sẽ đếm lặp. Vì chỉ cộng final, mỗi `add` = 1 `llm_call`.
        """
        if usage_metadata is None:
            return
        self.prompt_tokens += usage_metadata.prompt_token_count or 0
        self.thinking_tokens += usage_metadata.thoughts_token_count or 0
        self.output_tokens += usage_metadata.candidates_token_count or 0
        self.total_tokens += usage_metadata.total_token_count or 0
        self.llm_calls += 1

    def summary(self) -> str:
        """Chuỗi gọn 1 dòng để log."""
        return (
            f"total={self.total_tokens} prompt={self.prompt_tokens} "
            f"thinking={self.thinking_tokens} output={self.output_tokens} "
            f"llm_calls={self.llm_calls}"
        )
