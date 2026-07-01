# Module `example` — CRUD template để tạo module mới

Module **mẫu** của ai-aio: một Django app CRUD tối giản trên model `Example`, viết đúng theo kiến trúc phân lớp kiểu Laravel mà toàn hệ dùng chung (Request → DTO → Service → Response, kèm catalog i18n, form-request validate). Không phải tính năng nghiệp vụ thật — mục đích là **copy nó rồi đổi tên** để dựng nhanh một module mới, và làm ví dụ tham chiếu cho các lớp base tại [../base/](../base/).

So với module tối giản [../core/](../core/) (chỉ có 1 health endpoint), `example` minh hoạ đầy đủ vòng đời một tài nguyên: model + migration, serializer output, form-request validate + DTO, service nghiệp vụ, controller (ViewSet) và routing qua `DefaultRouter`.

## Cây thư mục

```
modules/example/
├── apps.py                         # AppConfig: name="modules.example.app", label="example"
├── app/                            # toàn bộ code nghiệp vụ (sub-package Django auto-discover)
│   ├── models/
│   │   ├── example.py              # model Example (name, description, is_active, timestamps)
│   │   └── __init__.py             # re-export Example (Django cần model importable từ app.models)
│   ├── serializers.py              # ExampleSerializer (ModelSerializer) — dùng cho output list/retrieve
│   ├── http/
│   │   ├── controllers/
│   │   │   └── example_controller.py   # ExampleController (ModelViewSet) — CRUD
│   │   └── requests/
│   │       └── example_request.py      # ExampleRequest (validate) + ExampleDTO
│   ├── services/
│   │   └── example_service.py      # ExampleService (nghiệp vụ store/update/destroy)
│   └── catalogs/
│       └── example_catalog.py      # ExampleCatalog — key chuỗi UI riêng của entity Example
├── routes/
│   └── public.py                   # DefaultRouter register "examples" → /api/examples/
└── database/
    └── migrations/
        └── 0001_initial.py         # tạo bảng example
```

Mỗi package (`models/`, `http/controllers/`, `http/requests/`, `services/`, `catalogs/`) có `__init__.py` re-export để import gọn, ví dụ `from modules.example.app.services import ExampleService`.

## Giải thích theo lớp

### AppConfig — [apps.py](apps.py)

Điểm khác biệt cốt lõi của layout kiểu Laravel: code nằm trong sub-package `app/`, nên `name = "modules.example.app"` để Django auto-discover được `models`. Vì `name` kết thúc bằng `.app`, `app_label` mặc định sẽ thành `"app"`, nên phải ép `label = "example"` để tên bảng và migration `0001_initial` tham chiếu đúng.

### Model — [app/models/example.py](app/models/example.py)

`Example` là `django.db.models.Model` thuần (không kế thừa base soft-delete) với các field: `name` (CharField 255), `description` (TextField, blank), `is_active` (BooleanField, mặc định `True`), `created_at` (`auto_now_add`), `updated_at` (`auto_now`); `Meta.ordering = ["-created_at"]`. Bảng do migration của chính module tạo (không phải `managed=False` như [../media/](../media/) hay `chatbot_documents`). Khi thêm model mới vào package, nhớ re-export trong [app/models/\_\_init\_\_.py](app/models/__init__.py).

### Serializer — [app/serializers.py](app/serializers.py)

`ExampleSerializer` là `ModelSerializer` chỉ dùng cho **output** (list/retrieve): expose `id, name, description, is_active, created_at, updated_at`; `read_only_fields = ["id", "created_at", "updated_at"]`. Việc **validate input** tách hẳn sang form-request bên dưới (đúng như Laravel tách `Resource` khỏi `FormRequest`).

### Request + DTO — [app/http/requests/example_request.py](app/http/requests/example_request.py)

`ExampleRequest` kế thừa `BaseFormRequest` (xem [../base/](../base/)) — đóng vai `FormRequest` của Laravel:

