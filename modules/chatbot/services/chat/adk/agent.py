"""Agent gốc của chatbot (ADK) — có tool RAG `search_knowledge_base`.

Agent là STATELESS (chỉ chứa config: model, instruction, tools) nên cache lại an
toàn để tái dùng giữa các request đồng thời. Model lấy từ env `GEMINI_CHAT_MODEL`.
"""

from __future__ import annotations

import functools

from google.adk.agents import Agent

from ..config import ChatConfig
from .constants import ROOT_AGENT_NAME
from .tools import search_knowledge_base

# Chỉ dẫn hệ thống — bám phong cách RAG grounded, song ngữ Việt/Anh, có trích nguồn.
AGENT_INSTRUCTION = (
    "Bạn là trợ lý AI của hệ thống AIO, trả lời câu hỏi dựa trên kho tài liệu nội bộ.\n\n"
    "## Công cụ\n"
    "- `search_knowledge_base`: tìm các đoạn tài liệu liên quan tới câu hỏi. HÃY GỌI "
    "tool này cho mọi câu hỏi cần thông tin từ tài liệu (chính sách, quy trình, sản phẩm, "
    "báo cáo...). Có thể gọi nhiều lần với truy vấn khác nhau nếu kết quả chưa đủ.\n\n"
    "## Quy tắc trả lời (NGHIÊM NGẶT)\n"
    "- Trả lời bằng ĐÚNG ngôn ngữ của câu hỏi người dùng.\n"
    "- CHỈ dựa trên kết quả tool và lịch sử hội thoại; TUYỆT ĐỐI không bịa thông tin ngoài "
    "tài liệu. Nếu tool không trả về thông tin liên quan, nói rõ là không tìm thấy trong "
    "tài liệu, đừng đoán.\n"
    "- Khi dùng thông tin từ một đoạn, nêu nguồn dạng (Nguồn: <tên tài liệu>, trang <số>) "
    "nếu có.\n"
    "- Trả lời trực tiếp, rõ ràng, súc tích; KHÔNG nhắc tới cơ chế kỹ thuật nội bộ "
    "(tool, vector, OpenSearch, chunk...). KHÔNG mở đầu kiểu 'Dựa trên tài liệu...'.\n"
    "- Với lời chào / trò chuyện chung, trả lời tự nhiên, không cần gọi tool."
)


@functools.lru_cache(maxsize=1)
def create_root_agent() -> Agent:
    """Tạo (và cache) agent gốc có tool RAG. Model đọc từ env tại lần tạo đầu."""
    chat_config = ChatConfig.from_env()
    return Agent(
        name=ROOT_AGENT_NAME,
        model=chat_config.chat_model,
        instruction=AGENT_INSTRUCTION,
        tools=[search_knowledge_base],
    )
