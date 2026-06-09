from django.apps import AppConfig


class ChatbotConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Dotted path tới package của module (vì app nằm trong modules/).
    name = "modules.chatbot"
