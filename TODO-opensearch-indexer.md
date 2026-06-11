# TODO — OpenSearch Indexer (`modules/chatbot/services/opensearch/indexer.py`)

Các điểm cần cải thiện của `OpenSearchIndexer.index_document` (review 2026-06-11).
Xếp theo độ ưu tiên; fix xong mục nào thì tick mục đó.

## Ưu tiên cao (sửa rẻ, tránh lỗi thật)

- [x] **1. Race khi tạo index** — `ensure_index` check-rồi-tạo không có lock:
  2 worker cùng ingest tài liệu đầu tiên → 1 worker ăn lỗi
  `resource_already_exists_exception` → tài liệu đó FAILED oan.
  - Vị trí: `ensure_index` (`indexer.py`)
  - Cách sửa: bọc `indices.create` trong try/except, nuốt lỗi
    "resource_already_exists" (coi như index đã có), các lỗi khác vẫn raise.
  - ĐÃ SỬA (2026-06-11): thêm `_create_index_if_missing(index, body)` vào
    `BaseOpenSearchClient` (nuốt đúng `resource_already_exists_exception`,
    lỗi khác vẫn raise) — 3 chỗ cùng pattern đều chuyển sang dùng:
    `indexer.ensure_index`, `summary_indexer._ensure_index`, `ltm._ensure_index`.

- [x] **2. Đổi `vector_dims` là bẫy ngầm** — mapping chốt `dimension` lúc tạo
  index; sau này đổi env số chiều thì `ensure_index` thấy index tồn tại → giữ
  mapping cũ → mọi vector mới sai chiều, embed/index fail hàng loạt, lỗi khó lần.
  - Vị trí: `ensure_index` + `_index_body` (`indexer.py`)
  - Cách sửa: khi index đã tồn tại, đọc mapping hiện có, so `dimension` của
    `chunk_vector` với `self.vector_dims`; lệch thì log error nói rõ phải
    reindex (hoặc raise sớm) thay vì để fail từng chunk về sau.
  - ĐÃ SỬA (2026-06-11): `_create_index_if_missing` (BaseOpenSearchClient) khi
    index đã tồn tại sẽ gọi `_verify_vector_dims`: so `dimension` của MỌI field
    `knn_vector` trong mapping hiện có với mapping code mong đợi → lệch thì
    raise RuntimeError kèm hướng xử lý (trả env về dims cũ hoặc reindex).
    Check generic nên cover cả 3 index (chunk_vector / summary_vector /
    content_vector). Lỗi ĐỌC mapping chỉ log warning, không chặn ingest.

## Ưu tiên vừa (hiệu năng / độ bền khi tải tăng)

- [ ] **3. `refresh` 2 lần mỗi tài liệu** — `refresh=True` ở `delete_by_query`
  + `indices.refresh` cuối `index_document`; refresh là thao tác nặng, ingest
  hàng loạt sẽ tốn I/O đáng kể.
  - Giữ refresh lúc xoá (cần, tránh bulk mới đụng bản chưa xoá hẳn).
  - Cách sửa: bỏ `indices.refresh` cuối, hoặc đổi sang `refresh="wait_for"`
    trong `helpers.bulk` nếu cần search thấy ngay sau ingest.

- [ ] **4. `helpers.bulk` không có retry** — một lỗi mạng thoáng qua làm rớt cả
  tài liệu (exception lên catch-all của ingest → FAILED). Status FAILED là
  trung thực nên chấp nhận được ở Phase hiện tại.
  - Cách sửa: thêm retry/backoff quanh `helpers.bulk` (hoặc dựa vào Celery
    retry của task ingest khi bật ở Phase sau — chọn 1 trong 2, tránh retry kép).

## Ghi nhận (chưa cần làm, biết để khỏi bất ngờ)

- [ ] **5. Không atomic — có "khoảng trống" khi re-ingest** — giữa lúc xoá bản
  cũ và bulk xong bản mới, tài liệu biến mất khỏi search; worker chết giữa
  chừng → mất hẳn/partial trong khi DB chỉ thấy FAILED. Khối lượng hiện tại
  chấp nhận được.
  - Hướng sửa nếu cần zero-downtime: ghi bản mới trước (ID theo version/lần
    ingest) rồi mới xoá bản cũ; hoặc dùng alias trỏ qua lại.

- [ ] **6. Kiến trúc parent-child join có đáng không** — join field tốn chi phí
  query (parent_id lookup, mget parent khi retrieve) trong khi metadata parent
  (tên file, mime_type…) có thể denormalize thẳng vào từng chunk: đơn giản hơn,
  nhanh hơn, khỏi cần routing. Đổi lại parent-child tiết kiệm dung lượng và
  sửa metadata chỉ chạm 1 doc. Hệ đã chạy thì KHÔNG đáng đập đi — chỉ xem lại
  nếu hiệu năng truy hồi thành vấn đề (đây là nơi nhìn đầu tiên).
