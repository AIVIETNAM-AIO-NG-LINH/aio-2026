# ai-aio

**Repo backend AI của hệ AIO** — nơi chứa **các module thuộc khóa học AIO**, tập trung **chỉ vào phần AI**. Dịch vụ Django + Django REST Framework (JSON thuần, **không** trang admin/HTML); mỗi tính năng AI là **một module** (Django app) trong [modules/](modules/).

> ### 🎯 Phạm vi repo (chỉ AI)
>
> - ✅ **Chỉ chứa luồng liên quan đến AI**: chatbot RAG (trích dẫn, sơ đồ tư duy, reasoning, đính kèm file, trí nhớ dài hạn), pipeline ingest tài liệu (embedding → vector store → knowledge graph), truy hồi hybrid + rerank, LLM/embedding (Gemini/Ollama).
> - ❌ **Không chứa phần ngoài AI**: đăng nhập/xác thực người dùng thật, nghiệp vụ CRUD chung, quản lý user–quyền–thanh toán, upload/CRUD file gốc… — những phần này do các service khác trong hệ AIO đảm nhiệm (**chủ yếu là `api-aio`**). `ai-aio` chỉ **tiêu thụ** dữ liệu đó: đọc bảng dùng chung (`media`, `chatbot_documents`), nhận header `X-Auth-User-Id` đã verify sẵn từ nginx, hỏi hạn mức token qua api-aio.
> - 🎓 Đây là **repo khung cho các module trong khóa học AIO**: [base/](modules/base/README.md) là lớp nền dùng chung, [example/](modules/example/README.md) là khuôn để học viên tạo module mới, [chatbot/](modules/chatbot/README.md) là một module AI hoàn chỉnh làm mẫu tham chiếu.

`ai-aio` chạy **cạnh `api-aio`** trong stack `nginx-aio`: dùng chung MariaDB (DB `api_ai`), Redis (broker Celery) và mạng docker `aio-net`. Dịch vụ **không publish cổng ra host** — mọi truy cập đi qua reverse-proxy `nginx-aio` tại `http://ai.localhost:8000`.

Tài liệu này giới thiệu **cấu trúc tổng thể** và **cách chạy code**; nó chỉ mô tả **luồng AI** của hệ. Chi tiết sâu của từng tính năng nằm ở README riêng trong mỗi module (xem danh sách ngay dưới).

---

## 📚 Tài liệu chi tiết từng module

**chatbot** là module **tính năng AI** (trọng tâm của repo); **base / core / example / media** là **khung & hạ tầng dùng chung** để dựng module AI — không phải nghiệp vụ ngoài AI. Mọi module theo cùng layout Laravel. Bấm vào link để xem tài liệu chi tiết (kèm sơ đồ luồng ở module chatbot):

| Module | Tài liệu |
|---|---|
| 🧩 **base** — lớp nền dùng chung (middleware, base model/repo/service/transformer, clients, exceptions) | [modules/base/README.md](modules/base/README.md) |
| ❤️ **core** — health check + khung module tối thiểu | [modules/core/README.md](modules/core/README.md) |
| 📦 **example** — module mẫu CRUD (khuôn để tạo module mới) | [modules/example/README.md](modules/example/README.md) |
| 🗂️ **media** — model media read-only (bảng của api-aio) | [modules/media/README.md](modules/media/README.md) |
| 🤖 **chatbot** — module AI chính: RAG chat (SSE), ingest, KG, mind map, quota, realtime (có sơ đồ luồng) | [modules/chatbot/README.md](modules/chatbot/README.md) |
| 📊 **chatbot / eval** — đánh giá chất lượng RAG | [modules/chatbot/eval/README.md](modules/chatbot/eval/README.md) |

---

## Stack

| Thành phần | Lựa chọn |
|---|---|
| Ngôn ngữ / Runtime | Python 3.13 |
| Web framework | Django 5.2 LTS + Django REST Framework (JSON only) |
| WSGI server (prod) | Gunicorn (`gthread`, giữ SSE) |
| Cơ sở dữ liệu | MariaDB (DB `api_ai`, dùng chung với `api-aio`) |
| Worker nền | Celery 5.4 (broker/result = Redis) |
| Vector store | OpenSearch 2.19 (index parent-child, hybrid + rerank) |
| Chat agent | Google ADK (Agent + tool RAG + Runner streaming SSE) |
| LLM / Embedding | `gemini` (mặc định) hoặc `ollama` (local, qua LiteLLM) |
| Knowledge Graph | LightRAG (PostgreSQL/pgvector + Neo4j) — **bật mặc định** |
| Object storage | S3 (boto3) — tải file gốc cho pipeline RAG |
| Realtime | Redis → `node-aio` (WebSocket) |
| Đóng gói | Docker (multi-stage), Docker Compose |
| CI/CD | Jenkins (build & deploy local, image `aio/ai-aio:latest`) — xem [Jenkinsfile](Jenkinsfile) |

