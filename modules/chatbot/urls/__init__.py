"""URL routes của module Chatbot — tách 2 nhóm, mỗi nhóm 1 file.

- `public.py`   — công khai, nối vào prefix `api/chatbot/` (chat / conversations).
- `internal.py` — service-to-service, nối vào prefix `api/internal/chatbot/`.

config/urls.py include() trực tiếp từng submodule (`modules.chatbot.urls.public`
/ `.internal`), nên không cần re-export gì ở đây.
"""
