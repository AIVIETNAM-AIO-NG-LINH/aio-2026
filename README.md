# AI AIO — Django REST API (Chatbot RAG)

Backend AI cho hệ AIO: **Django 5.2 (LTS)** + **Django REST Framework** (API JSON thuần — không admin / không giao diện HTML), chạy trong **Docker**. Cung cấp một **chatbot RAG**: ingest tài liệu (PDF/Word) thành kho tri thức và trả lời hỏi-đáp dạng **SSE streaming** qua **Google ADK** (Agent + tool RAG).

ai-aio chạy *cạnh* api-aio trong stack `nginx-aio`: dùng chung **MariaDB** (DB `api_ai`), **Redis** (broker Celery) và mạng docker `aio-net`. Truy cập từ ngoài qua reverse-proxy nginx (`http://ai.localhost:8000`), không publish cổng ra host.

## Stack

| Thành phần | Lựa chọn |
|------------|----------|
| Web framework | Django 5.2 LTS |
| API | Django REST Framework (JSON-only) |
| Database | MariaDB (DB `api_ai`, dùng chung với api-aio) |
| Driver | mysqlclient |
| WSGI server (prod) | Gunicorn |
| Worker nền | Celery + Redis |
| Vector store | OpenSearch 2.19 (kNN/HNSW, parent-child) |
| LLM / Embedding | Google GenAI (Gemini) — extract, embed, rewrite, summary, chat |
| Luồng chat | Google ADK (Agent + tool RAG + Runner streaming SSE) |
| Object storage | S3 / MinIO (boto3) — tải file gốc để ingest |
| Knowledge graph (tùy chọn) | LightRAG + PostgreSQL/pgvector + Neo4j |
| Config | django-environ (biến môi trường) |
| Runtime | Python 3.13 (trong Docker) |

## Kiến trúc & cấu trúc thư mục

Mỗi tính năng là một **module** (Django app) trong `modules/`. Module `base/` cung cấp lớp nền dùng chung theo phong cách Laravel (model soft-delete, repository, service, transformer, catalog dịch, middleware, client tới dịch vụ ngoài).

```
ai-aio/
├── config/                      # Django project
│   ├── settings.py              # cấu hình 12-factor (env)
│   ├── urls.py                  # nối route các module
│   ├── celery.py                # app Celery (autodiscover tasks)
│   └── wsgi.py / asgi.py
├── modules/
│   ├── base/                    # lớp nền dùng chung (KHÔNG có endpoint)
│   │   ├── models/              # SoftDeleteModel / NotSoftDeleteModel + helpers
│   │   ├── repositories/        # BaseRepository (truy vấn dữ liệu)
│   │   ├── services/            # BaseService (nghiệp vụ, response/exception chuẩn)
│   │   ├── transformers/        # Fractal-style transformer (shape JSON cho FE)
│   │   ├── catalogs/            # khóa i18n cho translate()
│   │   ├── middleware/          # EnsureAuthenticated / VerifyInternalToken …
│   │   ├── clients/             # S3, Gemini, OpenSearch, LightRAG, internal HTTP
│   │   ├── requests/            # BaseFormRequest (validate input)
│   │   ├── singletons/          # CurrentUser (user của request hiện tại)
│   │   ├── supports/            # translate_helper
│   │   └── exceptions/          # ApiException + exception handler (shape lỗi FE)
│   ├── core/                    # health check — GET /api/health/
│   ├── example/                 # MODULE MẪU (CRUD) — copy để tạo module mới
│   ├── media/                   # model Media (read-only, bảng api-aio, managed=False)
│   └── chatbot/                 # CHATBOT RAG (tính năng chính)
│       ├── models/              # ChatConversation, ChatMessage, ChatbotDocument
│       ├── enums/               # *_status, message_role
│       ├── repositories/        # truy vấn conversation / message / document
│       ├── requests/            # ChatRequest, IngestDocumentRequest
│       ├── services/
│       │   ├── chat_service.py  # điều phối 1 lượt chat (prepare → stream SSE)
│       │   ├── ingest_service.py# enqueue ingest tài liệu
│       │   ├── chat/            # ADK (agent/runner/session/tools), prompt, sse, history
│       │   ├── rag/             # embedder, query_rewriter, reranker_client, config
│       │   └── opensearch/      # indexer, retriever, summary_indexer, ltm
│       ├── pipelines/           # thân ingest chạy trong worker (extract→chunk→embed→index)
│       ├── tasks/               # vỏ Celery: ingest, chat (title + LTM)
│       ├── transformers/        # conversation/message transformer
│       ├── views/               # ChatViewSet (SSE) + IngestDocumentView
│       └── urls/                # public.py (chat) + internal.py (ingest)
├── manage.py
├── requirements.txt
├── entrypoint.sh                # chờ DB → migrate → chạy server
├── docker/
│   ├── Dockerfile               # multi-stage build (Python 3.13)
│   ├── docker-compose.yml       # DEV: runserver + worker + opensearch (+ profile lightrag)
│   └── docker-compose.prod.yml  # PROD: Gunicorn + worker + opensearch
├── .env                         # biến môi trường (git-ignored)
└── .env.example                 # mẫu để copy thành .env
```

