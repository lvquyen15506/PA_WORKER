"""Hồ sơ công nhân và bảng con (docs/thiet-ke/models.md mục 3.4).

Chuyển trạng thái xác minh chỉ qua apps.workers.workflow (Phase 4); mã hồ sơ sinh bằng
apps.core.codes.next_code (bước 6).
"""

from django.db import models
from django.utils import timezone

from apps.core.choices import (
    AnonymizationKind,
    ConsentMethod,
    FieldSource,
    Gender,
    IdDocType,
    RetentionBasis,
    VerificationStatus,
)
from apps.core.crypto import EncryptedTextField, compute_id_hash
from apps.core.models_base import AppendOnlyModel
from apps.core.text import compute_name_search
from apps.core.validators import validate_phone


class Worker(models.Model):
    worker_code = models.CharField("Mã hồ sơ", max_length=20, unique=True)
    employee_code = models.CharField(
        "Mã nhân viên", max_length=20, unique=True, null=True, blank=True
    )
    full_name = models.CharField("Họ tên", max_length=100)
    # Họ tên không dấu, chữ thường; tính lại mỗi lần save() bằng compute_name_search.
    name_search = models.CharField(max_length=100, db_index=True, editable=False)
    date_of_birth = models.DateField("Ngày sinh", null=True, blank=True, db_index=True)
    gender = models.CharField("Giới tính", max_length=10, choices=Gender.choices, blank=True)
    nationality = models.CharField("Quốc tịch", max_length=50, default="Việt Nam")
    phone = models.CharField(
        "Số điện thoại", max_length=10, db_index=True, validators=[validate_phone]
    )
    email = models.EmailField("Email", blank=True)
    current_address = models.CharField("Nơi ở hiện tại", max_length=255, blank=True)
    skills = models.TextField("Kỹ năng", blank=True)
    note = models.TextField("Ghi chú", blank=True)
    verification_status = models.CharField(
        "Trạng thái hồ sơ",
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.DRAFT,
        db_index=True,
    )
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="+", verbose_name="Người tạo"
    )
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    # Cập nhật khi sửa hồ sơ và khi dữ liệu con đổi (qua touch()); dùng cho quy tắc hồ sơ bỏ dở.
    updated_at = models.DateTimeField("Cập nhật lần cuối", default=timezone.now, db_index=True)
    anonymized_at = models.DateTimeField("Ẩn danh hóa lúc", null=True, blank=True)

    def __str__(self):
        return self.worker_code

    def save(self, *args, **kwargs):
        self.name_search = compute_name_search(self.full_name)
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    def touch(self):
        """Ghi nhận có thay đổi ở dữ liệu con của hồ sơ."""
        now = timezone.now()
        Worker.objects.filter(pk=self.pk).update(updated_at=now)
        self.updated_at = now


class IdentityDocument(models.Model):
    worker = models.OneToOneField(
        Worker, on_delete=models.PROTECT, related_name="identity", verbose_name="Hồ sơ"
    )
    id_doc_type = models.CharField(
        "Loại giấy tờ", max_length=20, choices=IdDocType.choices, blank=True
    )
    id_number_enc = EncryptedTextField("Số định danh", null=True, blank=True)
    # HMAC của số định danh đã chuẩn hóa; kiểm tra trùng. Tính tự động trong save().
    id_number_hash = models.CharField(
        max_length=64, unique=True, null=True, blank=True, editable=False
    )
    old_id_number_enc = EncryptedTextField("Số CMND cũ", null=True, blank=True)
    issue_date = models.DateField("Ngày cấp", null=True, blank=True)
    issue_place = models.CharField("Nơi cấp", max_length=255, blank=True)
    expiry_date = models.DateField("Có giá trị đến", null=True, blank=True)
    hometown = models.CharField("Quê quán", max_length=255, blank=True)
    birth_registration_place = models.CharField("Nơi đăng ký khai sinh", max_length=255, blank=True)
    permanent_address_enc = EncryptedTextField("Nơi thường trú", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Giấy tờ của {self.worker.worker_code}"

    def save(self, *args, **kwargs):
        self.id_number_hash = compute_id_hash(self.id_number_enc)
        super().save(*args, **kwargs)


class IdentityFieldSource(models.Model):
    """Nguồn từng trường do máy đọc (QR/OCR/Nhập tay), độ tin cậy, người xác nhận."""

    worker = models.ForeignKey(Worker, on_delete=models.PROTECT, related_name="field_sources")
    field_name = models.CharField(max_length=50)
    source = models.CharField(max_length=10, choices=FieldSource.choices)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    edited_by_user = models.BooleanField(default=False)
    confirmed_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    confirmed_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["worker", "field_name"], name="uniq_fieldsource_worker_field"
            )
        ]

    def __str__(self):
        # Không dùng giá trị cá nhân trong __str__ (có thể lọt vào nhật ký, log, trang lỗi).
        return f"{self.worker.worker_code} – nguồn #{self.pk}"


