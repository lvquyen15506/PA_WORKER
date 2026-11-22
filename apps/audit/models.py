"""Nhật ký thao tác (docs/thiet-ke/models.md mục 3.2).

Trường `worker` (FK tới workers.Worker) được thêm ở migration 0003, sau khi model Worker có.
"""

from django.db import models

from apps.core.choices import AuditAction
from apps.core.crypto import EncryptedTextField
from apps.core.models_base import AppendOnlyModel, NoUpdateQuerySet


class AuditLog(AppendOnlyModel):
    """Chỉ thêm: save() lần hai, delete(), update() đều bị chặn; PostgreSQL có trigger."""

    created_at = models.DateTimeField("Thời điểm", auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        verbose_name="Người thực hiện",
    )
    actor_label = models.CharField("Người thực hiện (nhãn)", max_length=150)
    action = models.CharField(
        "Hành động", max_length=30, choices=AuditAction.choices, db_index=True
    )
    object_type = models.CharField("Loại đối tượng", max_length=50)
    object_id = models.CharField("Mã đối tượng", max_length=50)
    # Mã hồ sơ, mã hợp đồng, loại tài liệu, tên báo cáo. KHÔNG chứa họ tên, số CCCD, tên tệp gốc.
    object_repr = models.CharField("Đối tượng", max_length=200)
    # Hồ sơ liên quan, để lọc nhật ký theo hồ sơ.
    worker = models.ForeignKey(
        "workers.Worker",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
        verbose_name="Hồ sơ",
    )
    changes = models.JSONField("Thay đổi", default=dict, blank=True)
    ip_address = models.GenericIPAddressField("Địa chỉ IP", null=True, blank=True)
    note = models.TextField("Ghi chú", blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.action} {self.object_type} {self.object_repr}"


class AuditPersonalValue(AppendOnlyModel):
    """Giá trị trước/sau của trường cá nhân, mã hóa. Không sửa; chỉ bị xóa khi ẩn danh hóa
    hồ sơ (apps.workers.retention.anonymize). PostgreSQL có trigger chặn UPDATE."""

    append_only_allow_delete = True
    objects = NoUpdateQuerySet.as_manager()

    audit_log = models.ForeignKey(
        AuditLog,
        on_delete=models.PROTECT,
        related_name="personal_values",
        verbose_name="Dòng nhật ký",
    )
    # Để xóa theo hồ sơ khi ẩn danh hóa.
    worker = models.ForeignKey(
        "workers.Worker", on_delete=models.PROTECT, related_name="+", db_index=True
    )
    field_name = models.CharField("Tên trường", max_length=80)
    old_value_enc = EncryptedTextField("Giá trị cũ", null=True, blank=True)
    new_value_enc = EncryptedTextField("Giá trị mới", null=True, blank=True)
