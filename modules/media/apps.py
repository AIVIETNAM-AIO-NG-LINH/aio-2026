from django.apps import AppConfig


class MediaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Dotted path tới package của module (vì app nằm trong modules/).
    name = "modules.media"