Danh sách phụ thuộc đầy đủ: [requirements.txt](requirements.txt).

---

## Kiến trúc & cấu trúc thư mục

### Layout kiểu Laravel (điểm khác biệt chính)

Mỗi tính năng là **một Django app** đặt trong `modules/<name>/`, tổ chức theo phong cách Laravel thay vì layout Django mặc định:

```
modules/<name>/
├── app/                  # toàn bộ code: http/(controllers, requests), services/,
│                         # repositories/, models/, enums/, transformers/, catalogs/, ...
├── routes/               # khai báo URL (public.py, v1/public.py, v1/internal.py) thay cho urls.py
├── database/migrations/  # migrations (vị trí khai lại qua MIGRATION_MODULES)
└── apps.py               # AppConfig
```

Ràng buộc trong [config/settings.py](config/settings.py):

- `INSTALLED_APPS` nạp 5 module qua `*.apps.*Config`: **base, core, example, media, chatbot**.
- `MIGRATION_MODULES` chuyển migrations của **mọi** app sang `modules.<app>.database.migrations`.
- `MIDDLEWARE` chỉ thêm **duy nhất** `modules.base.app.middleware.VerifyInternalToken` (ngoài default Django). Việc xác thực người dùng áp **per-route** kiểu route-middleware Laravel (`ensure_authenticated` / `authenticate_optional`), **không** global.

### Cây thư mục ở mức tổng

```
ai-aio/
├── config/               # dự án Django: settings.py, urls.py (định tuyến gốc), wsgi/asgi, celery
├── modules/              # các Django app (mỗi tính năng 1 module — tài liệu ở đầu README)
│   ├── base/             # nền tảng dùng chung (middleware, exceptions, DTO, auth helpers)
│   ├── core/             # tiện ích lõi + health check
│   ├── example/          # module mẫu (CRUD) — khuôn để tạo module mới
│   ├── media/            # metadata/tham chiếu media (file đính kèm)
│   └── chatbot/          # chatbot RAG, ingest tài liệu, mind map, knowledge graph
├── docker/               # Dockerfile + docker-compose*.yml + secrets.env(.example)
├── entrypoint.sh         # chờ DB → migrate → chạy CMD
├── manage.py
├── requirements.txt
└── Jenkinsfile
```

Định tuyến gốc — [config/urls.py](config/urls.py):

| Prefix | Include | Kết quả |
|---|---|---|
| `api/` | `modules.core.routes.public` | `GET /api/health/` |
| `api/` | `modules.example.routes.public` | `/api/examples/` CRUD (DefaultRouter) |
| `api/v1/chatbot/` | `modules.chatbot.routes.v1.public` | chat / conversations |
| `api/internal/v1/chatbot/` | `modules.chatbot.routes.v1.internal` | documents ingest / purge (nội bộ) |

---

## Yêu cầu trước khi chạy

- **Docker** + **Docker Compose**.
- Mạng docker `aio-net` đã tồn tại:
  ```bash
  docker network create aio-net
  ```
- **Development**: đã up `nginx-aio` **trước** (cung cấp MariaDB `db`, Redis `redis`, gateway `nginx-aio:8080`).
- **Production**: đã up `data-aio` **trước** (cung cấp `aio-net` + toàn bộ data store: db, redis, opensearch, postgres, neo4j).

> Mọi lệnh `docker compose` bên dưới chạy **từ thư mục gốc repo**.

---

## Chạy nhanh (Development)

Stack dev — [docker/docker-compose.yml](docker/docker-compose.yml) — gồm `web` (Django dev server, mount source live-reload), `worker` (Celery `--concurrency=2`) và `opensearch` (single-node, tắt security).

```bash
# 1. Config không bảo mật
cp .env.example .env

# 2. Secret (gitignored) — điền giá trị thật (DJANGO_SECRET_KEY, DB_PASSWORD,
#    INTERNAL_TOKEN, GEMINI_API_KEY, AWS_S3_*, LightRAG passwords, ...)
cp docker/secrets.env.example docker/secrets.env

# 3. Chạy (nginx-aio phải up trước, aio-net phải tồn tại)
docker compose -f docker/docker-compose.yml up --build
```

`entrypoint.sh` (service `web`) tự **chờ DB** rồi chạy `migrate --noinput` trước khi khởi động server; `worker` bỏ qua entrypoint và chạy thẳng Celery.

Kiểm tra dịch vụ sống (qua reverse-proxy):

```bash
curl http://ai.localhost:8000/api/health/
```

