from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Code nghiệp vụ (http/controllers...) nằm trong sub-package `app/`, nên `name`
    # trỏ vào đó cho đồng nhất với các module khác.
    name = "modules.core.app"
    # Giữ app_label = "core" (mặc định sẽ thành "app" do name kết thúc bằng `.app`).
    label = "core"
