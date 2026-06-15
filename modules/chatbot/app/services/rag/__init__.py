"""Thành phần RAG dùng chung của module Chatbot (Phase 1).

Các bước tái sử dụng cho cả ingest lẫn retrieve: embed, query rewrite + rerank,
và các config thuần tham số. Phần liên quan hạ tầng nằm chỗ khác: class thao tác
OpenSearch ở `chatbot/opensearch/`, orchestrator ingest + extractor (Gemini) +
chunker theo trang + LightRAG indexer + config riêng của ingest ở
`modules.chatbot.app.pipelines` (chạy trong worker).
"""