- Khai báo field như `rules()`; `error_messages` bọc `translate_lazy(...)` (resolve ngôn ngữ per-request lúc render lỗi, không phải lúc import).
- `validate_name()` — field-level: trim 2 đầu, chặn chuỗi toàn khoảng trắng.
- `validate()` — cross-field/DB: chặn `name` trùng; khi update loại chính bản ghi đang sửa qua `route_id()`. Phân nhánh create/update bằng `is_creating()` / `is_updating()` thừa hưởng từ `FormRequestMixin`.
- `to_dto()` — đọc `validated_data` → `ExampleDTO` (dataclass bất biến) để Service không phụ thuộc HTTP/request.

Khi `is_valid(raise_exception=True)` thất bại, mixin ném exception → handler trả **HTTP 422** theo shape V1. Chuỗi lỗi generic về field `name` lấy từ `CommonCatalog` của base; chuỗi gắn đích danh entity Example nằm ở catalog riêng.

### Service — [app/services/example_service.py](app/services/example_service.py)

`ExampleService` kế thừa `BaseService` ([../base/app/services/base_service.py](../base/app/services/base_service.py)), chỉ nhận **DTO** và trả `Response` qua helper để giữ đúng shape V1:

| Method | Hành vi |
|--------|---------|
| `store(dto)` | Tạo bản ghi → `response_success(...)` với `HTTP 201` |
| `update(id, dto)` | Không thấy → `not_found(...)` (404); có thì cập nhật (`save(update_fields=[...])`, gồm cả `updated_at`) → 200 |
| `destroy(id)` | Không thấy → `not_found(...)` (404); có thì `delete()` → 200 `{ "id": ... }` |

`response_success(data)` wrap thành `{"data": {..., "success": 1}}`; `not_found(message)` là sugar raise 404.

### Controller — [app/http/controllers/example_controller.py](app/http/controllers/example_controller.py)

`ExampleController` là `ModelViewSet`:

- `list` / `retrieve` (đọc): dùng thẳng `queryset = Example.objects.all()` + `serializer_class = ExampleSerializer` mặc định của ViewSet.
- `create` / `update` / `destroy` (ghi): override để đi qua `ExampleRequest` (validate) rồi `ExampleService` (nghiệp vụ) — tương tự inject `FormRequest` vào controller rồi gọi Service bên Laravel.

Lưu ý: `ExampleRequest` validate full payload (ngữ nghĩa PUT). `PATCH` (`partial_update`) cũng route qua `update` nên vẫn yêu cầu đủ field.

### Catalog — [app/catalogs/example_catalog.py](app/catalogs/example_catalog.py)

`ExampleCatalog(LangCatalog)` với namespace `_NS = "EXAMPLE"` giữ các key chuỗi UI đích danh entity (hiện có `NOT_FOUND = "EXAMPLE.NOT_FOUND"`). Chuỗi generic theo field (`NAME_REQUIRED`, `NAME_BLANK`, `NAME_MAX_255`, `NAME_TAKEN`...) dùng chung từ `CommonCatalog` của base.

### Route — [routes/public.py](routes/public.py)

Dùng `DefaultRouter().register(r"examples", ExampleController, basename="example")` và export `router.urls`. Được nối vào [../../config/urls.py](../../config/urls.py) dưới prefix `api/`, nên path đầy đủ là `/api/examples/`.

## Endpoints

`DefaultRouter` sinh đủ bộ CRUD:

| Method | URL | Action ViewSet | Kết quả |
|--------|-----|----------------|---------|
| GET | `/api/examples/` | `list` | Danh sách Example (sort `-created_at`) |
| POST | `/api/examples/` | `create` | Validate → tạo → `201` |
| GET | `/api/examples/{id}/` | `retrieve` | Chi tiết 1 Example |
| PUT | `/api/examples/{id}/` | `update` | Validate full → cập nhật |
| PATCH | `/api/examples/{id}/` | `partial_update` → `update` | Như PUT (vẫn cần đủ field) |
| DELETE | `/api/examples/{id}/` | `destroy` | Xoá → `200 { "id": ... }` |

