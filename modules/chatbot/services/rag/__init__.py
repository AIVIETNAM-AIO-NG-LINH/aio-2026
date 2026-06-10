"""Pipeline RAG của module Chatbot (Phase 1).

Gói các bước S3 → extract (Gemini) → chunk → embed → index (OpenSearch). Không
import sẵn `pipeline` ở đây để tránh kéo Django model vào lúc autodiscover task —
caller (task) import trực tiếp `modules.chatbot.services.rag.pipeline`.
"""
