# Module `media`

Module cung cấp **model `Media` chỉ-đọc** trỏ thẳng vào bảng `media` của **api-aio** (trong DB `api_ai` dùng chung). Đây không phải module tính năng: **không có endpoint, không controller, không service, không upload file** — nó chỉ expose một model + repository để các module khác (đặc biệt là [chatbot](../chatbot/README.md)) tra cứu thông tin file (đường dẫn S3, mime type, loại tài liệu…) khi đính kèm file vào chat hoặc ingest tài liệu vào kho tri thức.

Việc upload, phân loại và ghi bản ghi `media` hoàn toàn thuộc api-aio. Ở đây Django **chỉ ĐỌC** — bảng để `managed = False` nên `makemigrations`/`migrate` **không** tạo hay đổi cấu trúc bảng.

## Cấu trúc thư mục

Theo layout module kiểu Laravel của repo: toàn bộ code nằm trong `app/`, [apps.py](apps.py) trỏ `name` vào `modules.media.app` và giữ `label = "media"`.

```
media/
├── apps.py                       # AppConfig (name="modules.media.app", label="media")
├── app/
│   ├── models/
│   │   └── media.py              # model Media (read-only, managed=False) + accessor document_kind / url
│   ├── enums/
│   │   └── file_type.py          # FileType: 8 nhóm phân loại file (PDF/EXCEL/WORD/…)
│   └── repositories/
│       └── media_repository.py   # MediaRepository — gom truy vấn bảng `media` một chỗ
└── database/
    └── migrations/               # rỗng (chỉ __init__.py) — bảng do api-aio sở hữu, không migrate
```

> Không có `routes/`, `http/`, `services/`, `transformers/`… vì module này không phục vụ request nào. Module được đăng ký vào `INSTALLED_APPS` qua `modules.media.apps.MediaConfig` và migrations được ánh xạ sang `modules.media.database.migrations` bằng `MIGRATION_MODULES` (xem [../../config/settings.py](../../config/settings.py)), nhưng thư mục migrations cố ý để rỗng.

## Giải thích theo lớp

### Model — [app/models/media.py](app/models/media.py)

`Media` kế thừa [SoftDeleteModel](../base/app/models/soft_delete_model.py) của module base. Điểm mấu chốt ở `Meta`:

```python
class Meta(SoftDeleteModel.Meta):
    db_table = "media"     # bảng thật trong DB api_ai
    managed = False        # Django CHỈ ĐỌC — không tạo/migrate cấu trúc bảng
```

`managed = False` là điều quan trọng nhất của module: bảng `media` do **api-aio** sở hữu và ghi; ai-aio chỉ đọc để lấy metadata file. Vì kế thừa `SoftDeleteModel`, `Media.objects` mặc định **loại bản ghi đã soft-delete** (cột `deleted_at`), còn `Media.all_objects` gồm cả bản ghi đã xoá mềm.

**Các field ánh xạ cột bảng `media`:**

| Field | Kiểu | Cột | Ghi chú |
|-------|------|-----|---------|
| `id` | BigAutoField | `id` | PK (từ `BaseModel`) |
| `file_name` | CharField(255) | `file_name` | tên file lưu trên storage — dùng dựng object key / URL S3 |
| `original_name` | CharField(255) | `original_name` | tên gốc do người dùng upload (dùng cho `__str__`) |
| `mime_type` | CharField(255), null | `mime_type` | MIME thật của file (ưu tiên khi suy ra loại tài liệu) |
| `type` | CharField(255), null | `type` | phân loại phụ do api-aio khai |
| `file_type` | CharField(20), choices=`FileType` | `file_type` | nhóm phân loại hiển thị (do client khai — có thể sai/thiếu) |
| `size` | DecimalField(12, 2) | `size` | dung lượng file, **đơn vị MB**, 2 chữ số thập phân |
| `created_at` / `updated_at` | DateTimeField | — | timestamps (từ `BaseModel`) |
| `deleted_at` | DateTimeField, null | `deleted_at` | mốc soft-delete (từ `SoftDeleteModel`) |

**Accessor (property tính toán, không phải cột):**

- `document_kind -> "PDF" | "WORD" | None` — loại tài liệu có thể ingest vào chatbot. **Ưu tiên `mime_type`** (`application/pdf`, `application/msword`, mime của `.docx`), **fallback về `file_type`**; trả `None` nếu không phải tài liệu hỗ trợ. Lý do ưu tiên mime: cột `file_type` do client khai nên có thể sai/thiếu.
- `url -> str | None` — URL công khai của file trên S3/object storage, dựng từ `file_name` qua [S3Client.public_url()](../base/app/clients/s3_client.py) (cùng nguồn object key với lúc ingest đọc file, khớp link api-aio sinh ra). Import `S3Client` cục bộ trong property để tránh phụ thuộc boto3 lúc import model; **nuốt exception → trả `None`** nếu thiếu cấu hình S3 hay lỗi, caller tự lo fallback.

### Enum — [app/enums/file_type.py](app/enums/file_type.py)

`FileType(models.TextChoices)` — clone của `FileType` bên api-aio, phân loại media thành **8 nhóm** lưu ở cột `media.file_type`:

