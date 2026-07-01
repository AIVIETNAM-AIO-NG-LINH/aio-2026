from django.apps import AppConfig


class BaseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Code nền (models, clients, middleware, supports...) nằm trong sub-package
    # `app/`, nên `name` trỏ vào đó để Django auto-discover `models`.
    name = "modules.base.app"
    # Giữ app_label = "base" (mặc định sẽ thành "app" do name kết thúc bằng `.app`).
    label = "base"
