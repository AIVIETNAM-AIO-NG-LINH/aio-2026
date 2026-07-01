# Module `base` — Lớp nền dùng chung

Module `base` là **lớp nền (foundation layer)** của toàn bộ hệ ai-aio, port theo phong cách **Laravel** sang **Django 5.2 + Django REST Framework**. Nó **KHÔNG có endpoint** (không route công khai), mà cung cấp các lớp cơ sở & tiện ích mà **mọi module khác kế thừa**: model soft-delete, repository, service, transformer (Fractal-style), form-request (validate + DTO), catalog i18n, middleware xác thực, client tới dịch vụ ngoài (S3/Gemini/OpenSearch/LightRAG/Ollama/Realtime/api-aio), singleton `CurrentUser`, exception nghiệp vụ + handler shape lỗi cho FE.

Triết lý: giữ nguyên **shape response/lỗi của hệ V1 (Laravel)** để front-end không phải đổi, đồng thời chuẩn hoá cách viết một tính năng: `Controller → FormRequest (DTO) → Service → Repository → Transformer → response`.

> Cấu hình đăng ký ở project (xem [../../config/settings.py](../../config/settings.py)):
> - `AppConfig`: [apps.py](apps.py) đặt `name = "modules.base.app"` (code nằm trong sub-package `app/`) nhưng giữ `label = "base"`.
> - `MIGRATION_MODULES["base"] = "modules.base.database.migrations"` (khai lại vị trí migrations kiểu Laravel).
> - `MIDDLEWARE` global chỉ thêm **duy nhất** `modules.base.app.middleware.VerifyInternalToken` (ngoài các middleware mặc định của Django).
> - `REST_FRAMEWORK["EXCEPTION_HANDLER"] = "modules.base.app.exceptions.api_exception_handler"` — nối handler của base để render lỗi đúng shape FE.

## Cây thư mục `app/`

```
modules/base/
├── apps.py                       # AppConfig: name=modules.base.app, label=base
├── database/migrations/          # migrations của app base (khai qua MIGRATION_MODULES)
└── app/
    ├── models/                   # mô hình base + soft-delete (kiểu Laravel Eloquent)
    │   ├── base_model.py         # BaseModel (≈ ModelV2): id, created_at/updated_at, ordering
    │   ├── soft_delete_model.py  # SoftDeleteModel (≈ BaseModelV2): deleted_at + delete/restore
    │   ├── not_soft_delete_model.py # NotSoftDeleteModel (≈ BaseModelNotSoftDeletesV2)
    │   ├── managers.py           # BaseManager / SoftDeleteManager (lọc trashed)
    │   ├── querysets.py          # BaseQuerySet / SoftDeleteQuerySet (scope tái sử dụng)
    │   └── helpers.py            # fmt_dt (format datetime V1), has_value
    ├── repositories/
    │   └── base_repository.py    # BaseRepository[TModel]: query/find/create/update/delete
    ├── services/
    │   └── base_service.py       # BaseService: response_success/exception/not_found...
    ├── transformers/             # Fractal-style: model → dict cho FE
    │   ├── transformer_abstract.py  # TransformerAbstract + Item/Collection/Null resource
    │   └── transformer_service.py   # TransformerService: item/collection/paginator
    ├── requests/
    │   └── base_form_request.py  # BaseFormRequest / FormRequestMixin (validate → 422 shape V1)
    ├── catalogs/                 # khoá i18n cho translate()
    │   ├── lang_catalog.py       # LangCatalog (base catalog)
    │   └── common_catalog.py     # CommonCatalog (chuỗi dùng chung: FORBIDDEN, INVALID_DATA...)
    ├── middleware/               # gate xác thực (global + per-route)
    │   ├── verify_internal_token.py # VerifyInternalToken (chốt /api/internal/, sai → 403)
    │   ├── ensure_authenticated.py  # EnsureAuthenticated + decorator ensure_authenticated (401)
    │   └── authenticate_optional.py # AuthenticateOptional (không 401, populate nếu có)
    ├── clients/                  # client tới dịch vụ ngoài / nội bộ
    │   ├── gemini_client.py      # GeminiClient (Google GenAI: text/JSON/embed/upload)
    │   ├── s3_client.py          # S3Client (object storage: read_bytes/public_url)
    │   ├── opensearch_client.py  # BaseOpenSearchClient (vector store base class)
    │   ├── lightrag_client.py    # BaseLightRagClient (knowledge graph base class)
    │   ├── ollama_client.py      # OllamaClient (embedding local, cùng interface embed())
    │   ├── realtime_client.py    # RealtimeClient (publish Redis → node-aio → WebSocket)
    │   └── internal.py           # call_api (HTTP nội bộ tới api-aio qua nginx:8080)
    ├── singletons/
    │   └── current_user.py       # CurrentUser (id user của request hiện tại, contextvar)
    ├── supports/                 # helper cấp hàm
    │   ├── translate_helper.py   # translate / translate_lazy (i18n; hiện là stub)
    │   └── pagination_helper.py  # parse_pagination (page/limit từ query params)
    ├── exceptions/               # exception nghiệp vụ + render
    │   ├── exceptions.py         # ApiException / FailSuccessException / RequestValidationException
    │   └── handler.py            # api_exception_handler (nối REST_FRAMEWORK.EXCEPTION_HANDLER)
    └── constants/                # RES_SUCCESS = 1, RES_FAILED = 0 (cờ `success` body)
```

