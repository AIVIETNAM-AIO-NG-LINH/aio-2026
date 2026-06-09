# AI AIO — Django REST API

API backend dùng **Django 5.2 (LTS)** + **Django REST Framework**, chạy trong **Docker** với database **MariaDB**. Production phục vụ bằng **Gunicorn** + **WhiteNoise** (static files).

## Stack

| Thành phần | Lựa chọn |
|------------|----------|
| Web framework | Django 5.2 LTS |
| API | Django REST Framework |
| Database | MariaDB 11.4 |
| Driver | mysqlclient |
| WSGI server (prod) | Gunicorn |
| Static files (prod) | WhiteNoise |
| Config | django-environ (biến môi trường) |
| Runtime | Python 3.13 (trong Docker) |

## Cấu trúc thư mục

```
ai-aio/
├── config/                 # Django project (settings, urls, wsgi, asgi)
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py / asgi.py
├── core/                   # App ví dụ — chứa health check endpoint
│   ├── views.py            # GET /api/health/
│   └── urls.py
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
| — | `/admin/` | Django admin |

## Lệnh thường dùng

```bash
# Xem log
docker compose logs -f web

# Tạo superuser cho /admin/
docker compose exec web python manage.py createsuperuser

# Tạo & chạy migrations sau khi thêm model
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate

# Django shell
docker compose exec web python manage.py shell

# Dừng (giữ data) / dừng và xoá data
docker compose down
docker compose down -v
```

## Thêm một API mới

1. Tạo app: `docker compose exec web python manage.py startapp <ten_app>`
2. Thêm app vào `INSTALLED_APPS` trong [config/settings.py](config/settings.py)
3. Viết model → `makemigrations` + `migrate`
4. Viết serializer + view (DRF), khai báo route trong `urls.py` của app
5. `include(...)` app vào [config/urls.py](config/urls.py)

App [core/](core/) là ví dụ tối giản (chỉ có health endpoint) — copy theo mẫu đó.

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
