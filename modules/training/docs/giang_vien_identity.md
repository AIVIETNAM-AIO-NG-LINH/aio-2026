# Định danh Giảng viên — `Data_Giang_Vien_Clean.csv`

> **Kết luận quan trọng:** KHÔNG có một cột đơn nào xác định được một giảng viên
> đã có trong hệ thống hay chưa. Phải dùng quy tắc tra cứu 2 tầng (xem dưới).

## 1. Grain của file

- 1126 dòng = **mỗi dòng là 1 lần phân công GV cho 1 lớp** (461 lớp, ~2.4 GV/lớp).
- **0 dòng trùng hoàn toàn** trên cả 20 cột → mỗi dòng là một bản ghi phân công riêng.
- Không có khóa tự nhiên → bảng nối `training_class_instructors` dùng **surrogate id**,
  KHÔNG đặt `unique` / `unique_together`.

## 2. Không cột nào unique để nhận diện GV

| Khóa thử | Kết quả |
|---|---|
| Mọi cột đơn | Cao nhất `Tên giảng viên` = 600 / 1126 → **không unique** |
| `Mã ngân sách` + `Mã giảng viên` | 99 trùng |
| `Mã ngân sách` + `Tên giảng viên` | 5 trùng |
| Toàn bộ 20 cột | 0 dòng trùng hoàn toàn |

Lý do cặp `(Mã ngân sách + Tên giảng viên)` vẫn trùng: cùng 1 GV trong cùng 1 lớp
nhưng **điểm học viên khác nhau** (vd lớp `2025K182`, Nguyễn Thương Huyền: 4.52 vs
4.57) — như 2 đợt ghi nhận điểm.

## 3. Vì sao mã không phủ hết — ai có mã, ai không

| Nguồn GV | Số dòng | Có `Mã giảng viên` | Có `Mã cán bộ` |
|---|---|---|---|
| GVNB | 676 | 583 | 676 |
| Thuê ngoài | 402 | 338 | 2 |
| Lớp cử đi học | 20 | 0 | 0 |
| Giám khảo VCB | 17 | 0 | 17 |
| Khách mời | 5 | 0 | 0 |
| Biên soạn TL | 3 | 2 | 3 |
| Teambuilding | 3 | 0 | 0 |

- **203 dòng không có `Mã giảng viên`** (chủ yếu thuê ngoài) → chỉ còn TÊN để nhận diện.
- `Tên giảng viên` không sạch: 600 distinct (raw) → 482 sau chuẩn hóa HOA + gộp space.

## 4. `Mã cán bộ` thực ra là khóa tin cậy (sau chuẩn hóa)

- Raw: 79/326 mã cán bộ ↔ >1 tên → tưởng loạn.
- Sau chuẩn hóa tên (UPPER + gộp khoảng trắng): chỉ còn **1/326**, và đó là mã rác `"0"`.
- ⇒ `Mã cán bộ` (≠ `"0"`) định danh ổn định **325/326 mã ↔ đúng 1 người**.

## 5. Quy tắc nhận biết GV đã có trong hệ thống (dùng khi import)

Tra theo thứ tự:

1. **Có `Mã cán bộ` (≠ "0")** → tra theo `employee_code`.
   Áp dụng GVNB / Giám khảo VCB / Biên soạn (~696 dòng). Rất tin cậy.
2. **Không có `Mã cán bộ`** → tra theo **TÊN đã chuẩn hóa** (viết HOA + gộp khoảng trắng).
   Áp dụng Thuê ngoài / Khách mời / Lớp cử đi học / Teambuilding (~430 dòng).
3. **Mã `"0"` coi như NULL** (giá trị rác).

Gợi ý hiện thực: thêm cột định danh chuẩn hóa `identity_key` (unique) trên
`TrainingInstructor`:

```
identity_key = "EMP:<ma_can_bo>"          nếu có mã cán bộ (≠ "0")
             = "NAME:<TÊN HOA gộp space>"  nếu không
```

Khi import: `TrainingInstructor.objects.get_or_create(identity_key=...)` →
tự biết GV đã tồn tại hay chưa, không tạo trùng. (Có thể đặt khóa này ở
script import thay vì cột model — tùy quyết định sau.)