> Mỗi package đều export gọn qua `__init__.py`, ví dụ `from modules.base.app.models import SoftDeleteModel`, `from modules.base.app.services import BaseService`, `from modules.base.app.supports import translate`.

## Giải thích theo lớp

### 1. Models — [app/models/](app/models/)

Phân cấp model tương đương 3 lớp Eloquent bên Laravel (`ModelV2` / `BaseModelV2` / `BaseModelNotSoftDeletesV2`). Quy ước: **model nghiệp vụ kế thừa một trong hai lớp con** (`SoftDeleteModel` hoặc `NotSoftDeleteModel`), KHÔNG kế thừa thẳng `BaseModel`.

| Lớp | File | Vai trò |
|-----|------|---------|
| `BaseModel` | [app/models/base_model.py](app/models/base_model.py) | Gốc abstract: khai `id` tường minh (BigAutoField), `created_at` (`auto_now_add`) / `updated_at` (`auto_now`), `Meta.ordering = ["-id"]`, manager `BaseManager`. Có `get_table_name()` và `fmt_dt` (format datetime ra shape V1). |
| `SoftDeleteModel` | [app/models/soft_delete_model.py](app/models/soft_delete_model.py) | Thêm cột `deleted_at` (index). `delete()` = **soft delete** (set `deleted_at`), `hard_delete()` = xoá vật lý, `restore()` = khôi phục, property `is_trashed`. Có 2 manager: `objects` (chỉ row còn sống) và `all_objects` (≈ `withTrashed`). |
| `NotSoftDeleteModel` | [app/models/not_soft_delete_model.py](app/models/not_soft_delete_model.py) | Alias rõ nghĩa của `BaseModel` cho model dạng pivot/catalog không cần `deleted_at`. |

Hỗ trợ:

- [app/models/managers.py](app/models/managers.py) — `BaseManager` (expose helper của `BaseQuerySet`); `SoftDeleteManager(with_trashed=False)` tự lọc `deleted_at__isnull=True` (≈ global scope `SoftDeletingScope`), `with_trashed=True` trả tất cả (dùng cho `all_objects`).
- [app/models/querysets.py](app/models/querysets.py) — scope tái sử dụng: `when(field, value)` (bỏ điều kiện khi value rỗng, list/tuple/set → `field__in`), `when_many(dict)`, `order_by_id_desc/asc`, `order_by_updated_desc`. `SoftDeleteQuerySet` thêm `delete()`/`restore()` hàng loạt, `alive()`, `trashed()`.
- [app/models/helpers.py](app/models/helpers.py) — `fmt_dt(value)` → `'Y-m-d H:i:s'` (mirror `ModelV2::serializeDate`, `None` giữ `None`); `has_value(value)` (None và collection/string rỗng → coi như "không có giá trị").

