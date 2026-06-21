"""Cấu hình tầng chat (generation) — đọc từ biến môi trường (12-factor).

Tách riêng khỏi `rag/config.py` (lo ingest/retrieve). Tái dùng `_env*` helper của
RAG để khỏi trùng logic parse env; Gemini/OpenSearch do client ở
`modules.base.clients` tự quản config.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..rag.config import _env, _env_bool, _env_int


def _env_float(name: str, default: float) -> float:
    """Parse env dạng float; lỗi/không set → default."""
    raw = _env(name)
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class ChatConfig:
    """Tham số sinh câu trả lời + trí nhớ hội thoại cho chatbot."""

    # --- Sinh câu trả lời (Gemini) ---
    chat_model: str          # model sinh câu trả lời (stream).
    max_output_tokens: int   # trần token cho 1 câu trả lời (0 = không giới hạn).
    context_top_k: int       # số chunk RAG đưa vào context prompt.
    history_size: int        # số tin nhắn gần nhất (cả user+assistant) làm lịch sử.

    # --- Tự sinh tiêu đề hội thoại (Celery, nền) ---
    title_enabled: bool
    title_model: str

    # --- Long-term memory (LTM) trên OpenSearch ---
    ltm_enabled: bool
    ltm_index: str           # index lưu lịch sử hội thoại (vector).
    ltm_top_k: int           # số lượt hội thoại cũ truy hồi làm ngữ cảnh.
    ltm_min_score: float     # ngưỡng điểm tối thiểu để giữ 1 kết quả LTM.

    # --- Provider LLM cho agent (gemini|ollama) ---
    llm_provider: str        # 'gemini' (mặc định) | 'ollama'
    ollama_api_base: str     # vd http://ollama:11434
    ollama_chat_model: str   # vd qwen2.5 / llama3.1

    # --- File người dùng đính kèm trong chat (đẩy lên Gemini Files API) ---
    attached_files_enabled: bool   # bật/tắt tính năng đính kèm file trong chat.
    attached_files_max: int        # trần số file đính kèm mỗi lượt (chống lạm dụng).
    gemini_file_ttl_hours: int     # TTL Files API (~48h) — quá hạn thì re-push.

    @classmethod
    def from_env(cls) -> ChatConfig:
        return cls(
            chat_model=_env("GEMINI_CHAT_MODEL", default="gemini-2.5-flash"),
            max_output_tokens=_env_int("CHAT_MAX_OUTPUT_TOKENS", default=0),
            context_top_k=_env_int("CHAT_CONTEXT_TOP_K", default=5),
            history_size=_env_int("CHAT_HISTORY_SIZE", default=10),
            title_enabled=_env_bool("CHAT_TITLE_ENABLED", default=True),
            title_model=_env("GEMINI_TITLE_MODEL", default="gemini-2.5-flash"),
            ltm_enabled=_env_bool("CHAT_LTM_ENABLED", default=True),
            ltm_index=_env("OPENSEARCH_CHAT_HISTORY_INDEX", default="chatbot-chat-history"),
            ltm_top_k=_env_int("CHAT_LTM_TOP_K", default=3),
            ltm_min_score=_env_float("CHAT_LTM_MIN_SCORE", default=0.5),
            llm_provider=_env("LLM_PROVIDER", default="gemini").lower(),
            ollama_api_base=_env("OLLAMA_API_BASE", default="http://ollama:11434"),
            ollama_chat_model=_env("OLLAMA_CHAT_MODEL", default="qwen2.5"),
            attached_files_enabled=_env_bool("CHAT_ATTACHED_FILES_ENABLED", default=True),
            attached_files_max=_env_int("CHAT_ATTACHED_FILES_MAX", default=5),
            gemini_file_ttl_hours=_env_int("GEMINI_FILE_TTL_HOURS", default=48),
        )
