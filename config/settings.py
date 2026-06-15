"""
Django settings for the ai-aio project.

Configuration is driven by environment variables (12-factor style) so the same
image runs in dev and production with different `.env` values. See `.env.example`.
"""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Environment -----------------------------------------------------------
env = environ.Env(
    DJANGO_DEBUG=(bool, False),
)
# Load a local .env when present (running outside Docker). Inside Docker the
# variables are injected by docker-compose, so a missing file is harmless.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-change-me-in-production")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# --- Applications ----------------------------------------------------------
# Only the apps a JSON API needs — no admin or other HTML interface.
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    # Third-party
    "rest_framework",
    # Local modules (mỗi tính năng là 1 app trong modules/)
    "modules.base",
    "modules.core",
    "modules.example",
    "modules.media",
    "modules.chatbot.apps.ChatbotConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "modules.base.middleware.VerifyInternalToken",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database (MariaDB / MySQL backend) ------------------------------------
DATABASES = {
    "default": {
        "ENGINE": env("DB_ENGINE", default="django.db.backends.mysql"),
        "NAME": env("DB_NAME", default="ai_aio"),
        "USER": env("DB_USER", default="ai_aio"),
        "PASSWORD": env("DB_PASSWORD", default=""),
        "HOST": env("DB_HOST", default="db"),
        "PORT": env("DB_PORT", default="3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
        },
        "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=60),
    }
}

# --- Password validation ---------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internationalization --------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Chatbot giữ migrations trong package `database/` (kiểu Laravel) thay vì
# `<app>/migrations/` mặc định của Django — khai báo lại vị trí cho app `chatbot`.
MIGRATION_MODULES = {
    "chatbot": "modules.chatbot.database.migrations",
}

# --- Django REST Framework -------------------------------------------------
REST_FRAMEWORK = {
    # JSON only — the HTML Browsable API is intentionally disabled.
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    # Datetime trong JSON ra `Y-m-d H:i:s` (UTC+0) — tương đương
    # ModelV2::serializeDate() bên Laravel, thay cho ISO-8601 mặc định của DRF.
    # UTC nhờ TIME_ZONE="UTC" + USE_TZ=True ở trên (không setTimezone từng request).
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",
    # Nhận input cả ISO-8601 lẫn `Y-m-d H:i:s` để round-trip an toàn.
    "DATETIME_INPUT_FORMATS": ["iso-8601", "%Y-%m-%d %H:%M:%S"],
    # Render ApiException / FailSuccessException của base module ra đúng shape FE
    # (đóng vai render() của exception bên Laravel); lỗi khác để DRF xử lý mặc định.
    "EXCEPTION_HANDLER": "modules.base.exceptions.api_exception_handler",
}

# --- Internal service-to-service (ai-aio ↔ api-aio qua nginx:8080) ----------
# Secret dùng chung; `INTERNAL_TOKEN` PHẢI khớp .env của api-aio. Không gắn user.
INTERNAL_TOKEN = env("INTERNAL_TOKEN", default="")
INTERNAL_GATEWAY_URL = env("INTERNAL_GATEWAY_URL", default="http://nginx-aio:8080")
INTERNAL_API_HOST = env("INTERNAL_API_HOST", default="api.localhost")

# --- Celery (worker nền cho pipeline ingest) -------------------------------
# Broker + result backend = redis dùng chung trong stack nginx-aio (trên aio-net).
# DB 0 cho broker, DB 1 cho result để tách không gian key. Đổi qua env nếu cần.
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://redis:6379/1")
# Serializer JSON (tránh pickle) + timezone đồng bộ với Django.
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# --- Security (only enforced when DEBUG is off) ----------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = env.bool("DJANGO_SESSION_COOKIE_SECURE", default=False)
    CSRF_COOKIE_SECURE = env.bool("DJANGO_CSRF_COOKIE_SECURE", default=False)
