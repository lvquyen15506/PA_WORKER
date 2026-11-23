"""Lưu cài đặt hệ thống từ trang Cài đặt; mọi thay đổi ghi nhật ký (trang.md mục 5.2).

Chỉ Admin (kiểm tra ở view bằng role_required và lại ở đây với các hàm ghi)."""

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.audit.services import log
from apps.core.choices import AuditAction, RoleCode
from apps.core.models import DocumentType, QrFormat, SystemSetting

from .catalogs import MSG_SYSTEM_TYPE, similar_client_companies
from .models import ClientCompany

SETTING_FIELDS = ("ocr_confidence_threshold", "external_ocr_enabled", "external_ocr_url")
QR_FIELDS = ("is_active", "separator", "date_format", "field_order")
CODE_FIELDS = (
    "worker_code_prefix",
    "worker_code_use_year",
    "worker_code_digits",
    "employee_code_prefix",
    "employee_code_use_year",
    "employee_code_digits",
)
THRESHOLD_FIELDS = (
    "expiry_warning_days",
    "assignment_limit_months",
    "failed_retention_months",
    "resigned_retention_years",
    "auto_archive_resigned_days",
    "auto_archive_failed_days",
    "stale_draft_months",
    "intake_ttl_hours",
)


class CatalogError(Exception):
    """Thao tác danh mục không thực hiện được; thông báo tiếng Việt."""


def _require_admin(user):
    if user is None or getattr(user, "role", None) is None or user.role.code != RoleCode.ADMIN:
        raise PermissionDenied


@transaction.atomic
def save_catalog(user, form, *, request=None):
    """Lưu form danh mục đã hợp lệ (thêm hoặc sửa), ghi nhật ký CREATE/UPDATE.

    Trả (đối tượng, danh sách công ty khách nghi trùng khi bỏ dấu) — cảnh báo, không chặn."""
    _require_admin(user)
    instance = form.instance
    adding = instance.pk is None
    fields = form.catalog.fields
    # Giá trị cũ đọc lại từ CSDL: form.is_valid() đã gán giá trị mới vào form.instance.
    stored = None if adding else type(instance).objects.select_for_update().get(pk=instance.pk)
    before = {} if adding else {name: getattr(stored, name) for name in fields}
    obj = form.save()
    if adding:
        changes = {name: (None, getattr(obj, name)) for name in fields}
        log(
            AuditAction.CREATE,
            user=user,
            obj=obj,
            changes=changes,
            note="Thêm danh mục",
            request=request,
        )
    else:
        changes = {
            name: (before[name], getattr(obj, name))
            for name in fields
            if before[name] != getattr(obj, name)
        }
        if changes:
            log(
                AuditAction.UPDATE,
                user=user,
                obj=obj,
                changes=changes,
                note="Sửa danh mục",
                request=request,
            )
    similar = (
        similar_client_companies(obj.name, exclude_pk=obj.pk)
        if isinstance(obj, ClientCompany)
        else []
    )
    return obj, similar


@transaction.atomic
def set_catalog_active(user, obj, active, *, request=None):
    """Ngừng sử dụng / dùng lại một mục danh mục (không có xóa). Ghi nhật ký UPDATE."""
    _require_admin(user)
    obj = type(obj).objects.select_for_update().get(pk=obj.pk)
    if obj.is_active == active:
        return obj
    if not active and isinstance(obj, DocumentType) and obj.system_code:
        raise CatalogError(MSG_SYSTEM_TYPE)
    obj.is_active = active
    obj.save(update_fields=["is_active"])
    log(
        AuditAction.UPDATE,
        user=user,
        obj=obj,
        changes={"is_active": (not active, active)},
        note="Dùng lại danh mục" if active else "Ngừng sử dụng danh mục",
        request=request,
    )
    return obj


@transaction.atomic
def _save_setting_fields(user, values, note, request):
    _require_admin(user)
    system = SystemSetting.objects.select_for_update().get(pk=1)
    changes = _diff(system, values)
    if not changes:
        return {}
    for name, (_, new) in changes.items():
        setattr(system, name, new)
    system.updated_by = user
    system.save()
    log(AuditAction.UPDATE, user=user, obj=system, changes=changes, note=note, request=request)
    return changes


def save_code_rules(user, cleaned, *, request=None):
    """Quy tắc sinh mã: chỉ ảnh hưởng mã cấp sau đó; mã đã cấp giữ nguyên."""
    values = {name: cleaned[name] for name in CODE_FIELDS}
    return _save_setting_fields(user, values, "Cập nhật quy tắc sinh mã", request)


def save_thresholds(user, cleaned, *, request=None):
    values = {name: cleaned[name] for name in THRESHOLD_FIELDS}
    return _save_setting_fields(user, values, "Cập nhật ngưỡng và thời hạn", request)


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
