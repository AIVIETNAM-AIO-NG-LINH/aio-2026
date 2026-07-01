from django.apps import AppConfig


class MediaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Code nghiệp vụ (models, repositories, enums...) nằm trong sub-package `app/`,
    # nên `name` trỏ vào đó để Django auto-discover `models`.
    name = "modules.media.app"
    # Giữ app_label = "media" (mặc định sẽ thành "app" do name kết thúc bằng `.app`)
    # để bảng/content-types tham chiếu tới app này không đổi.
    label = "media"
