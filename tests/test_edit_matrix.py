"""Ma trận sửa theo trạng thái (models.md mục 4.4): 6 trạng thái × 4 vai trò × 4 thao tác.

Bảng kỳ vọng viết độc lập với apps/workers/rules.py.
"""

import pytest
from django.utils import timezone

from apps.core.choices import VerificationStatus as VS
from apps.workers import rules
from apps.workers.models import Worker
from tests.factories import make_user, make_worker_in_status

pytestmark = pytest.mark.django_db

ADMIN, MGR, HR, VIEWER = "ADMIN", "HR_MANAGER", "HR_STAFF", "VIEWER"
STAFF = {ADMIN, MGR, HR}
MANAGERS = {ADMIN, MGR}

ACTIONS = {
    "edit": rules.can_edit_profile,
    "add": rules.can_add_document,
    "replace": rules.can_replace_document,
    "verify": rules.can_verify_document,
}

# trạng thái -> thao tác -> vai trò được làm (thiếu = không ai)
EXPECTED = {
    VS.DRAFT: {"edit": STAFF, "add": STAFF, "replace": STAFF, "verify": MANAGERS},
    VS.NEEDS_INFO: {"edit": STAFF, "add": STAFF, "replace": STAFF, "verify": MANAGERS},
    VS.PENDING: {"verify": MANAGERS},
    VS.VERIFIED: {"edit": STAFF, "add": STAFF, "replace": MANAGERS, "verify": MANAGERS},
    VS.REJECTED: {},
    VS.ARCHIVED: {},
}


@pytest.mark.parametrize("action", list(ACTIONS))
@pytest.mark.parametrize("role", [ADMIN, MGR, HR, VIEWER])
@pytest.mark.parametrize("status", list(VS))
def test_ma_tran_sua_theo_trang_thai(status, role, action):
    worker = make_worker_in_status(status)
    allowed = EXPECTED[status].get(action, set())
    assert ACTIONS[action](make_user(role), worker) is (role in allowed)


@pytest.mark.parametrize("action", list(ACTIONS))
@pytest.mark.parametrize("status", list(VS))
def test_ho_so_da_an_danh_khong_ai_sua_duoc(status, action):
    worker = make_worker_in_status(status)
    Worker.objects.filter(pk=worker.pk).update(anonymized_at=timezone.now())
    worker.refresh_from_db()
    for role in (ADMIN, MGR, HR, VIEWER):
        assert ACTIONS[action](make_user(role), worker) is False


@pytest.mark.parametrize("action", list(ACTIONS))
def test_chua_dang_nhap_khong_co_quyen_nao(action):
    from django.contrib.auth.models import AnonymousUser

    worker = make_worker_in_status(VS.DRAFT)
    assert ACTIONS[action](AnonymousUser(), worker) is False
    assert ACTIONS[action](None, worker) is False


def test_hr_them_duoc_nhung_khong_thay_the_khi_da_xac_minh_cau_10():
    worker = make_worker_in_status(VS.VERIFIED)
    hr = make_user(HR)
    assert rules.can_add_document(hr, worker) is True
    assert rules.can_replace_document(hr, worker) is False


def test_cho_duyet_chi_khoa_phan_duoc_duyet_ql_van_xac_minh_tai_lieu():
    worker = make_worker_in_status(VS.PENDING)
    manager = make_user(MGR)
    assert rules.can_verify_document(manager, worker) is True
    assert rules.can_edit_profile(manager, worker) is False
    assert rules.can_add_document(manager, worker) is False