> **DB dùng chung:** ai-aio nối thẳng vào DB `api_ai` của api-aio. Bảng `media` và
> `chatbot_documents` thuộc api-aio nên model để `managed=False` (Django chỉ ĐỌC,
> chỉ ghi cột `status`, KHÔNG migrate cấu trúc). Các bảng riêng của ai-aio
> (`chat_conversations`, `chat_messages`, `django_*`, `auth_*`, `example`…) do
> `entrypoint.sh migrate` tạo trong cùng DB này.

## Yêu cầu trước khi chạy

ai-aio không tự dựng MariaDB / Redis — nó dùng chung từ stack `nginx-aio`. Vì vậy:

```bash
# 1. Tạo mạng dùng chung (1 lần)
docker network create aio-net

# 2. Up stack nginx-aio trước (cung cấp db + redis + reverse proxy)
#    (xem repo nginx-aio)
```

## Chạy nhanh (Development)

Yêu cầu: **Docker** + **Docker Compose** (không cần cài Python ở máy) và đã làm bước "Yêu cầu trước khi chạy".

```bash
# 1. Tạo .env từ mẫu rồi điền các secret (DB, INTERNAL_TOKEN, GEMINI_API_KEY, S3…)
cp .env.example .env

# 2. Build & chạy (web + worker + opensearch)
docker compose -f docker/docker-compose.yml up --build
```

Mẹo: `export COMPOSE_FILE=docker/docker-compose.yml` để khỏi gõ `-f` mỗi lần.

Health check (qua proxy): <http://ai.localhost:8000/api/health/> → trả về:

```json
{"status": "ok", "database": "up"}
```

Server dev tự reload khi sửa code (thư mục được mount vào container). Index OpenSearch giữ qua volume `opensearch-data`.

## Chạy production (Gunicorn)

```bash
docker compose -f docker/docker-compose.prod.yml up --build -d
```

Khác với dev: dùng Gunicorn (theo CMD trong Dockerfile), `DJANGO_DEBUG=False`, không mount code. Nhớ đổi `DJANGO_SECRET_KEY`, `INTERNAL_TOKEN`, secret DB/S3/Gemini trong `.env` trước khi deploy thật. Nếu đã có cluster OpenSearch riêng (có auth): xoá service `opensearch` trong compose và trỏ `OPENSEARCH_URL/USER/PASSWORD` sang cluster đó.

### Knowledge graph (LightRAG) — tùy chọn

PostgreSQL + Neo4j cho LightRAG nằm trong **profile `lightrag`** (mặc định KHÔNG lên). Chỉ bật khi `LIGHTRAG_ENABLED=true`:

```bash
docker compose -f docker/docker-compose.yml --profile lightrag up -d
```

## Endpoints

| Method | URL | Mô tả |
|--------|-----|-------|
| GET | `/api/health/` | Health check (app + kết nối DB) |
| POST | `/api/v1/chatbot/chat` | Hỏi-đáp RAG — trả lời **SSE** (`meta → delta* → done\|error`). Body: `{question, conversation_id?, top_k?}` |
| GET | `/api/v1/chatbot/conversations` | Danh sách hội thoại của user (phân trang) |
| GET | `/api/v1/chatbot/conversations/{id}/messages` | Tin nhắn của 1 hội thoại (phân trang) |
| POST | `/api/internal/v1/chatbot/documents/ingest` | **Nội bộ** — nhận `{document_id}`, enqueue ingest → `202` |
| GET · POST | `/api/examples/` | Module mẫu — list / create |
| GET · PUT · PATCH · DELETE | `/api/examples/{id}/` | Module mẫu — chi tiết / sửa / xoá |

**Xác thực:**

- Nhóm `/api/v1/chatbot/*` (công khai): nginx verify token user (qua api-aio) rồi forward header `X-Auth-User-Id`. Gate `ensure_authenticated` chặn 401 nếu thiếu, có thì populate `CurrentUser`.
- Nhóm `/api/internal/v1/*` (service-to-service): middleware `VerifyInternalToken` chốt header `X-Internal-Token` ở prefix (sai → 403). Không gắn user.

