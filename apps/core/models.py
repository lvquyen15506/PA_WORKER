"""Danh mục, cài đặt, bộ đếm mã, cấu hình QR (docs/thiet-ke/models.md mục 3.3).

Danh mục dùng `is_active` thay cho xóa: mục đang được dùng thì chỉ ngừng sử dụng.
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .choices import CodeType, IdDocType
from .crypto import EncryptedTextField


class Department(models.Model):
    name = models.CharField("Tên phòng ban", max_length=100, unique=True)
    sort_order = models.PositiveSmallIntegerField("Thứ tự", default=0)
    is_active = models.BooleanField("Đang sử dụng", default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Section(models.Model):
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="sections", verbose_name="Phòng ban"
    )
    name = models.CharField("Tên bộ phận", max_length=100)
    sort_order = models.PositiveSmallIntegerField("Thứ tự", default=0)
    is_active = models.BooleanField("Đang sử dụng", default=True)

    class Meta:
        ordering = ["department__sort_order", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "name"], name="uniq_section_department_name"
            )
        ]

    def __str__(self):
        return self.name


class Team(models.Model):
    section = models.ForeignKey(
        Section, on_delete=models.PROTECT, related_name="teams", verbose_name="Bộ phận"
    )
    name = models.CharField("Tên tổ", max_length=100)
    sort_order = models.PositiveSmallIntegerField("Thứ tự", default=0)
    is_active = models.BooleanField("Đang sử dụng", default=True)

    class Meta:
        ordering = ["section__sort_order", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["section", "name"], name="uniq_team_section_name")
        ]

    def __str__(self):
        return self.name


class Position(models.Model):
    name = models.CharField("Tên chức danh", max_length=100, unique=True)
    is_active = models.BooleanField("Đang sử dụng", default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Shift(models.Model):
    name = models.CharField("Tên ca", max_length=50, unique=True)
    time_range = models.CharField("Khung giờ", max_length=20, blank=True)
    is_active = models.BooleanField("Đang sử dụng", default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ApplicationSource(models.Model):
    name = models.CharField("Nguồn ứng tuyển", max_length=100, unique=True)
    is_active = models.BooleanField("Đang sử dụng", default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class EducationLevel(models.Model):
    name = models.CharField("Trình độ", max_length=100, unique=True)
    rank = models.PositiveSmallIntegerField("Cấp bậc", unique=True)  # số lớn = cao hơn (câu 14)
    is_active = models.BooleanField("Đang sử dụng", default=True)

    class Meta:
        ordering = ["rank"]

    def __str__(self):
        return self.name


class RequiredDocumentGroup(models.Model):
    name = models.CharField("Nhóm tài liệu bắt buộc", max_length=100, unique=True)
    sort_order = models.PositiveSmallIntegerField("Thứ tự", default=0)
    is_active = models.BooleanField("Đang sử dụng", default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class DocumentType(models.Model):
    name = models.CharField("Loại tài liệu", max_length=100, unique=True)
    # Mã cố định cho loại mà mã nguồn dùng (PORTRAIT, CONTRACT...); không sửa trên giao diện.
    system_code = models.CharField("Mã hệ thống", max_length=30, null=True, blank=True, unique=True)
    required_group = models.ForeignKey(
        RequiredDocumentGroup,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="document_types",
        verbose_name="Nhóm bắt buộc",
    )
    sort_order = models.PositiveSmallIntegerField("Thứ tự", default=0)
    is_active = models.BooleanField("Đang sử dụng", default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.system_code = self.system_code or None  # rỗng -> NULL để unique cho phép nhiều dòng
        super().save(*args, **kwargs)


_DIGITS = [MinValueValidator(3), MaxValueValidator(8)]


class SystemSetting(models.Model):
    """Bảng Settings: một dòng duy nhất (pk = 1), đọc qua SystemSetting.load()."""

    worker_code_prefix = models.CharField("Tiền tố mã hồ sơ", max_length=10, default="HS")
    worker_code_use_year = models.BooleanField("Mã hồ sơ có năm", default=True)
    worker_code_digits = models.PositiveSmallIntegerField(
        "Số chữ số mã hồ sơ", default=5, validators=_DIGITS
    )
    employee_code_prefix = models.CharField("Tiền tố mã nhân viên", max_length=10, default="CN")
    employee_code_use_year = models.BooleanField("Mã nhân viên có năm", default=False)
    employee_code_digits = models.PositiveSmallIntegerField(
        "Số chữ số mã nhân viên", default=5, validators=_DIGITS
    )
    expiry_warning_days = models.PositiveSmallIntegerField(
        "Cảnh báo sắp hết hạn (ngày)", default=30
    )
    ocr_confidence_threshold = models.PositiveSmallIntegerField(
        "Ngưỡng tin cậy OCR (%)", default=80
    )
    failed_retention_months = models.PositiveSmallIntegerField(
        "Lưu hồ sơ ứng viên không được tuyển (tháng)", default=12
    )
    resigned_retention_years = models.PositiveSmallIntegerField(
        "Lưu hồ sơ công nhân đã nghỉ (năm)", default=10
    )
    auto_archive_resigned_days = models.PositiveSmallIntegerField(
        "Tự Lưu trữ sau khi nghỉ việc (ngày)", default=30
    )
    auto_archive_failed_days = models.PositiveSmallIntegerField(
        "Tự Lưu trữ sau kết quả không đạt / bị từ chối (ngày)", default=30
    )
    stale_draft_months = models.PositiveSmallIntegerField("Hồ sơ bỏ dở (tháng)", default=6)
    intake_ttl_hours = models.PositiveSmallIntegerField(
        "Thời hạn phiên nhận diện (giờ)", default=24
    )
    external_ocr_enabled = models.BooleanField("Bật API OCR ngoài", default=False)
    external_ocr_url = models.URLField("Địa chỉ API OCR ngoài", blank=True)
    # Ghi một lần ở lần khởi động đầu, không sửa, không hiện trên giao diện (câu 31).
    key_check_enc = EncryptedTextField(null=True, blank=True)
    key_check_hash = models.CharField(max_length=64, null=True, blank=True)
    updated_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cài đặt hệ thống"

    def __str__(self):
        return "Cài đặt hệ thống"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Không xóa dòng cài đặt hệ thống.")

    @classmethod
    def load(cls):
        return cls.objects.get(pk=1)


class CodeSequence(models.Model):
    """Bộ đếm mã; chỉ tăng. Cấp mã bằng apps.core.codes.next_code (bước 6)."""

    code_type = models.CharField(max_length=10, choices=CodeType.choices)
    year = models.PositiveSmallIntegerField(default=0)  # 0 khi mã không có năm
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["code_type", "year"], name="uniq_codesequence_type_year"
            )
        ]

    def __str__(self):
        return f"{self.code_type} {self.year}: {self.last_number}"


DEFAULT_QR_FIELD_ORDER = [
    "id_number",
    "old_id_number",
    "full_name",
    "date_of_birth",
    "gender",
    "permanent_address",
    "issue_date",
]


def default_qr_field_order():
    return list(DEFAULT_QR_FIELD_ORDER)


QR_ID_DOC_TYPES = [
    (IdDocType.CCCD_2021.value, IdDocType.CCCD_2021.label),
    (IdDocType.CAN_CUOC_2024.value, IdDocType.CAN_CUOC_2024.label),
]


class QrFormat(models.Model):
    """Cấu trúc QR theo mẫu thẻ (câu 20, giả định chưa kiểm chứng bằng thẻ thật)."""

    id_doc_type = models.CharField(max_length=20, choices=QR_ID_DOC_TYPES, unique=True)
    separator = models.CharField(max_length=5, default="|")
    field_order = models.JSONField(default=default_qr_field_order)
    date_format = models.CharField(max_length=20, default="ddmmyyyy")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.id_doc_type