Secret bắt buộc: `DJANGO_SECRET_KEY`, `DB_PASSWORD`, `INTERNAL_TOKEN` (phải **giống** `api-aio`), `GEMINI_API_KEY` (RAG/chat). Tham chiếu đầy đủ: [docker/secrets.env.example](docker/secrets.env.example).

---

## Bật Knowledge Graph (LightRAG)

Knowledge Graph **bật trong cấu hình mẫu** — [.env.example](.env.example) đặt `LIGHTRAG_ENABLED=true`. Nếu bỏ biến này, code tự **fallback về tắt** (`BaseLightRagClient` đọc `LIGHTRAG_ENABLED` với `default=False`).

> Lưu ý: dòng comment "TẮT mặc định" trong `.env.example` mô tả mặc định của **code**, không khớp với giá trị mẫu `=true` ngay bên dưới.

Datastore của LightRAG (PostgreSQL/pgvector + Neo4j) **không** chạy cùng `docker compose up` thường:

- **Development** — thuộc profile `lightrag`, phải bật kèm:
  ```bash
  docker compose -f docker/docker-compose.yml --profile lightrag up -d
  ```
- **Production** — postgres/neo4j lấy từ `data-aio` (không khai trong compose của ai-aio); chỉ cần data-aio đã up.

Secret liên quan: `LIGHTRAG_PG_PASSWORD`, `LIGHTRAG_NEO4J_PASSWORD` (trong `docker/secrets.env`, phải khớp `data-aio`).

Để **tắt** KG: đặt `LIGHTRAG_ENABLED=false` trong `.env`. Pipeline KG là **fail-safe** — không chặn tài liệu chuyển sang `READY`.

---

## Chạy LLM local (Ollama) — tùy chọn

Mặc định LLM/embedding dùng Gemini. Để chạy local, dùng stack Ollama riêng — [docker/docker-compose.ollama.yml](docker/docker-compose.ollama.yml):

```bash
# 1. Up stack Ollama (cùng aio-net → web/worker gọi qua ollama:11434)
docker compose -f docker/docker-compose.ollama.yml up -d

# 2. Pull model (lần đầu, cache vào volume)
docker compose -f docker/docker-compose.ollama.yml exec ollama ollama pull qwen2.5
docker compose -f docker/docker-compose.ollama.yml exec ollama ollama pull nomic-embed-text
```

Rồi đặt trong `.env` và restart `web`/`worker`:

