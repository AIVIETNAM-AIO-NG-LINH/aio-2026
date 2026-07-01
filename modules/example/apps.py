from django.apps import AppConfig


class ExampleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Code nghiệp vụ (models, http, services, catalogs...) nằm trong sub-package
    # `app/`, nên `name` trỏ vào đó để Django auto-discover `models`.
    name = "modules.example.app"
    # Giữ app_label = "example" (mặc định sẽ thành "app" do name kết thúc bằng
    # `.app`) để bảng `example` + migration 0001 tham chiếu không đổi.
    label = "example"
