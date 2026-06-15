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

# Chỉ dẫn hệ thống — RAG grounded, có trích nguồn. Prompt viết TIẾNG ANH (model
# bám instruction tốt hơn); câu trả lời vẫn theo ngôn ngữ của câu hỏi người dùng.
AGENT_INSTRUCTION = (
    "You are the AI assistant of the AIO system. You answer questions based on the "
    "internal document knowledge base.\n\n"
    "## Tools\n"
    "- `search_knowledge_base`: finds document passages relevant to the question. "
    "CALL this tool for every question that may need information from the documents "
    "(policies, processes, products, reports, ...). You may call it multiple times "
    "with different queries if the first results are not sufficient.\n\n"
    "## Answering rules (STRICT)\n"
    "- LANGUAGE: ALWAYS answer in the language of the user's LATEST message — "
    "regardless of the language of the documents, tool results, long-term memory "
    "or earlier turns. If the user switches language mid-conversation, switch "
    "with them.\n"
    "- Rely ONLY on tool results and the conversation history; NEVER fabricate "
    "information that is not in the documents. If the tool returns nothing relevant, "
    "say clearly that the information was not found in the documents — do not guess.\n"
    "- When you use information from a passage, cite it as (Source: <document name>, "
    "page <number>) when available, with the label in the same language as your "
    "answer (e.g. 'Nguồn' in Vietnamese).\n"
    "- Answer directly, clearly and concisely; do NOT mention internal technical "
    "mechanisms (tools, vectors, OpenSearch, chunks, ...). Do NOT open with phrases "
    "like 'Based on the documents...'.\n"
    "- For greetings / casual small talk, reply naturally without calling any tool."
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