## Luồng chính

**Ingest tài liệu** (`/api/internal/v1/chatbot/documents/ingest` → Celery `chatbot.ingest_document`):
file gốc tải từ S3 → trích text theo trang (pypdf + Gemini OCR cho trang scan/ảnh) → chunk theo trang (kèm contextual header) → embed (Gemini) → index parent-child vào OpenSearch. Phụ (fail-safe, không chặn READY): index summary + LightRAG/KG. Status `chatbot_documents.status`: `PENDING → READY | FAILED`.

**Chat** (`/api/v1/chatbot/chat`, SSE qua Google ADK):
`prepare` (đồng bộ) tạo/lấy conversation, chặn lượt đang xử lý (409), lưu message user + placeholder bot → `stream` nạp LTM (hội thoại cũ liên quan) + lịch sử N lượt vào session ADK → Runner chạy agent, agent tự gọi tool `search_knowledge_base` (hybrid BM25 + kNN, RRF, rewrite + rerank) → stream câu trả lời. Sau lượt: Celery sinh tiêu đề hội thoại + lưu LTM (nền, fail-safe).

## Lệnh thường dùng

```bash
# Giả định đã export COMPOSE_FILE=docker/docker-compose.yml
# (nếu không, thêm -f docker/docker-compose.yml sau `docker compose`).

# Xem log web / worker
docker compose logs -f web
docker compose logs -f worker

# Tạo & chạy migrations sau khi thêm model (CHỈ bảng riêng của ai-aio)
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate

# Django shell
docker compose exec web python manage.py shell

# Dừng (giữ data) / dừng và xoá volume (mất index OpenSearch → phải re-ingest)
docker compose down
docker compose down -v
```

## Thêm một module mới

Cách nhanh nhất: **copy module mẫu** [modules/example/](modules/example/) rồi đổi tên.

1. Copy: `cp -r modules/example modules/<ten_module>`
2. Sửa `apps.py`: `name = "modules.<ten_module>"` (đổi luôn tên class config)
3. Đổi tên model / serializer / viewset / service trong các file tương ứng
4. Sửa `urls.py`: đổi prefix `router.register(r"<ten>", ...)`
5. Xoá file migration cũ trong `modules/<ten_module>/migrations/` (giữ lại `__init__.py`)
6. Đăng ký vào `INSTALLED_APPS` ([config/settings.py](config/settings.py)): thêm `"modules.<ten_module>"`
7. Nối route trong [config/urls.py](config/urls.py): `path("api/", include("modules.<ten_module>.urls"))`
8. Tạo migration: `docker compose exec web python manage.py makemigrations && ... migrate`

Tham khảo: [modules/core/](modules/core/) là module tối giản (chỉ health endpoint), [modules/example/](modules/example/) là module CRUD đầy đủ dùng làm template, [modules/chatbot/](modules/chatbot/) là module phức tạp dùng đủ lớp base (repository/service/transformer/pipeline/task).

## Biến môi trường

Xem [.env.example](.env.example) (đã chú thích chi tiết từng nhóm). Quan trọng nhất:

| Nhóm | Biến tiêu biểu |
|------|----------------|
| Django | `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` |
| Database (DB `api_ai` dùng chung) | `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` |
| Internal (ai-aio ↔ api-aio) | `INTERNAL_TOKEN` (PHẢI khớp api-aio), `INTERNAL_GATEWAY_URL` |
| Celery / Redis | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` |
| S3 / object storage | `AWS_S3_ENDPOINT/REGION/BUCKET/ACCESS_KEY/SECRET_KEY`, `MEDIA_FOLDER` |
| Google GenAI (Gemini) | `GEMINI_API_KEY`, `EMBEDDING_MODEL`, `GEMINI_EXTRACT_MODEL`, `GEMINI_CHAT_MODEL` |
| OpenSearch | `OPENSEARCH_URL`, `OPENSEARCH_INDEX`, `OPENSEARCH_VECTOR_DIMS` |
| Retrieve (hybrid + rerank) | `RETRIEVE_TOP_K/TOP_N/RRF_K`, `QUERY_REWRITE_*`, `RERANK_*` |
| Chat | `CHAT_CONTEXT_TOP_K`, `CHAT_HISTORY_SIZE`, `CHAT_TITLE_ENABLED`, `CHAT_LTM_*` |
| LightRAG (tùy chọn) | `LIGHTRAG_ENABLED`, `LIGHTRAG_PG_*`, `LIGHTRAG_NEO4J_*` |
</content>
</invoke>
