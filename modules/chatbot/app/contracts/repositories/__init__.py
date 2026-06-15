"""Interface cho repository layer của Chatbot — re-export để import gọn."""

from .chat_conversation_repository import ChatConversationRepositoryInterface
from .chat_message_repository import ChatMessageRepositoryInterface
from .chatbot_document_repository import ChatbotDocumentRepositoryInterface

__all__ = [
    "ChatConversationRepositoryInterface",
    "ChatMessageRepositoryInterface",
    "ChatbotDocumentRepositoryInterface",
]
