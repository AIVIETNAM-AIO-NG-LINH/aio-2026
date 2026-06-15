"""Pipeline chạy nền của module Chatbot — orchestrator cho Celery task.

Khác với `services/` (class nhận DTO từ request, trả `Response`), code ở đây
chạy trong worker, không gắn với HTTP request/response.

Không import sẵn submodule ở đây để tránh kéo Django model vào lúc
autodiscover task — caller (task) import trực tiếp
`modules.chatbot.app.pipelines.ingest`.
"""
