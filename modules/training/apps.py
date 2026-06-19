from django.apps import AppConfig


class TrainingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Code nghiệp vụ (models, tasks, services, http...) nằm trong sub-package `app/`,
    # nên `name` trỏ vào đó để Django/Celery auto-discover `models` & `tasks`.
    name = "modules.training.app"
    # app_label = "training" — migrations/content-types/bảng dùng nhãn ngắn này.
    label = "training"
