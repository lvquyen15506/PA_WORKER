"""Nhãn trạng thái: ánh xạ giá trị -> (nhãn, màu), viết MỘT chỗ (skill pa-ui mục 5).

- Bốn bộ trạng thái lấy nhãn từ TextChoices trong choices.py; giá trị của bốn bộ không trùng nhau
  nên tra theo mã là đủ.
- Chỉ số tự tính (Thiếu giấy tờ, Hoàn thiện, Sắp hết hạn) và nhãn hiển thị (tài khoản, danh mục,
  đăng nhập) KHÔNG phải bộ trạng thái nghiệp vụ được lưu, nên không có TextChoices riêng.
"""

from .choices import (
    DocumentVerificationStatus as Doc,
)
from .choices import (
    RecruitmentStatus as Rec,
)
from .choices import (
    VerificationStatus as Ver,
)
from .choices import (
    WorkStatus as Work,
)

SUCCESS, BLUE, WARNING, DANGER, MUTED = "success", "blue", "warning", "danger", "muted"

# Mã chỉ số tự tính (không lưu)
MISSING_DOCS = "missing_docs"
COMPLETE = "complete"
EXPIRING = "expiring"

# Nhãn hiển thị (không phải bộ trạng thái)
ACCOUNT_ACTIVE = "account_active"
ACCOUNT_LOCKED = "account_locked"
ACCOUNT_TEMP_LOCKED = "account_temp_locked"
CATALOG_ACTIVE = "catalog_active"
CATALOG_STOPPED = "catalog_stopped"
LOGIN_OK = "login_ok"
LOGIN_FAILED = "login_failed"

_STATUS_COLORS = {
    SUCCESS: [Ver.VERIFIED, Doc.MATCHED, Rec.PASSED, Work.ACTIVE],
    BLUE: [Ver.PENDING, Rec.NEW, Rec.SCREENING, Rec.INTERVIEW, Work.PROBATION, Work.AWAITING],
    WARNING: [Ver.NEEDS_INFO, Work.SUSPENDED],
    DANGER: [Ver.REJECTED, Rec.FAILED, Doc.INVALID],
    MUTED: [Ver.DRAFT, Ver.ARCHIVED, Work.RESIGNED, Rec.DECLINED, Doc.UNVERIFIED],
}

# mã -> (nhãn, màu) cho bốn bộ trạng thái
STATUS_BADGES = {m.value: (m.label, color) for color, ms in _STATUS_COLORS.items() for m in ms}

# mã -> (nhãn, màu) cho chỉ số tự tính và nhãn hiển thị
DERIVED_BADGES = {
    MISSING_DOCS: ("Thiếu giấy tờ", WARNING),
    COMPLETE: ("Hoàn thiện", SUCCESS),
    EXPIRING: ("Sắp hết hạn", WARNING),
    ACCOUNT_ACTIVE: ("Đang hoạt động", SUCCESS),
    ACCOUNT_LOCKED: ("Bị khóa", DANGER),
    ACCOUNT_TEMP_LOCKED: ("Khóa tạm", WARNING),
    CATALOG_ACTIVE: ("Đang dùng", SUCCESS),
    CATALOG_STOPPED: ("Ngừng", MUTED),
    LOGIN_OK: ("Thành công", SUCCESS),
    LOGIN_FAILED: ("Thất bại", DANGER),
}

ALL_BADGES = {**STATUS_BADGES, **DERIVED_BADGES}


def lookup(value):
    """Trả (nhãn, màu) cho một mã; mã lạ -> (chuỗi gốc, xám) để trang không vỡ."""
    key = getattr(value, "value", value)
    if key in ALL_BADGES:
        return ALL_BADGES[key]
    return (str(value) if value not in (None, "") else "—"), MUTED


# Hiển thị khóa của tài khoản: ('ok'|'admin'|'temp') -> mã nhãn
ACCOUNT_LOCK_BADGE = {"ok": ACCOUNT_ACTIVE, "admin": ACCOUNT_LOCKED, "temp": ACCOUNT_TEMP_LOCKED}
