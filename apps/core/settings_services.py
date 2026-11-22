"""Lưu cài đặt hệ thống từ trang Cài đặt; mọi thay đổi ghi nhật ký (trang.md mục 5.2)."""

from django.db import transaction

from apps.audit.services import log
from apps.core.choices import AuditAction
from apps.core.models import QrFormat, SystemSetting

SETTING_FIELDS = ("ocr_confidence_threshold", "external_ocr_enabled", "external_ocr_url")
QR_FIELDS = ("is_active", "separator", "date_format", "field_order")


def _diff(instance, values):
    """{tên trường: (giá trị cũ, giá trị mới)} của các trường thực sự đổi."""
    return {
        name: (getattr(instance, name), value)
        for name, value in values.items()
        if getattr(instance, name) != value
    }


@transaction.atomic
def save_ocr_qr(user, form, *, request=None):
    """Lưu form OCR và QR đã hợp lệ. Mỗi đối tượng có thay đổi ghi một dòng nhật ký UPDATE (giá
    trị cũ/mới). Trả danh sách mô tả đối tượng đã đổi (rỗng nếu không có gì đổi)."""
    changed = []
    system = SystemSetting.objects.select_for_update().get(pk=1)
    changes = _diff(system, {name: form.cleaned_data[name] for name in SETTING_FIELDS})
    if changes:
        for name, (_, new) in changes.items():
            setattr(system, name, new)
        system.updated_by = user
        system.save()
        log(
            AuditAction.UPDATE,
            user=user,
            obj=system,
            changes=changes,
            note="Cập nhật cài đặt OCR",
            request=request,
        )
        changed.append("system")
    for qr_format in QrFormat.objects.select_for_update().filter(
        pk__in=[f.pk for f in form.qr_formats]
    ):
        changes = _diff(qr_format, form.format_values(qr_format))
        if not changes:
            continue
        for name, (_, new) in changes.items():
            setattr(qr_format, name, new)
        qr_format.save()
        log(
            AuditAction.UPDATE,
            user=user,
            obj=qr_format,
            changes=changes,
            note="Cập nhật cấu hình QR",
            request=request,
        )
        changed.append(qr_format.id_doc_type)
    return changed