### 2. Repository — [app/repositories/base_repository.py](app/repositories/base_repository.py)

`BaseRepository[TModel]` là base generic theo model (port `BaseRepositoryV2`, gộp luôn vai trò contract vì Django không có DI container). Subclass khai `model` qua class attribute hoặc truyền vào `__init__`:

```python
class ArticleRepository(BaseRepository[Article]):
    model = Article
```

| Method | Vai trò |
|--------|---------|
| `query()` | QuerySet mới qua manager mặc định (với `SoftDeleteModel` đã loại row đã xoá). |
| `find(id)` | Trả instance theo pk, hoặc `None`. |
| `create(attributes)` | Tạo + save + `refresh_from_db()`. |
| `update_model(instance, attributes)` | Set field (chỉ khi có attr) + save + reload. |
| `delete_model(instance)` | Xoá (soft delete nếu model hỗ trợ), chuẩn hoá kết quả về `bool`. |
| `force_delete_model(instance)` | Xoá vật lý (gọi `hard_delete()` nếu có). |

### 3. Service — [app/services/base_service.py](app/services/base_service.py)

`BaseService` (abstract — chỉ dùng qua subclass) chuẩn hoá **envelope response/lỗi** giữ nguyên shape V1:

| Method | Kết quả |
|--------|---------|
| `response_success(data, status=200)` | `{ "data": { ..., "success": 1 } }` — tự thêm `success` nếu thiếu. |
| `response_success_json(data, status=200)` | Raw JSON, KHÔNG wrap (vd token grant, file metadata). |
| `exception(message, status_code)` | Raise `ApiException` với status tuỳ ý. |
| `not_permission(message)` | Sugar raise **403**. |
| `not_found(message)` | Sugar raise **404** (resource không tồn tại / không thuộc bạn). |
| `response_success_failed(message, success=0, data=None)` | Raise `FailSuccessException`: **HTTP 200** nhưng body `success: 0` cho fail nghiệp vụ (login sai, state không hợp lệ), không phải HTTP error. |

Các method `raise` được render qua `api_exception_handler` (mục 8) — mirror cơ chế `render()` của exception bên Laravel.

### 4. Transformers — [app/transformers/](app/transformers/)

Port `league/fractal` — tách "shape JSON trả cho FE" khỏi service/repository.

- [app/transformers/transformer_abstract.py](app/transformers/transformer_abstract.py) — `TransformerAbstract`: subclass override `transform(obj) -> dict`. Quan hệ lồng (includes) khai qua `default_includes` (luôn nest) và `available_includes` (nest khi caller yêu cầu); mỗi include `x` cần method `include_x(obj)` trả `self.item(...)` / `self.collection(...)` / `self.null()`. Include lồng sâu dùng dấu chấm (`"media.user"`).
- [app/transformers/transformer_service.py](app/transformers/transformer_service.py) — `TransformerService` (entry-point tĩnh, stateless):
  - `item(obj, transformer, includes)` → dict (unwrap).
  - `collection(items, transformer, ...)` → `{"data": [...]}` (+ `meta` nếu có).
  - `paginator(paginator, transformer, ...)` → `{"data": [...], "meta": {"pagination": {...}}}`.
  - `make_paginator(items, total, limit, current_page)` / `make_paginator_hollow(...)` — dựng `Paginator` từ `(total, items)` mà repository trả về (kể cả trang trắng).

### 5. Requests — [app/requests/base_form_request.py](app/requests/base_form_request.py)

Vai trò của Laravel `FormRequest` ở DRF là **Serializer**. Module này cung cấp:

