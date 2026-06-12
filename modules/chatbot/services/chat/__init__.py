"""Tầng sinh câu trả lời (generation) cho chatbot — ghép RAG + Gemini.

Khác `services/rag/` (lo INGEST + RETRIEVE chunk), package này lo bước CUỐI của
luồng chat: dựng prompt từ chunk đã truy hồi + lịch sử + LTM, gọi Gemini stream
ra câu trả lời. (LTM `ChatHistoryIndex` nằm ở `services/opensearch/ltm.py` cùng
các client OpenSearch khác.)
"""
