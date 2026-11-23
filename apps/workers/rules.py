"""Ma trận sửa hồ sơ theo trạng thái (docs/thiet-ke/models.md mục 4.4).

Kiểm tra ở máy chủ: view và service gọi các hàm ở đây; ẩn nút trên giao diện chỉ là phần phụ.
Hồ sơ đã ẩn danh hóa thì không ai sửa được gì. Viewer không có quyền nào ở đây.
"""

from apps.core.choices import RoleCode, VerificationStatus

# Vai trò được tính theo mã (chuỗi), so với user.role.code.
ALL_STAFF = frozenset({RoleCode.HR_STAFF.value, RoleCode.HR_MANAGER.value, RoleCode.ADMIN.value})
MANAGERS = frozenset({RoleCode.HR_MANAGER.value, RoleCode.ADMIN.value})

EDIT_PROFILE = "edit_profile"  # thông tin cá nhân, giấy tờ, liên hệ, đồng ý
ADD_DOCUMENT = "add_document"
REPLACE_DOCUMENT = "replace_document"
VERIFY_DOCUMENT = "verify_document"  # đổi trạng thái xác minh của tài liệu (câu 34)

_VS = VerificationStatus
_OPEN_FOR_STAFF = {
    EDIT_PROFILE: ALL_STAFF,
    ADD_DOCUMENT: ALL_STAFF,
    REPLACE_DOCUMENT: ALL_STAFF,
    VERIFY_DOCUMENT: MANAGERS,
}

# Trạng thái -> thao tác -> vai trò được làm. Thiếu = không ai được (Bị từ chối và Lưu trữ chỉ xem).
MATRIX = {
    _VS.DRAFT: _OPEN_FOR_STAFF,
    _VS.NEEDS_INFO: _OPEN_FOR_STAFF,
    # Chờ duyệt: khóa phần được duyệt (câu 36); QL, Admin vẫn đổi xác minh tài liệu.
    _VS.PENDING: {VERIFY_DOCUMENT: MANAGERS},
    # Đã xác minh: sửa định danh thì tự về Chờ duyệt (workflow).
    # HR thêm được tài liệu nhưng không thay thế (câu 10).
    _VS.VERIFIED: {
        EDIT_PROFILE: ALL_STAFF,
        ADD_DOCUMENT: ALL_STAFF,
        REPLACE_DOCUMENT: MANAGERS,
        VERIFY_DOCUMENT: MANAGERS,
    },
    _VS.REJECTED: {},
    _VS.ARCHIVED: {},
}


def role_code(user):
    """Mã vai trò của người dùng; None nếu chưa đăng nhập."""
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return user.role.code


def can(user, worker, action):
    code = role_code(user)
    if code is None or worker.anonymized_at is not None:
        return False
    allowed = MATRIX.get(VerificationStatus(worker.verification_status), {}).get(action, ())
    return code in allowed


def can_edit_work_tabs(user, worker):
    """Tab Tuyển dụng và Quá trình làm việc thao tác được ở mọi trạng thái trừ Bị từ chối và Lưu trữ
    (câu 36); vai trò A, Q, H; hồ sơ đã ẩn danh hóa thì không ai sửa. Viewer không có quyền nào."""
    code = role_code(user)
    if code not in ALL_STAFF or worker.anonymized_at is not None:
        return False
    return worker.verification_status not in (
        VerificationStatus.REJECTED,
        VerificationStatus.ARCHIVED,
    )


def can_edit_profile(user, worker):
    return can(user, worker, EDIT_PROFILE)


def can_add_document(user, worker):
    return can(user, worker, ADD_DOCUMENT)


def can_replace_document(user, worker):
    return can(user, worker, REPLACE_DOCUMENT)


def can_verify_document(user, worker):
    return can(user, worker, VERIFY_DOCUMENT)