- `FormRequestMixin` — override `is_valid(raise_exception=True)` để fail thì ném `RequestValidationException` (**422 shape V1**: `{ data: { status: 422, message, data: { field: first_error } } }`). Kèm helper `route_id()`, `is_creating()` / `is_updating()`, `enum_or_null(key, EnumCls)`, `decode_json_inputs(data, keys)` (decode field gửi dạng stringified JSON).
- `BaseFormRequest = FormRequestMixin + serializers.Serializer` (request thường, không gắn model). Request gắn model thì tự trộn `FormRequestMixin + serializers.ModelSerializer`.

Convention: khai báo field như `rules()`, cross-field validate override `validate()`, có DTO thì thêm `to_dto()` (Service chỉ nhận DTO). Message lỗi 422 mặc định (`invalid_data_message`) dùng `translate_lazy` để resolve ngôn ngữ **per-request** (không phải lúc import).

### 6. Catalogs — [app/catalogs/](app/catalogs/)

Khoá i18n (dạng hằng `NAMESPACE.NAME`) cho `translate("Text", MyCatalog.KEY)`:

- [app/catalogs/lang_catalog.py](app/catalogs/lang_catalog.py) — `LangCatalog`: base rỗng để các catalog kế thừa.
- [app/catalogs/common_catalog.py](app/catalogs/common_catalog.py) — `CommonCatalog` (namespace `COMMON`): chuỗi **dùng chung** không gắn entity cụ thể: `FORBIDDEN`, `INVALID_DATA`, `UNAUTHENTICATED`, `NAME_BLANK`, `NAME_MAX_255`, `NAME_REQUIRED`, `NAME_TAKEN`. Chuỗi gắn entity cụ thể để ở catalog của module sở hữu.

### 7. Middleware & singleton — [app/middleware/](app/middleware/), [app/singletons/current_user.py](app/singletons/current_user.py)

Cơ chế xác thực: **tin header do nginx `auth_request` inject** sau khi verify token. `X-Auth-User-Id` = user đã đăng nhập; `X-Internal-Token` = chứng minh service-to-service.

| Thành phần | File | Vai trò | Đăng ký |
|------------|------|---------|---------|
| `VerifyInternalToken` | [app/middleware/verify_internal_token.py](app/middleware/verify_internal_token.py) | Chốt mọi path dưới `/api/internal/`: `X-Internal-Token` phải khớp `settings.INTERNAL_TOKEN` (so sánh constant-time), sai/thiếu → **403**. KHÔNG gắn user. | **Global** (`MIDDLEWARE`) |
| `EnsureAuthenticated` / `ensure_authenticated` | [app/middleware/ensure_authenticated.py](app/middleware/ensure_authenticated.py) | Đọc `X-Auth-User-Id`, thiếu/≤0 → **401**; hợp lệ → populate `CurrentUser`. Viết dạng `MiddlewareMixin` nên vừa gắn global được, vừa dùng làm **decorator per-route** (kiểu route-middleware Laravel). | **Per-route** (decorator) |
| `AuthenticateOptional` | [app/middleware/authenticate_optional.py](app/middleware/authenticate_optional.py) | Như trên nhưng **KHÔNG 401** khi thiếu header — có user thì populate `CurrentUser`, không thì đi tiếp như guest (`get_id()` = 0). | Tuỳ dùng |

`CurrentUser` — [app/singletons/current_user.py](app/singletons/current_user.py): holder id user của request hiện tại, dùng `contextvars.ContextVar` (state per-request, đúng ngữ nghĩa singleton-per-request dù được khởi tạo nhiều lần). Chỉ giữ `id` (không giữ cả model User). API: `set(user_id)`, `get_id()` (guest → 0), `reset()`.

> Lưu ý: gate `ensure_authenticated` áp **per-route** (như `Route::middleware('auth')`), **không** đăng ký global — chỉ `VerifyInternalToken` là global.

