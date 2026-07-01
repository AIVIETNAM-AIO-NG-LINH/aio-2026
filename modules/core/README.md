# Module `core` — Health check

Module hạ tầng tối giản của **ai-aio**: chỉ cung cấp đúng một endpoint `GET /api/health/` để báo trạng thái ứng dụng và kết nối database. Không có model, không có nghiệp vụ, không có bảng dữ liệu riêng.

Ngoài vai trò health-check, `core` còn là **module mẫu nhỏ nhất** minh hoạ layout kiểu Laravel áp dụng trong repo: toàn bộ code nằm trong sub-package [app/](app/), URL khai báo trong [routes/public.py](routes/public.py) thay cho `urls.py` mặc định, migrations đặt trong [database/migrations/](database/migrations/) (rỗng vì module không có model). So sánh với [../example/](../example/) (CRUD đầy đủ) và [../chatbot/](../chatbot/) (dùng đủ lớp base) để thấy lớp tăng dần của cấu trúc module.

## Cây thư mục

```
core/
├── apps.py                                   # AppConfig: name="modules.core.app", label="core"
├── app/                                      # toàn bộ code của module
│   └── http/
│       └── controllers/
│           ├── __init__.py                   # re-export HealthController cho routes import gọn
│           └── health_controller.py          # HealthController (APIView) — logic health-check
├── routes/
│   └── public.py                             # khai báo URL: path("health/", ...) — thay cho urls.py
└── database/
    └── migrations/                           # rỗng (chỉ có __init__.py) — module không có model/bảng
```

## Giải thích theo lớp

### [apps.py](apps.py) — AppConfig

`CoreConfig` đặt `name = "modules.core.app"` (trỏ vào sub-package `app/` chứa code, đồng nhất với các module khác) nhưng ghim `label = "core"`. Nếu để mặc định, Django sẽ suy ra `app_label` là `"app"` (vì `name` kết thúc bằng `.app`); việc khai `label = "core"` giữ định danh app ổn định và khớp với key `"core"` trong `MIGRATION_MODULES`. App được đăng ký qua `"modules.core.apps.CoreConfig"` trong `INSTALLED_APPS`.

### [app/http/controllers/health_controller.py](app/http/controllers/health_controller.py) — Controller

`HealthController` là một DRF `APIView` chỉ hiện thực method `get`. Nó là probe liveness/readiness:

- Gọi `connection.ensure_connection()` (Django `default` DB) trong `try/except`.
- Nếu kết nối DB thành công: trả về HTTP **200** với `{"status": "ok", "database": "up"}`.
- Nếu `ensure_connection()` ném exception (DB down): trả về HTTP **503** với `{"status": "degraded", "database": "down"}`.

Không truy vấn bảng nào, không cần xác thực — chỉ kiểm tra bản thân app còn phản hồi và mở được kết nối tới database dùng chung (`api_ai`).

### [app/http/controllers/\_\_init\_\_.py](app/http/controllers/__init__.py)

Chỉ re-export `HealthController` (`from .health_controller import HealthController`) để [routes/public.py](routes/public.py) import ngắn gọn. Core chỉ có endpoint hạ tầng, không version hoá như chatbot nên controller để phẳng thay vì gom theo thư mục `v1/`.

### [routes/public.py](routes/public.py) — Định tuyến

Khai báo `urlpatterns` với một dòng: `path("health/", HealthController.as_view(), name="health")`. File được nối vào [../../config/urls.py](../../config/urls.py) dưới prefix `api/`, nên đường dẫn đầy đủ là `GET /api/health/`. Đây là thứ thay cho `urls.py` mặc định của Django app trong layout kiểu Laravel.

### [database/migrations/](database/migrations/)

Thư mục migrations rỗng (chỉ có `__init__.py`). Module `core` không định nghĩa model nên không có migration nào. Vị trí này được khai lại trong `MIGRATION_MODULES` (`"core": "modules.core.database.migrations"`) theo quy ước chung của repo — đặt migrations trong `database/migrations/` thay vì `<app>/migrations/` mặc định.

## Endpoint

| Method | URL | Xác thực | Mô tả |
|--------|-----|----------|-------|
| GET | `/api/health/` | Không | Health check: kiểm tra app phản hồi + mở được kết nối DB |

**Shape JSON trả về (chính xác theo code):**

Khi DB kết nối được — HTTP `200`:

```json
{"status": "ok", "database": "up"}
```

Khi DB không kết nối được — HTTP `503`:

```json
{"status": "degraded", "database": "down"}
```

## Luồng chính

`GET /api/health/` → `HealthController.get()` → gọi `connection.ensure_connection()`:

1. Kết nối OK → payload `{"status": "ok", "database": "up"}`, status **200**.
2. Kết nối lỗi (exception) → payload `{"status": "degraded", "database": "down"}`, status **503**.

Không có tác vụ nền, không ghi dữ liệu, không phụ thuộc dịch vụ ngoài (Redis/OpenSearch/S3/Gemini) — chỉ chạm tới database `default`.

## Biến môi trường liên quan

Module không đọc biến môi trường riêng. Kết quả health-check phụ thuộc vào cấu hình database `default` (dùng chung với toàn hệ), khai trong [../../config/settings.py](../../config/settings.py):

| Biến | Vai trò với health-check |
|------|--------------------------|
| `DB_NAME` | Tên database (`api_ai`) mà `ensure_connection()` mở tới |
| `DB_USER` / `DB_PASSWORD` | Thông tin đăng nhập DB |
| `DB_HOST` / `DB_PORT` | Địa chỉ MariaDB (alias `db` trên `aio-net`) |

Nếu các giá trị này sai hoặc MariaDB chưa sẵn sàng, endpoint trả `503` / `database: down`.

## Ghi chú tích hợp

- **Đăng ký app:** `"modules.core.apps.CoreConfig"` trong `INSTALLED_APPS`; migrations trỏ về `modules.core.database.migrations` qua `MIGRATION_MODULES` — xem [../../config/settings.py](../../config/settings.py).
- **Định tuyến:** nối vào root urlconf bằng `path("api/", include("modules.core.routes.public"))` — xem [../../config/urls.py](../../config/urls.py). Đây là route công khai, không đứng sau gate xác thực nào (khác nhóm `/api/v1/chatbot/*` và `/api/internal/v1/*`).
- **Quan hệ với [../base/](../base/):** khác các module nghiệp vụ, `core` **không** dùng lớp nền của `base` (repository/service/transformer/middleware). Middleware toàn cục duy nhất `modules.base.app.middleware.VerifyInternalToken` chỉ chốt các prefix nội bộ nên không ảnh hưởng tới `/api/health/`.
- **Dùng làm probe:** endpoint hợp cho liveness/readiness của Docker/reverse-proxy. Qua nginx: <http://ai.localhost:8000/api/health/>. Mã trạng thái 200/503 phản ánh trực tiếp việc mở được kết nối MariaDB dùng chung.
- **Làm khuôn cho module mới:** cấu trúc `app/http/controllers` + `routes/public.py` + `database/migrations/` (rỗng) là bộ khung tối thiểu để dựng một Django app kiểu Laravel trong repo này. Cần thêm model/CRUD thì tham khảo [../example/](../example/).
