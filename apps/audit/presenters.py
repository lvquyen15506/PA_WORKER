"""Dựng dòng "trước/sau" của nhật ký để hiển thị (câu 11, 30), dùng chung cho tab Lịch sử của hồ sơ
(`/ho-so/<id>/lich-su/chi-tiet/`) và trang Nhật ký (`/nhat-ky/<id>/`).

- Trường không cá nhân: giá trị trước/sau nằm ngay trong `AuditLog.changes`.
- Trường cá nhân: giá trị giải mã từ `AuditPersonalValue`; số định danh, CMND cũ LUÔN dạng che.
- Hồ sơ đã ẩn danh hóa: các giá trị cá nhân đã bị xóa nên hiện "(đã ẩn danh)".
Chỉ Admin và Quản lý nhân sự được gọi (view kiểm tra vai trò).
"""

from apps.core.text import mask_id_number
from apps.workers import history_labels

MASKED_FIELDS = {"identity.id_number", "identity.old_id_number"}
ANONYMIZED = "(đã ẩn danh)"


def change_rows(entry):
    """[{field, old, new}] cho một dòng nhật ký (mỗi trường thay đổi một dòng; không có thay đổi
    thì danh sách rỗng). Dùng `entry.personal_values` (nên prefetch) và `entry.worker`."""
    worker = entry.worker
    anonymized = bool(worker and worker.anonymized_at)
    saved_values = {p.field_name: p for p in entry.personal_values.all()}
    rows = []
    for field_name, value in (entry.changes or {}).items():
        if isinstance(value, list):  # trường không cá nhân
            old, new = value
        else:  # trường cá nhân
            saved = saved_values.get(field_name)
            if saved is None:
                old = new = ANONYMIZED if anonymized else None
            else:
                old, new = saved.old_value_enc, saved.new_value_enc
                if field_name in MASKED_FIELDS:
                    old, new = mask_id_number(old) or None, mask_id_number(new) or None
        rows.append(
            {
                "field": history_labels.field_label(field_name, entry.object_type),
                "old": history_labels.value_label(field_name, entry.object_type, old),
                "new": history_labels.value_label(field_name, entry.object_type, new),
            }
        )
    return rows


def actor_name(entry):
    """Người thực hiện: họ tên, thiếu thì tên tài khoản; dòng của hệ thống hiện "Hệ thống"."""
    if entry.user:
        return entry.user.full_name or entry.user.username
    return entry.actor_label


# Dòng đổi trạng thái ghi TRƯỚC Phase 7 còn lý do do người dùng gõ ở `note` (từ Phase 7 lý do đó ở
# AuditPersonalValue). Bảng nhật ký chỉ thêm và có trigger chặn sửa nên không xóa được tại CSDL:
# với hồ sơ đã ẩn danh hóa, các dòng cũ đó được che khi hiển thị. Cài mới không có dòng kiểu cũ.
_OLD_REASON_ACTIONS = {"STATUS_CHANGE", "REOPEN"}
_SYSTEM_REASON_PREFIX = "Sửa trường định danh:"


def display_note(entry):
    """Ghi chú để hiển thị (che lý do người gõ ở dòng cũ của hồ sơ đã ẩn danh hóa)."""
    note = entry.note
    worker = entry.worker
    if (
        note
        and worker is not None
        and worker.anonymized_at is not None
        and entry.action in _OLD_REASON_ACTIONS
        and entry.user_id is not None
        and "status_reason" not in (entry.changes or {})
        and not note.startswith(_SYSTEM_REASON_PREFIX)
    ):
        return ANONYMIZED
    return note


def field_labels(entry):
    """Tên các trường thay đổi (tiếng Việt), không kèm giá trị: cho cột "Trường thay đổi"."""
    return [history_labels.field_label(name, entry.object_type) for name in (entry.changes or {})]