### 8. Exceptions — [app/exceptions/](app/exceptions/)

Cặp exception nghiệp vụ + handler (đóng vai `render()` của Laravel, đăng ký ở `REST_FRAMEWORK["EXCEPTION_HANDLER"]`):

- [app/exceptions/exceptions.py](app/exceptions/exceptions.py):
  - `ApiException(message, status_code=400)` → render `{ "data": { "message": ... } }` + `status_code`.
  - `FailSuccessException(message, success=0, data={})` → **HTTP 200** + `{ "data": { "message", "success", "data" } }` (fail nghiệp vụ, không phải HTTP error).
  - `RequestValidationException(fields, message)` → **HTTP 422** shape V1 `{ "data": { "status": 422, "message", "data": { field: first_error } } }`.
- [app/exceptions/handler.py](app/exceptions/handler.py) — `api_exception_handler(exc, context)`: nhận diện 3 exception trên và dựng JSON đúng shape; các lỗi khác fallback về `drf_exception_handler` mặc định.

### 9. Clients — [app/clients/](app/clients/)

Client mỏng, **tự quản cấu hình qua env (12-factor)**; caller chỉ gọi method. Deps nặng (boto3, google-genai, opensearchpy, lightrag, redis) được **import lazy** để module vẫn import an toàn ở image slim (web/chat không cài deps RAG — chỉ worker mới cần).

| Client | File | Vai trò | Env chính |
|--------|------|---------|-----------|
| `GeminiClient` | [app/clients/gemini_client.py](app/clients/gemini_client.py) | Google GenAI: `generate_text` / `agenerate_text`, `generate_json` (structured output cho sơ đồ tư duy, trả kèm usage token), `upload_file` (Gemini Files API — chat đính kèm file), `embed` / `aembed`. Expose `embedding_model` / `extract_model` / `summary_model`. | `GEMINI_API_KEY`, `EMBEDDING_MODEL`, `GEMINI_EXTRACT_MODEL`, `GEMINI_SUMMARY_MODEL` |
| `S3Client` | [app/clients/s3_client.py](app/clients/s3_client.py) | Object storage (S3/MinIO): `read_bytes(file_name)` (tải object gốc để ingest), `public_url(file_name)` (dựng link khớp api-aio — chỉ ghép chuỗi, không cần boto3). | `AWS_S3_ENDPOINT/REGION/BUCKET/ACCESS_KEY/SECRET_KEY`, `AWS_S3_URL`, `AWS_S3_USE_PATH_STYLE`, `MEDIA_FOLDER` |
| `BaseOpenSearchClient` | [app/clients/opensearch_client.py](app/clients/opensearch_client.py) | **Base class** cho các class domain OpenSearch (indexer/retriever/summary/LTM): dựng connection, expose `self._client`, `index` / `summary_index` / `vector_dims`; có `_retry_transient` (backoff cho 429/5xx/connection), `_create_index_if_missing`, `_verify_vector_dims`. | `OPENSEARCH_URL/USER/PASSWORD/VERIFY_CERTS`, `OPENSEARCH_INDEX`, `OPENSEARCH_SUMMARY_INDEX`, `OPENSEARCH_VECTOR_DIMS` |
| `BaseLightRagClient` | [app/clients/lightrag_client.py](app/clients/lightrag_client.py) | **Base class** cho knowledge graph (LightRAG): kiểm tra `self.enabled`, dựng LightRAG (PostgreSQL cho KV/Vector/DocStatus, Neo4j cho graph; LLM = Gemini Flash, embedding = Gemini @768 chiều), chạy `self._run_with_rag(action)` bao trọn vòng đời init → action → finalize. | `LIGHTRAG_ENABLED`, `LIGHTRAG_WORKING_DIR`, `LIGHTRAG_PG_*`, `LIGHTRAG_NEO4J_*` |
| `OllamaClient` | [app/clients/ollama_client.py](app/clients/ollama_client.py) | Embedding local (thay Gemini khi `EMBEDDING_PROVIDER=ollama`): `embed()` cùng interface với `GeminiClient` (embedding đối xứng, bỏ qua `task_type`), trả vector thô. | `OLLAMA_API_BASE`, `OLLAMA_EMBEDDING_MODEL` |
| `RealtimeClient` + `realtime_client()` | [app/clients/realtime_client.py](app/clients/realtime_client.py) | Publish event `{type, data}` xuống Redis cho **node-aio** đẩy ra WebSocket: `broadcast(type, data)` (mọi user), `to_user(id, type, data)` (1 user). Lỗi Redis bị nuốt (log) — realtime là phụ trợ, không làm hỏng luồng nghiệp vụ. `realtime_client()` cache client dùng chung cả process. | `REALTIME_REDIS_URL` (fallback `CELERY_BROKER_URL`), `REALTIME_CHANNEL_PREFIX` |
| `call_api()` | [app/clients/internal.py](app/clients/internal.py) | Gọi HTTP nội bộ sang **api-aio** (Laravel) qua reverse-proxy nội bộ nginx:8080: định tuyến bằng Host header, xác thực bằng `X-Internal-Token`. | `INTERNAL_GATEWAY_URL`, `INTERNAL_API_HOST`, `INTERNAL_TOKEN` |