class EmergencyContact(models.Model):
    worker = models.ForeignKey(Worker, on_delete=models.PROTECT, related_name="emergency_contacts")
    full_name = models.CharField("Họ tên", max_length=100)
    relationship = models.CharField("Quan hệ", max_length=50)
    phone = models.CharField("Số điện thoại", max_length=10, validators=[validate_phone])
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.worker.worker_code} – liên hệ #{self.sort_order}"


class DataConsent(models.Model):
    """Lịch sử ghi nhận đồng ý; bản ghi mới nhất là hiệu lực."""

    worker = models.ForeignKey(Worker, on_delete=models.PROTECT, related_name="consents")
    consented = models.BooleanField("Đồng ý")
    consent_date = models.DateField("Ngày đồng ý")
    method = models.CharField("Hình thức", max_length=20, choices=ConsentMethod.choices)
    # Bắt buộc khi method = PAPER (biên bản đã ký, loại CONSENT).
    # Tham chiếu bằng chuỗi để tránh import vòng với app documents.
    document = models.ForeignKey(
        "documents.WorkerDocument",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="consents",
    )
    recorded_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at", "-id"]

    def __str__(self):
        return f"{self.worker.worker_code} – đồng ý {self.consent_date}"


class StatusChange(AppendOnlyModel):
    """Chỉ thêm; nguồn của dòng thời gian trạng thái (câu 11)."""

    worker = models.ForeignKey(Worker, on_delete=models.PROTECT, related_name="status_changes")
    from_status = models.CharField(max_length=20, choices=VerificationStatus.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=VerificationStatus.choices)
    # Lý do hệ thống tự điền chỉ dùng mã hồ sơ, không họ tên (câu 30).
    reason = models.TextField(blank=True)
    # True khi lý do do người dùng gõ (có thể chứa tên): ẩn danh hóa thay bằng "(đã ẩn danh)"
    # (retention._redact_status_reasons, models.md 4.7). Lý do hệ thống tự điền là False.
    reason_by_user = models.BooleanField(default=False)
    changed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["changed_at", "id"]

    def __str__(self):
        return f"{self.worker.worker_code}: {self.from_status or '—'} → {self.to_status}"


class AnonymizationRecord(models.Model):
    """Biên bản hủy (ẩn danh hóa)."""

    record_no = models.CharField(max_length=20, unique=True)
    kind = models.CharField(
        max_length=20, choices=AnonymizationKind.choices, default=AnonymizationKind.EXPIRED
    )
    request_ref = models.CharField(max_length=100, blank=True)
    performed_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    performed_at = models.DateTimeField(auto_now_add=True)
    worker_count = models.PositiveIntegerField()
    note = models.TextField(blank=True)

    def __str__(self):
        return self.record_no


class AnonymizationItem(models.Model):
    record = models.ForeignKey(AnonymizationRecord, on_delete=models.PROTECT, related_name="items")
    worker = models.OneToOneField(
        Worker, on_delete=models.PROTECT, related_name="anonymization_item"
    )
    worker_code = models.CharField(max_length=20)
    employee_code = models.CharField(max_length=20, blank=True)
    retention_basis = models.CharField(max_length=20, choices=RetentionBasis.choices)
    retention_expired_on = models.DateField()

    def __str__(self):
        return self.worker_code
