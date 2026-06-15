"""Primitive của luồng chat (chat pipeline) — các "mảnh ghép" cho bước sinh câu trả lời.

Package này ngang hàng `adk/` và `rag/` (KHÔNG nằm trong `services/`): nó gom các
khối nền dùng chung cho luồng chat — `config` (ChatConfig), `prompt` (dựng prompt),
`history` (nạp lịch sử), `citations` (chuẩn hoá nguồn), `sse` (contract event đẩy
FE), `generator` (gọi Gemini sinh text). `services/v1/chat_service.py` (orchestrator)
cùng `adk/`, `opensearch/`, `tasks/` ghép các mảnh này lại.

Khác `rag/` (lo INGEST + RETRIEVE chunk), đây là bước CUỐI: dựng prompt từ chunk đã
truy hồi + lịch sử + LTM rồi stream câu trả lời. (LTM `ChatHistoryIndex` nằm ở
`chatbot/opensearch/ltm.py` cùng các client OpenSearch khác.)
"""