### 10. Supports & constants

- [app/supports/translate_helper.py](app/supports/translate_helper.py) — `translate(text, key, ...)` (gọi runtime) và `translate_lazy` (cho chuỗi class-attribute, resolve per-request). **Hiện là stub**: trả thẳng `text` (chưa có Language/TranslateCache); call-site cứ gọi như thật, sau này thay ruột hàm.
- [app/supports/pagination_helper.py](app/supports/pagination_helper.py) — `parse_pagination(request)` → `(page, limit)` từ query params (`page` default 1, `limit` default 20 tối đa 100).
- [app/constants/](app/constants/) — `RES_SUCCESS = 1`, `RES_FAILED = 0` (cờ `success` trong body response; sửa typo `RES_FAILD` của Laravel nhưng giữ giá trị).

## Endpoint

Module `base` **không expose endpoint nào**. Nó chỉ cung cấp lớp nền + gate xác thực cho các module khác. Danh sách endpoint toàn hệ xem [README chính của repo](../../README.md).

## Luồng điển hình một module dùng `base`

Một tính năng (Django app trong `modules/<name>/`) kết hợp các lớp base theo mạch **Controller → FormRequest (DTO) → Service → Repository/Model → Transformer/Serializer → response**. Ví dụ tối giản là module mẫu [../example/](../example/):

1. **Route** khai trong `routes/` (thay `urls.py` mặc định), gắn per-route `ensure_authenticated` nếu cần đăng nhập (xem [../../config/urls.py](../../config/urls.py)).
2. **Controller** ([../example/app/http/controllers/example_controller.py](../example/app/http/controllers/example_controller.py)) nhận request, dựng **FormRequest** rồi `is_valid(raise_exception=True)` — fail → 422 shape V1 tự động qua `api_exception_handler`.
3. **FormRequest** (kế thừa `BaseFormRequest` / `FormRequestMixin`) validate input và `to_dto()` gói thành DTO thuần.
4. **Service** (kế thừa `BaseService`) nhận **DTO** (không biết HTTP), gọi **Repository/Model** thao tác DB, và trả `Response` qua `response_success()` / `not_found()`... để giữ envelope V1. Xem [../example/app/services/example_service.py](../example/app/services/example_service.py).
5. **Transformer** (`TransformerAbstract` + `TransformerService`) hoặc serializer DRF shape dữ liệu ra dict/JSON cho FE (list dùng `paginator(...)`).
6. Trong service, cần user hiện tại thì đọc `CurrentUser().get_id()`; cần dịch chuỗi thì `translate("...", SomeCatalog.KEY)`; cần gọi dịch vụ ngoài thì dùng client tương ứng ở [app/clients/](app/clients/).

