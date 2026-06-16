"""URL routes của module Chatbot — version hóa theo thư mục con (`v1/`).

- `v1/public.py`   — công khai, nối vào prefix `api/v1/chatbot/` (chat / conversations).
- `v1/internal.py` — service-to-service, nối vào prefix `api/internal/v1/chatbot/`.

config/urls.py include() trực tiếp từng submodule (`modules.chatbot.routes.v1.public`
/ `.internal`), nên không cần re-export gì ở đây.
"""
