"""Models của module Chatbot — mỗi model 1 file, gom lại import ở đây.

Django cần model importable từ `modules.chatbot.models`, nên mọi model mới thêm
vào package này phải được re-export tại đây.
"""

from .chatbot_document import ChatbotDocument

__all__ = ["ChatbotDocument"]
