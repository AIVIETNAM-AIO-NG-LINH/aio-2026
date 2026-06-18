"""Agent gốc của chatbot (ADK) — có tool RAG `search_knowledge_base` + KG `search_knowledge_graph`.

Agent là STATELESS (chỉ chứa config: model, instruction, tools) nên cache lại an
toàn để tái dùng giữa các request đồng thời. Model lấy từ env `GEMINI_CHAT_MODEL`.
"""

from __future__ import annotations

import functools

from google.adk.agents import Agent
from google.adk.planners import BuiltInPlanner
from google.genai import types

from ..chat_pipeline.config import ChatConfig
from .constants import ROOT_AGENT_NAME
from .tools import search_knowledge_base, search_knowledge_graph

# Chỉ dẫn hệ thống — RAG grounded, có trích nguồn. Prompt viết TIẾNG ANH (model
# bám instruction tốt hơn); câu trả lời vẫn theo ngôn ngữ của câu hỏi người dùng.
AGENT_INSTRUCTION = (
    "You are the AI assistant of the AIO system. You answer questions based on the "
    "internal document knowledge base.\n\n"
    "## Tools\n"
    "- `search_knowledge_base`: finds document passages relevant to the question. "
    "CALL this tool for every question that may need information from the documents "
    "(policies, processes, products, reports, ...). You may call it multiple times "
    "with different queries if the first results are not sufficient.\n"
    "- `search_knowledge_graph`: explores entities and the relationships between them "
    "in the knowledge graph. CALL this for questions about HOW things relate — "
    "connections, dependencies, causes, or multi-hop reasoning across documents "
    "(e.g. 'how does X affect Y', 'what links A to B'). For a simple single-fact "
    "lookup, prefer `search_knowledge_base`.\n\n"
    "## Answering rules (STRICT)\n"
    "- LANGUAGE: ALWAYS answer in the language of the user's LATEST message — "
    "regardless of the language of the documents, tool results, long-term memory "
    "or earlier turns. If the user switches language mid-conversation, switch "
    "with them.\n"
    "- GROUNDING (CRITICAL): answer ONLY from the tool results (the internal "
    "documents) and the conversation history. Your own world knowledge and any "
    "external/web information are STRICTLY FORBIDDEN as a source — even if you are "
    "certain of the answer (e.g. general facts, geography, history, public figures, "
    "current events). NEVER fabricate or fill gaps from outside the documents.\n"
    "- If the documents do not contain the answer (tool returns nothing relevant, or "
    "the question is outside their scope), DO NOT answer from outside knowledge. "
    "Reply that the information is not available in the system's documents — in the "
    "user's language (e.g. in Vietnamese: 'Xin lỗi, thông tin này không có trong tài "
    "liệu của hệ thống.'). Do not guess.\n"
    "- When you use information from a passage, cite it as (Source: <document name>, "
    "page <number>) when available, with the label in the same language as your "
    "answer (e.g. 'Nguồn' in Vietnamese).\n"
    "- Answer directly, clearly and concisely; do NOT mention internal technical "
    "mechanisms (tools, vectors, OpenSearch, chunks, ...). Do NOT open with phrases "
    "like 'Based on the documents...'.\n"
    "- For greetings / casual small talk, reply naturally without calling any tool."
)


# Bật suy luận (chain-of-thought) MẶC ĐỊNH: `include_thoughts=True` để Gemini phát
# các part `thought` ra stream → handler bóc thành chunk "thinking" → SSE event
# `thinking` cho FE (xem stream_handler.py + chat_pipeline/sse.py). `thinking_budget`
# để mặc định (dynamic: model tự cân) — chỉ model dòng 2.5+ mới hỗ trợ thoughts.
_THINKING_PLANNER = BuiltInPlanner(
    thinking_config=types.ThinkingConfig(include_thoughts=True)
)


def _build_model(cfg: ChatConfig):
    """provider=ollama → LiteLlm(ollama_chat/...); gemini → string model như cũ."""
    if cfg.llm_provider == "ollama":
        from google.adk.models.lite_llm import LiteLlm
        return LiteLlm(
            model=f"ollama_chat/{cfg.ollama_chat_model}",
            api_base=cfg.ollama_api_base,
        )
    return cfg.chat_model


@functools.lru_cache(maxsize=1)
def create_root_agent() -> Agent:
    """Tạo (và cache) agent gốc có tool RAG. Model + provider đọc từ env tại lần tạo đầu."""
    cfg = ChatConfig.from_env()
    # _THINKING_PLANNER (include_thoughts) là tính năng riêng Gemini 2.5+; đa số model
    # Ollama không hỗ trợ → tắt planner cho ollama để tránh lỗi/bỏ qua âm thầm.
    planner = None if cfg.llm_provider == "ollama" else _THINKING_PLANNER
    return Agent(
        name=ROOT_AGENT_NAME,
        model=_build_model(cfg),
        instruction=AGENT_INSTRUCTION,
        planner=planner,
        tools=[search_knowledge_base, search_knowledge_graph],
    )
