"""Thành phần RAG dùng chung của module Chatbot (Phase 1).

Các bước tái sử dụng cho cả ingest lẫn retrieve: extract (Gemini) → chunk →
embed, query rewrite + rerank, và các config thuần tham số. Phần liên quan hạ
tầng nằm chỗ khác: class thao tác OpenSearch ở `services/opensearch/`,
orchestrator ingest ở `modules.chatbot.pipelines.ingest` (chạy trong worker).
"""
