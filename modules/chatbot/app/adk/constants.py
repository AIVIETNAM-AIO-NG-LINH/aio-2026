"""Hằng số dùng chung cho tầng ADK của chatbot."""

from __future__ import annotations

# Tên app ADK (gắn vào session). Cố định để session service phân vùng đúng.
APP_NAME = "ai_aio_chatbot"

# Tên agent gốc — cũng là `author` của event model trong session history.
ROOT_AGENT_NAME = "aio_chatbot"

# Tên tool RAG (khớp giữa agent, stream handler khi nhận function_response).
SEARCH_TOOL_NAME = "search_knowledge_base"

# Tên tool truy vấn knowledge graph (LightRAG). Tách khỏi SEARCH_TOOL_NAME vì shape
# kết quả khác (context string, không có metadata chunk) → không trích citations.
GRAPH_TOOL_NAME = "search_knowledge_graph"

# Tên tool vẽ sơ đồ tư duy. Là TRIGGER thuần (agent gọi khi user yêu cầu); việc sinh
# JSON sơ đồ chạy ở chat_service sau lượt trả lời. Khớp giữa agent ↔ stream_handler.
MINDMAP_TOOL_NAME = "create_mind_map"