| Giá trị | Ý nghĩa |
|---------|---------|
| `PDF` | tài liệu PDF |
| `EXCEL` | bảng tính |
| `WORD` | tài liệu Word |
| `POWERPOINT` | trình chiếu |
| `IMAGE` | ảnh |
| `VIDEO` | video |
| `ZIP` | file nén |
| `FILE` | loại khác / mặc định |

Enum chỉ để cast/đọc giá trị cột `file_type` ra kiểu enum; việc phân loại tại thời điểm upload nằm ở api-aio. Trong `document_kind`, chỉ `PDF` và `WORD` được coi là tài liệu ingest được.

### Repository — [app/repositories/media_repository.py](app/repositories/media_repository.py)

`MediaRepository(BaseRepository[Media])` gom mọi truy vấn bảng `media` về một chỗ (mirror pattern Laravel). Quy ước: service/helper của các module khác **không** query `Media.objects` trực tiếp mà đi qua repository này. Vì `query()` của [BaseRepository](../base/app/repositories/base_repository.py) dùng manager mặc định (`objects`), **bản ghi soft-delete tự bị loại**.

Ngoài các method kế thừa từ base (`find(id)`, `query()`…), repository thêm:

- `map_by_id(media_ids: list[int]) -> dict[int, Media]` — nạp nhiều media trong **một query** và trả map `id → Media`, tiện khi đính kèm nhiều file cùng lúc. Id không tồn tại / đã soft-delete đơn giản là không có trong map. List rỗng trả `{}`.

## Endpoint

Module **không có endpoint nào**. Nó không được nối vào [../../config/urls.py](../../config/urls.py); giá trị của nó là cung cấp model + repository cho các module khác dùng nội bộ.

## Cách các module khác dùng module này

Module `media` là dependency đọc-metadata của [chatbot](../chatbot/README.md). Các điểm tích hợp thực tế:

- **Đính kèm file trong chat** — `chat_attachments` gọi `MediaRepository().map_by_id(media_ids)` để nạp media theo `media_ids` FE gửi, rồi dùng `media.url` / `media.mime_type` / `media.original_name` / `media.document_kind` để đẩy file lên Gemini Files API (xem [../chatbot/app/support/chat_attachments.py](../chatbot/app/support/chat_attachments.py)).
- **Ingest tài liệu** — pipeline ingest đọc `media.document_kind` để quyết định cách trích text (PDF vs Word), xem [../chatbot/app/pipelines/ingest.py](../chatbot/app/pipelines/ingest.py).
- **Trỏ nguồn (citation)** — tool `document_link` gọi `MediaRepository().find(media_id)` rồi lấy `Media.url` để dựng link tài liệu trong câu trả lời, xem [../chatbot/app/tools/document_link.py](../chatbot/app/tools/document_link.py).
- **Quan hệ FK** — model `ChatbotDocument` (cũng `managed = False`, bảng `chatbot_documents` của api-aio) khai `ForeignKey(Media, db_column="media_id")`: mỗi tài liệu học của chatbot trỏ tới một bản ghi `media`, xem [../chatbot/app/models/chatbot_document.py](../chatbot/app/models/chatbot_document.py).

## Biến môi trường liên quan

Module không đọc biến môi trường trực tiếp, nhưng accessor `Media.url` phụ thuộc cấu hình S3 (qua `S3Client`). Các biến liên quan (khai ở [../../.env.example](../../.env.example)):

| Biến | Vai trò |
|------|---------|
| `AWS_S3_URL` | base URL công khai (ưu tiên nhất khi dựng `Media.url`) |
| `AWS_S3_ENDPOINT` | endpoint S3/MinIO — fallback dựng URL `{endpoint}/{bucket}/{key}` |
| `AWS_S3_BUCKET` | tên bucket chứa file media |
| `AWS_S3_REGION` | region S3 |
| `AWS_S3_ACCESS_KEY` / `AWS_S3_SECRET_KEY` | credential (chỉ dùng khi tải file thật lúc ingest, không cần cho `public_url`) |
| `MEDIA_FOLDER` | thư mục prefix của object key (`{MEDIA_FOLDER}/{file_name}`), mặc định `media` |

Cấu hình S3 phải **khớp api-aio** để `Media.url` sinh ra link đúng với link mà api-aio dùng.

## Ghi chú tích hợp

- **Sở hữu bảng:** cấu trúc bảng `media` là của **api-aio**. Ở ai-aio, `Media` để `managed = False` — không bao giờ chạy migration lên bảng này. Nếu api-aio đổi schema bảng `media`, cần cập nhật field trong [app/models/media.py](app/models/media.py) tay cho khớp.
- **Kế thừa base:** `Media` dựa trên [SoftDeleteModel](../base/app/models/soft_delete_model.py) và `MediaRepository` dựa trên [BaseRepository](../base/app/repositories/base_repository.py) của module [base](../base/README.md) — soft-delete và các scope truy vấn dùng chung đến từ đó.
- **Read-only nghiêm ngặt:** không có luồng ghi trong module này. Mọi thao tác upload/sửa/xoá file thuộc api-aio; ai-aio chỉ đọc metadata phục vụ chatbot.
