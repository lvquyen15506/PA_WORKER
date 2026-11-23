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


def field_labels(entry):
    """Tên các trường thay đổi (tiếng Việt), không kèm giá trị: cho cột "Trường thay đổi"."""
    return [history_labels.field_label(name, entry.object_type) for name in (entry.changes or {})]
