# AI AIO — Django REST API

API backend dùng **Django 5.2 (LTS)** + **Django REST Framework** (API JSON thuần — không có admin / giao diện HTML), chạy trong **Docker** với database **MariaDB**. Production phục vụ bằng **Gunicorn**.

## Stack

| Thành phần | Lựa chọn |
|------------|----------|
| Web framework | Django 5.2 LTS |
| API | Django REST Framework |
| Database | MariaDB 11.4 |
| Driver | mysqlclient |
| WSGI server (prod) | Gunicorn |
| Config | django-environ (biến môi trường) |
| Runtime | Python 3.13 (trong Docker) |

## Cấu trúc thư mục

```
ai-aio/
├── config/                 # Django project (settings, urls, wsgi, asgi)
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py / asgi.py
├── modules/                # Mỗi tính năng là 1 module (Django app)
│   ├── core/               # health check — GET /api/health/
│   │   ├── views.py
│   │   └── urls.py
│   └── example/            # MODULE MẪU (CRUD) — copy để tạo module mới
│       ├── models.py
│       ├── serializers.py
│       ├── views.py        # ExampleViewSet (CRUD đầy đủ)
│       ├── urls.py         # router DRF -> /api/examples/
│       └── migrations/
├── manage.py
├── requirements.txt
├── Dockerfile              # multi-stage build (Python 3.13)
├── entrypoint.sh           # chờ DB → migrate → chạy server
├── docker-compose.yml      # DEV: MariaDB + runserver (auto-reload)
├── docker-compose.prod.yml # PROD: MariaDB + Gunicorn
├── .env                    # biến môi trường (git-ignored)
└── .env.example            # mẫu để copy thành .env
```

## Chạy nhanh (Development)

Yêu cầu: **Docker** + **Docker Compose** (không cần cài Python ở máy).

```bash
# 1. (Tuỳ chọn) tạo .env từ mẫu — repo đã kèm sẵn .env dev chạy được ngay
cp .env.example .env

# 2. Build & chạy
docker compose up --build
```

Mở: <http://localhost:8000/api/health/> → trả về:

```json
{"status": "ok", "database": "up"}
```

Server dev tự reload khi bạn sửa code (thư mục được mount vào container). DB được giữ qua volume `mariadb_data`.

## Chạy production (Gunicorn)

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

Khác với dev: dùng Gunicorn (3 workers), `DJANGO_DEBUG=False`, không mount code, không expose cổng DB ra ngoài. Nhớ đổi `DJANGO_SECRET_KEY` và mật khẩu DB trong `.env` trước khi deploy thật.

## Endpoints

| Method | URL | Mô tả |
|--------|-----|-------|
| GET | `/api/health/` | Health check (app + kết nối DB) |
| GET · POST | `/api/examples/` | Module mẫu — list / create |
| GET · PUT · PATCH · DELETE | `/api/examples/{id}/` | Module mẫu — chi tiết / sửa / xoá |
| POST | `/api/internal/chatbot/documents/ingest` | Nội bộ — nhận `{document_id}`, enqueue ingest → `202` (gate bằng `X-Internal-Token`) |

## Lệnh thường dùng

```bash
# Xem log
docker compose logs -f web

# Tạo & chạy migrations sau khi thêm model
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate

# Django shell
docker compose exec web python manage.py shell

# Celery worker (chạy nền cho ingest) — service `worker` đã có trong compose,
# tự lên cùng `docker compose up`. Xem log riêng:
docker compose logs -f worker

# Dừng (giữ data) / dừng và xoá data
docker compose down
docker compose down -v
```

## Thêm một module mới

Cách nhanh nhất: **copy module mẫu** [modules/example/](modules/example/) rồi đổi tên.

1. Copy: `cp -r modules/example modules/<ten_module>`
2. Sửa `apps.py`: `name = "modules.<ten_module>"` (đổi luôn tên class config)
3. Đổi tên model / serializer / viewset trong `models.py`, `serializers.py`, `views.py`
4. Sửa `urls.py`: đổi prefix `router.register(r"<ten>", ...)`
5. Xoá file migration cũ trong `modules/<ten_module>/migrations/` (giữ lại `__init__.py`)
6. Đăng ký vào `INSTALLED_APPS` ([config/settings.py](config/settings.py)): thêm `"modules.<ten_module>"`
7. Nối route trong [config/urls.py](config/urls.py): `path("api/", include("modules.<ten_module>.urls"))`
8. Tạo migration: `docker compose exec web python manage.py makemigrations && ... migrate`

Tham khảo: [modules/core/](modules/core/) là module tối giản (chỉ health endpoint), [modules/example/](modules/example/) là module CRUD đầy đủ dùng làm template.

## Biến môi trường

Xem [.env.example](.env.example). Quan trọng:

| Biến | Ý nghĩa |
|------|---------|
| `DJANGO_SECRET_KEY` | Khoá bí mật Django (đổi khi deploy) |
| `DJANGO_DEBUG` | `True` cho dev, `False` cho prod |
| `DJANGO_ALLOWED_HOSTS` | Danh sách host hợp lệ (phân tách bằng dấu phẩy) |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Thông tin MariaDB |
| `DB_ROOT_PASSWORD` | Mật khẩu root MariaDB |
| `DB_HOST` / `DB_PORT` | Mặc định `db` / `3306` |