Route này **công khai** ở prefix `api/` (không đi qua nhóm `/api/v1/chatbot/*` hay `/api/internal/v1/*`), nên không gắn gate xác thực nào — đúng tinh thần một module template để test nhanh. Nếu module thật cần chặn đăng nhập, áp per-route gate `ensure_authenticated` (kiểu route-middleware Laravel) như chatbot làm, thay vì global.

## Luồng ghi (create/update)

```
POST/PUT /api/examples/{id}?
  → ExampleController.create|update
      → ExampleRequest(data).is_valid(raise_exception=True)   # fail → 422 (shape V1)
      → ExampleRequest.to_dto() → ExampleDTO
      → ExampleService().store|update(dto)
          → Example.objects.create|save(...)
          → response_success(ExampleSerializer(obj).data)      # { data: { ..., success: 1 } }
```

Đọc (`list`/`retrieve`) đi thẳng qua serializer mặc định của ViewSet, không qua Service.

## Biến môi trường

Module này **không có biến môi trường riêng**. Nó chỉ dùng DB mặc định của dự án (`DB_*`) như mọi app khác; bảng `example` được tạo bởi migration của chính module qua `entrypoint.sh migrate`. Xem [../../.env.example](../../.env.example) cho cấu hình chung.

## Tích hợp với hệ & cách nhân bản thành module mới

Module đã được nối sẵn ở hai nơi:

- [../../config/settings.py](../../config/settings.py): `INSTALLED_APPS` chứa `"modules.example.apps.ExampleConfig"`; `MIGRATION_MODULES["example"] = "modules.example.database.migrations"` (khai lại vị trí migrations kiểu Laravel).
- [../../config/urls.py](../../config/urls.py): `path("api/", include("modules.example.routes.public"))`.

Để dựng module mới, copy `example` rồi đổi tên:

1. **Copy**: `cp -r modules/example modules/<ten_module>`.
2. **Đổi [apps.py](apps.py)**: `name = "modules.<ten_module>.app"`, đổi tên class config (vd `<Ten>Config`), và đặt `label = "<ten_module>"`.
3. **Đổi model** ([app/models/example.py](app/models/example.py) + re-export ở [app/models/\_\_init\_\_.py](app/models/__init__.py)) và **serializer** ([app/serializers.py](app/serializers.py)) theo tính năng thật.
4. **Đổi request/DTO** ([app/http/requests/example_request.py](app/http/requests/example_request.py)), **service** ([app/services/example_service.py](app/services/example_service.py)), **controller** ([app/http/controllers/example_controller.py](app/http/controllers/example_controller.py)) và **catalog** ([app/catalogs/example_catalog.py](app/catalogs/example_catalog.py)); cập nhật các `__init__.py` re-export tương ứng.
5. **Sửa route** ([routes/public.py](routes/public.py)): đổi prefix `router.register(r"<ten>", ...)` và `basename`.
6. **Xoá migration cũ** trong `modules/<ten_module>/database/migrations/` (giữ lại `__init__.py`).
7. **Đăng ký** vào `INSTALLED_APPS` ở [../../config/settings.py](../../config/settings.py) và thêm entry vào `MIGRATION_MODULES`.
8. **Nối route** trong [../../config/urls.py](../../config/urls.py): thêm `path("api/", include("modules.<ten_module>.routes.public"))`.
9. **Tạo & chạy migration**: `python manage.py makemigrations && python manage.py migrate` (trong container: `docker compose exec web ...`).

Các lớp nền (`BaseFormRequest`, `BaseService`, `LangCatalog`, `CommonCatalog`, translate helper) đều nằm ở module base — xem [../base/](../base/). Module phức tạp dùng đủ lớp base (repository/transformer/pipeline/task) tham khảo [../chatbot/](../chatbot/).