Module phức tạp hơn (`chatbot`) dùng đủ các lớp base: `BaseRepository`, `BaseService`, transformer, `BaseFormRequest` (DTO), `BaseOpenSearchClient` / `BaseLightRagClient` / `GeminiClient` / `S3Client` / `RealtimeClient` / `call_api`, `CurrentUser`, và `ensure_authenticated` per-route.

## Biến môi trường liên quan

Các nhóm env mà **client & middleware của base** đọc trực tiếp (chi tiết đầy đủ xem [../../.env.example](../../.env.example)):

| Nhóm | Biến | Dùng ở |
|------|------|--------|
| Internal (ai-aio ↔ api-aio) | `INTERNAL_TOKEN`, `INTERNAL_GATEWAY_URL`, `INTERNAL_API_HOST` | `VerifyInternalToken`, `call_api` |
| Object storage | `AWS_S3_ENDPOINT`, `AWS_S3_REGION`, `AWS_S3_BUCKET`, `AWS_S3_ACCESS_KEY`, `AWS_S3_SECRET_KEY`, `AWS_S3_URL`, `AWS_S3_USE_PATH_STYLE`, `MEDIA_FOLDER` | `S3Client` |
| Google GenAI (Gemini) | `GEMINI_API_KEY`, `EMBEDDING_MODEL`, `GEMINI_EXTRACT_MODEL`, `GEMINI_SUMMARY_MODEL` | `GeminiClient` |
| OpenSearch | `OPENSEARCH_URL`, `OPENSEARCH_USER`, `OPENSEARCH_PASSWORD`, `OPENSEARCH_VERIFY_CERTS`, `OPENSEARCH_INDEX`, `OPENSEARCH_SUMMARY_INDEX`, `OPENSEARCH_VECTOR_DIMS` | `BaseOpenSearchClient` |
| LightRAG (KG) | `LIGHTRAG_ENABLED`, `LIGHTRAG_WORKING_DIR`, `LIGHTRAG_PG_HOST/PORT/USER/PASSWORD/DATABASE`, `LIGHTRAG_NEO4J_URI/USERNAME/PASSWORD` | `BaseLightRagClient` |
| Ollama (local) | `OLLAMA_API_BASE`, `OLLAMA_EMBEDDING_MODEL` | `OllamaClient` |
| Realtime | `REALTIME_REDIS_URL` (fallback `CELERY_BROKER_URL`), `REALTIME_CHANNEL_PREFIX` | `RealtimeClient` |

## Ghi chú tích hợp

- **Là nền, không phải feature**: `base` không có route/model nghiệp vụ riêng — mọi module khác import từ `modules.base.app.*`. Không đặt logic gắn entity cụ thể vào đây (vd chuỗi/catalog gắn entity nên ở module sở hữu).
- **Giữ shape V1 cho FE**: envelope `{ data: {...} }`, cờ `success`, lỗi 422/403/404 và cơ chế `FailSuccessException` (HTTP 200 + `success: 0`) đều bám shape hệ Laravel V1 — đổi ở base là đổi toàn hệ, cần thận trọng.
- **An toàn image slim**: client import deps nặng lazy; nhờ đó service web/chat import base không kéo theo boto3/genai/opensearch/lightrag/redis — chỉ worker ingest mới nạp thật.
- **Xác thực phân tầng**: `VerifyInternalToken` (global) chốt `/api/internal/`; `ensure_authenticated` (per-route) chốt endpoint công khai cần đăng nhập; `CurrentUser` là nguồn "ai đang gọi" duy nhất (không tách admin/user, login là đủ).
- **i18n hiện là stub**: `translate()` trả thẳng `text`. Khi port phần dịch thật, chỉ cần thay ruột hàm trong [app/supports/translate_helper.py](app/supports/translate_helper.py) — call-site không đổi.
