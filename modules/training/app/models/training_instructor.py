"""Model `TrainingInstructor` — một GIẢNG VIÊN (dimension người dạy).

Nguồn: file `Data_Giang_Vien_Clean.csv` (1126 dòng phân công). Mỗi GV xuất hiện
ở nhiều lớp → tách dimension người ra khỏi bảng nối `TrainingClassInstructor`
(nơi giữ điểm/thời lượng theo từng phân công).

Định danh KHÔNG ổn định để ép `unique`: 203 dòng thiếu `instructor_code`
(GV thuê ngoài), và cùng một mã có thể ghi khác tên (bản version E0017 vs
E0017.03). Giữ cả `instructor_code` lẫn `employee_code` làm khóa tra cứu mềm,
việc gộp người trùng để cho bước import xử lý — model không tự suy luận.

Thuộc tính người (đơn vị/chức vụ/cấp bậc) gần như ổn định theo mã GV nên đặt ở
đây; chỉ `Nguồn GV` là sạch tuyệt đối nên enum hóa (`InstructorSource`).
"""

from __future__ import annotations

from django.db import models

from modules.base.models import NotSoftDeleteModel

from modules.training.app.enums import InstructorSource


class TrainingInstructor(NotSoftDeleteModel):
    """Một giảng viên — định danh mềm theo mã GV / mã cán bộ / tên."""

    instructor_code = models.CharField(max_length=64, null=True, blank=True, db_index=True)  # Mã giảng viên (E0017.03)
    employee_code = models.CharField(max_length=32, null=True, blank=True, db_index=True)    # Mã cán bộ (đối với GVNB)
    name = models.CharField(max_length=255, db_index=True)                                   # Tên giảng viên
    unit = models.CharField(max_length=255, null=True, blank=True)                           # Đơn vị của GV (FTC, Sbank...)
    source = models.CharField(                                                               # Nguồn GV (GVNB/Thuê ngoài...)
        max_length=32, choices=InstructorSource.choices, null=True, blank=True
    )
    position = models.CharField(max_length=255, null=True, blank=True)                       # Chức vụ
    rank = models.CharField(max_length=64, null=True, blank=True)                            # Cấp bậc GVNB (Cơ bản/Trung cấp/Cao cấp)

    class Meta(NotSoftDeleteModel.Meta):
        db_table = "training_instructors"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"TrainingInstructor#{self.pk} ({self.name})"
