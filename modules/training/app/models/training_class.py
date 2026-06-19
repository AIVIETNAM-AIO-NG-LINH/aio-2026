"""Model `TrainingClass` — một LỚP đào tạo (1 dòng = 1 lần mở lớp).

Nguồn: file `Data_Khoa_Hoc_Clean.csv`. Mỗi dòng là một LỚP, định danh bởi
`budget_code` (Mã ngân sách / VCB class code) — khóa join duy nhất sang
`TrainingInstructor` và `TrainingStudent` (khớp 100% giữa 3 file).

LƯU Ý grain: `item_id` (Mã khóa học / Item ID) là định danh KHÓA (chương trình,
~203 khóa); một khóa mở NHIỀU lớp. Câu hỏi ở cấp khóa phải `GROUP BY item_id`,
đừng nhầm mỗi dòng là một khóa. `class_id` (Mã lớp / Class ID) KHÔNG đáng tin
(có giá trị placeholder trùng) nên chỉ giữ để tham khảo, không dùng làm khóa.

Điểm số để `null` (không default 0): nhiều lớp chưa được đánh giá — coi NULL=0
sẽ làm sai trung bình. Mọi phép `AVG` phải bỏ NULL.
"""

from __future__ import annotations

from django.db import models

from modules.base.models import NotSoftDeleteModel

from modules.training.app.enums import CommitmentStatus, TestStatus

from .training_period import TrainingPeriod
from .training_staff import TrainingStaff


class TrainingClass(NotSoftDeleteModel):
    """Một lớp đào tạo — bảng trung tâm liên kết giảng viên và học viên."""

    # --- Định danh / khóa join ---------------------------------------------
    budget_code = models.CharField(max_length=32, unique=True)      # Mã ngân sách (VCB class code) — KHÓA JOIN
    item_id = models.CharField(max_length=32, null=True, blank=True, db_index=True)  # Mã khóa học (Item ID) — định danh KHÓA
    class_id = models.CharField(max_length=32, null=True, blank=True)  # Mã lớp (Class ID) — tham khảo, không tin cậy

    # --- Thông tin lớp ------------------------------------------------------
    class_name = models.CharField(max_length=255, db_index=True)    # Tên lớp học (Course name)
    period = models.ForeignKey(                                  # Kỳ ghi nhận → training_periods
        TrainingPeriod,
        on_delete=models.SET_NULL,
        db_column="period_id",
        related_name="classes",
        null=True,
        blank=True,
    )
    start_date = models.DateField(null=True, blank=True)            # Ngày bắt đầu (Start)
    end_date = models.DateField(null=True, blank=True)              # Ngày kết thúc (End)

    # --- Số lượng học viên / lượt -------------------------------------------
    student_count = models.IntegerField(null=True, blank=True)             # Số lượng học viên
    manager_attendance_count = models.IntegerField(null=True, blank=True)  # Số lượt đào tạo CBQL
    staff_attendance_count = models.IntegerField(null=True, blank=True)    # Số lượt đào tạo nhân viên
    passed_count = models.IntegerField(null=True, blank=True)              # Số lượng Đạt
    failed_count = models.IntegerField(null=True, blank=True)              # Số lượng Không Đạt

    # --- Thời lượng ---------------------------------------------------------
    duration_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)           # Thời lượng (Giờ)
    internal_duration_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)  # Thời lượng nội bộ (giờ)
    training_hours = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)          # Số giờ đào tạo (thời lượng*số hv đạt)

    # --- Điểm đánh giá (cấp lớp; NULL khi chưa đánh giá) ---------------------
    content_score = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)      # Điểm đánh giá nội dung
    instructor_score = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)   # Điểm TB của HV đánh giá GV
    logistics_score = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)    # Điểm đánh giá Hậu cần
    class_mgmt_score = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)   # Điểm đánh giá QLL
    overall_avg_score = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)  # Điểm đánh giá TB chung cả khóa

    # --- Vận hành -----------------------------------------------------------
    # Quản lý lớp: 1 lớp có thể có NHIỀU người (dữ liệu ghép bằng "+") → M2M.
    # Bảng nối lưu (training_class_id, training_staff_id), không lặp tên.
    class_managers = models.ManyToManyField(
        TrainingStaff, related_name="managed_classes", blank=True
    )
    # LĐP QLĐT: mỗi lớp đúng 1 người → FK đơn, cột `training_dept_leader_id`.
    training_dept_leader = models.ForeignKey(
        TrainingStaff,
        on_delete=models.SET_NULL,
        db_column="training_dept_leader_id",
        related_name="led_classes",
        null=True,
        blank=True,
    )
    has_test = models.CharField(                                    # Bài kiểm tra (Có/Không)
        max_length=16, choices=TestStatus.choices, null=True, blank=True
    )
    training_commitment = models.CharField(                         # Cam kết đào tạo (Có/Không)
        max_length=16, choices=CommitmentStatus.choices, null=True, blank=True
    )
    note = models.TextField(null=True, blank=True)                                 # Ghi chú

    class Meta(NotSoftDeleteModel.Meta):
        db_table = "training_classes"
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"TrainingClass#{self.pk} ({self.budget_code} - {self.class_name})"