```dotenv
LLM_PROVIDER=ollama
EMBEDDING_PROVIDER=ollama
OLLAMA_API_BASE=http://ollama:11434
OLLAMA_CHAT_MODEL=qwen2.5
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

> Đổi `EMBEDDING_PROVIDER` **bắt buộc re-index OpenSearch** (không gian vector khác nhau — không trộn 2 provider trong cùng index). Ollama (LLM local) được **miễn** tính hạn mức token.

---

## Chạy production (Gunicorn)

Stack prod — [docker/docker-compose.prod.yml](docker/docker-compose.prod.yml) — gồm `web` (Gunicorn, `DJANGO_DEBUG=False`, image `aio/ai-aio:latest`, **không** mount source) và `worker`. Toàn bộ data store lấy **từ `data-aio`** (external), không khai ở đây.

```bash
# data-aio đã up trước (aio-net + db/redis/opensearch/postgres/neo4j)
docker compose -f docker/docker-compose.prod.yml up -d --build
```

Secret tách riêng ở `docker/secrets.env` (gitignored). Trong CI/CD Jenkins: config lấy từ `.env.example`, secret lấy từ credential kiểu "Secret file" (`env-ai-aio`). Xem [Jenkinsfile](Jenkinsfile).

---

## Endpoints

| Method | Path | Ghi chú |
|---|---|---|
| GET | `/api/health/` | Health check |
| GET · POST | `/api/examples/` | Danh sách / tạo (module mẫu) |
| GET · PUT · PATCH · DELETE | `/api/examples/{id}/` | Chi tiết / cập nhật / xoá |
| POST | `/api/v1/chatbot/chat` | Chat SSE (`ensure_authenticated`) |
| GET | `/api/v1/chatbot/conversations` | Danh sách hội thoại (phân trang, `?q`, `?max_id`) |
| PATCH | `/api/v1/chatbot/conversations/{id}` | Đổi tên hội thoại |
| DELETE | `/api/v1/chatbot/conversations/{id}` | Xoá mềm hội thoại |
| GET | `/api/v1/chatbot/conversations/{id}/messages` | Danh sách tin nhắn |
| POST | `/api/internal/v1/chatbot/documents/ingest` | Ingest tài liệu (nội bộ) |
| POST | `/api/internal/v1/chatbot/documents/purge` | Xoá tài liệu khỏi index (nội bộ) |

**Luồng SSE của chat**: `meta` (kèm `citations`) → `delta`* → (`mindmap_pending` → `mindmap`)? → `done` | `error`. (Tool gọi từ lần 2 trở đi phát thêm event `citations`.)

### Xác thực

- **Nhóm công khai `/api/v1/chatbot/*`**: `nginx-aio` verify token user (qua `api-aio`) rồi forward header `X-Auth-User-Id`. Route dùng `ensure_authenticated` → thiếu header trả **401**, có thì populate `CurrentUser`.
- **Nhóm nội bộ `/api/internal/v1/*`** (service-to-service): middleware `VerifyInternalToken` chốt header `X-Internal-Token` ngay ở prefix (sai → **403**), không gắn user.

---

## Lệnh thường dùng

```bash
# Xem log (dev)
docker compose -f docker/docker-compose.yml logs -f web worker

# Chạy migrations thủ công (web đã tự migrate lúc khởi động)
docker compose -f docker/docker-compose.yml exec web python manage.py migrate

# Django shell
docker compose -f docker/docker-compose.yml exec web python manage.py shell

# Đánh giá RAG (xem modules/chatbot/eval/README.md)
docker compose -f docker/docker-compose.yml exec web python manage.py eval_rag

# Dừng (giữ dữ liệu)
docker compose -f docker/docker-compose.yml down

# Dừng và XOÁ volume (opensearch/postgres/neo4j — mất index, phải re-ingest)
docker compose -f docker/docker-compose.yml down -v
```

---

## Thêm một module mới

Kiến trúc kiểu Laravel giúp thêm tính năng theo khuôn cố định:

1. Copy `modules/example/` sang `modules/<name>/` và đổi tên `AppConfig` trong `apps.py`.
2. Đăng ký app vào `INSTALLED_APPS` và trỏ migrations vào `MIGRATION_MODULES` — [config/settings.py](config/settings.py).
3. Khai URL trong `modules/<name>/routes/…` rồi thêm **một dòng** `include()` vào [config/urls.py](config/urls.py).

Chi tiết đầy đủ về khuôn (controllers, requests, services, repositories, transformers, per-route auth): [modules/example/README.md](modules/example/README.md).

---

## Biến môi trường

Config không bảo mật ở [.env.example](.env.example); **toàn bộ secret** ở `docker/secrets.env` (gitignored, template [docker/secrets.env.example](docker/secrets.env.example)). Docker nạp cả hai qua `env_file`. Các nhóm chính:

| Nhóm | Ví dụ biến | Nơi khai |
|---|---|---|
| Django | `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_SECRET_KEY` 🔐 | `.env` / secrets |
| Database (MariaDB dùng chung) | `DB_NAME=api_ai`, `DB_USER`, `DB_PASSWORD` 🔐, `DB_HOST`, `DB_PORT` | `.env` / secrets |
| Internal service-to-service | `INTERNAL_GATEWAY_URL`, `INTERNAL_TOKEN` 🔐 | `.env` / secrets |
| Celery / Redis | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | `.env` |
| Realtime | `REALTIME_REDIS_URL`, `REALTIME_CHANNEL_PREFIX` | `.env` |
| S3 / object storage | `AWS_S3_*`, `MEDIA_FOLDER` (🔐 key/secret) | secrets |
| Gemini / GenAI | `GEMINI_API_KEY` 🔐, `EMBEDDING_MODEL`, `GEMINI_*_MODEL` | `.env` / secrets |
| Provider LLM/Embedding | `LLM_PROVIDER`, `EMBEDDING_PROVIDER`, `OLLAMA_*` | `.env` |
| OpenSearch (RAG) | `OPENSEARCH_URL`, `OPENSEARCH_INDEX`, `OPENSEARCH_VECTOR_DIMS`, `OPENSEARCH_PASSWORD` 🔐 | `.env` / secrets |
| Truy hồi / Rerank | `RETRIEVE_TOP_K`, `RERANK_*` (🔐 `RERANK_API_KEY`) | `.env` / secrets |
| Chatbot (chat/mind map/quota/files) | `GEMINI_CHAT_MODEL`, `CHAT_MINDMAP_ENABLED`, `GEMINI_MINDMAP_MODEL`, `CHAT_ATTACHED_FILES_*`, `GEMINI_FILE_TTL_HOURS` | `.env` |
| LightRAG / KG | `LIGHTRAG_ENABLED`, `LIGHTRAG_PG_*`, `LIGHTRAG_NEO4J_*` (🔐 passwords) | `.env` / secrets |

Xem giá trị mặc định và ghi chú chi tiết trực tiếp trong [.env.example](.env.example). Ý nghĩa từng biến theo tính năng: xem README của module tương ứng, chủ yếu [modules/chatbot/README.md](modules/chatbot/README.md).
