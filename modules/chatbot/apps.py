from django.apps import AppConfig


class ChatbotConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Code nghiệp vụ (models, tasks, services, http...) nằm trong sub-package `app/`,
    # nên `name` trỏ vào đó để Django/Celery auto-discover `models` & `tasks`.
    name = "modules.chatbot.app"
    # Giữ app_label = "chatbot" để migrations/content-types/bảng cũ không đổi.
    label = "chatbot"
