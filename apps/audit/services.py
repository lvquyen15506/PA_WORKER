"""Ghi nhật ký thao tác. MỌI nơi ghi nhật ký phải gọi log(); không tạo AuditLog trực tiếp.

Trường cá nhân (PERSONAL_FIELDS) không bao giờ ghi giá trị rõ vào AuditLog.changes: chỉ ghi
"(xem giá trị chi tiết)"; giá trị trước/sau lưu mã hóa ở AuditPersonalValue (câu 30).
"""

import datetime
import decimal

from django.db import transaction

from apps.core.choices import AuditAction

from .models import AuditLog, AuditPersonalValue
from .personal_fields import (
    PERSONAL_FIELDS,
    VIRTUAL_FIELDS,
    attr_name,
    field_label,
    is_personal,
)

PERSONAL_PLACEHOLDER = "(xem giá trị chi tiết)"
SYSTEM_LABEL = "Hệ thống"


def _model_label(obj):
    return f"{obj._meta.app_label}.{obj.__class__.__name__}"


def _text(value):
    """Giá trị -> chuỗi ổn định để lưu (None giữ None)."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return format(value, "f")
    if hasattr(value, "value") and hasattr(value, "label"):  # TextChoices
        return str(value.value)
    return str(value)


def _client_ip(request):
    if request is None:
        return None
    return request.META.get("REMOTE_ADDR") or None


def _resolve_worker(obj, worker):
    if worker is not None:
        return worker
    if obj is None:
        return None
    if _model_label(obj) == "workers.Worker":
        return obj
    return getattr(obj, "worker", None)


@transaction.atomic
def log(
    action,
    *,
    user=None,
    obj=None,
    worker=None,
    changes=None,
    note="",
    request=None,
    object_type=None,
    object_id=None,
    object_repr=None,
):
    """Ghi một dòng nhật ký (và các giá trị cá nhân đi kèm) trong một giao dịch.

    action       một giá trị AuditAction.
    user         người thực hiện; None = "Hệ thống".
    obj          đối tượng bị tác động. object_type/object_id/object_repr suy ra từ obj;
                 object_repr = str(obj), an toàn vì __str__ không chứa dữ liệu cá nhân.
    worker       hồ sơ liên quan; mặc định là obj (nếu là Worker) hoặc obj.worker.
    changes      {tên logic: (giá trị cũ, giá trị mới)} theo tên logic ở personal_fields.py
                 (ví dụ "id_number", không phải "id_number_enc"). Truyền giá trị RÕ.
    note         lý do, bộ lọc khi xuất báo cáo. Không ghi họ tên (dùng mã hồ sơ).
    request      để lấy địa chỉ IP.
    object_*     chỉ dùng cho sự kiện không có obj (xuất báo cáo, đăng nhập...). object_repr
                 phải là mã hoặc tên báo cáo, không phải họ tên, số CCCD, tên tệp gốc.
    """
    if action not in AuditAction.values:
        raise ValueError(f"Hành động nhật ký không hợp lệ: {action!r}")
    if obj is None and not (object_type and object_repr is not None):
        raise ValueError("Cần obj, hoặc cả object_type và object_repr.")

    label = _model_label(obj) if obj is not None else None
    pk = getattr(obj, "pk", None)
    related_worker = _resolve_worker(obj, worker)

    public, personal = {}, []
    for logical, pair in (changes or {}).items():
        old, new = pair
        if label is None:
            raise ValueError("Ghi thay đổi từng trường cần có obj.")
        attr = attr_name(label, logical)
        if logical not in VIRTUAL_FIELDS.get(label, ()):  # trường ảo không có cột trong model
            try:
                obj._meta.get_field(attr)
            except Exception as exc:
                raise ValueError(f"{label} không có trường {logical!r}.") from exc
        name = field_label(label, logical, pk)
        if is_personal(label, logical):
            personal.append((name, _text(old), _text(new)))
            public[name] = PERSONAL_PLACEHOLDER
        else:
            public[name] = [_text(old), _text(new)]

    if personal and related_worker is None:
        raise ValueError("Trường cá nhân phải gắn với một hồ sơ (worker).")

    entry = AuditLog.objects.create(
        user=user if getattr(user, "pk", None) else None,
        actor_label=user.get_username() if getattr(user, "pk", None) else SYSTEM_LABEL,
        action=action,
        object_type=label or object_type,
        object_id=str(pk) if obj is not None else str(object_id or ""),
        object_repr=(str(obj) if obj is not None else object_repr)[:200],
        worker=related_worker,
        changes=public,
        ip_address=_client_ip(request),
        note=note,
    )
    for name, old, new in personal:
        AuditPersonalValue.objects.create(
            audit_log=entry,
            worker=related_worker,
            field_name=name,
            old_value_enc=old,
            new_value_enc=new,
        )
    return entry


__all__ = ["log", "PERSONAL_FIELDS", "PERSONAL_PLACEHOLDER"]
