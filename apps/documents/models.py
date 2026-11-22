"""Tài liệu hồ sơ (docs/thiet-ke/models.md mục 3.5)."""

from django.db import models

from apps.core.choices import DocumentVerificationStatus
from apps.core.storage import private_storage


def document_upload_to(instance, filename):
    """Thư mục theo hồ sơ; PrivateStorage đổi tên tệp thành chuỗi ngẫu nhiên."""
    return f"documents/{instance.worker_id}/{filename}"


class WorkerDocument(models.Model):
    worker = models.ForeignKey("workers.Worker", on_delete=models.PROTECT, related_name="documents")
    document_type = models.ForeignKey(
        "core.DocumentType", on_delete=models.PROTECT, related_name="+"
    )
    # Rỗng sau ẩn danh hóa.
    stored_file = models.FileField(
        storage=private_storage, upload_to=document_upload_to, null=True, blank=True
    )
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)  # theo chữ ký tệp thật, không theo đuôi tên
    size_bytes = models.PositiveIntegerField()  # tối đa 10 MB
    version = models.PositiveSmallIntegerField(default=1)
    replaces = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="replaced_by"
    )
    is_current = models.BooleanField(default=True, db_index=True)
    verification_status = models.CharField(
        max_length=20,
        choices=DocumentVerificationStatus.choices,
        default=DocumentVerificationStatus.UNVERIFIED,
    )
    verified_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    uploaded_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at", "-id"]

    def __str__(self):
        return f"{self.worker.worker_code} – {self.document_type} v{self.version}"
