"""Không tự duyệt (models.md mục 4.2, câu 8): áp dụng cả với Admin."""

import pytest

from apps.core.choices import VerificationStatus as VS
from apps.workers.models import Worker
from apps.workers.workflow import (
    TransitionError,
    TransitionForbidden,
    Trigger,
    can_review,
    is_own_submission,
    transition,
)
from tests.factories import make_user, make_worker_full, make_worker_in_status

pytestmark = pytest.mark.django_db

OPS = [(VS.VERIFIED, ""), (VS.NEEDS_INFO, "Cần bổ sung ảnh"), (VS.REJECTED, "Giấy tờ sai")]


def pending_worker(scenario, role):
    """Trả (hồ sơ Chờ duyệt, actor). scenario: creator | submitter | both | neither."""
    actor = make_user(role)
    creator = actor if scenario in ("creator", "both") else make_user("HR_STAFF")
    submitter = actor if scenario in ("submitter", "both") else make_user("HR_STAFF")
    worker = make_worker_full(created_by=creator)
    transition(worker, VS.PENDING, submitter)
    return worker, actor


@pytest.mark.parametrize("role", ["ADMIN", "HR_MANAGER"])
@pytest.mark.parametrize("scenario", ["creator", "submitter", "both"])
@pytest.mark.parametrize(("dst", "reason"), OPS)
def test_nguoi_tao_hoac_nguoi_gui_khong_duoc_xu_ly_ke_ca_admin(role, scenario, dst, reason):
    worker, actor = pending_worker(scenario, role)
    with pytest.raises(TransitionForbidden) as exc:
        transition(worker, dst, actor, reason)
    assert "chính mình" in exc.value.message
    assert Worker.objects.get(pk=worker.pk).verification_status == VS.PENDING
    assert is_own_submission(worker, actor) and not can_review(worker, actor)


@pytest.mark.parametrize("role", ["ADMIN", "HR_MANAGER"])
@pytest.mark.parametrize(("dst", "reason"), OPS)
def test_nguoi_khac_duoc_xu_ly(role, dst, reason):
    worker, actor = pending_worker("neither", role)
    assert can_review(worker, actor)
    transition(worker, dst, actor, reason)
    assert Worker.objects.get(pk=worker.pk).verification_status == dst


def test_chan_tu_duyet_la_403_ngay_ca_khi_thieu_ly_do():
    worker, actor = pending_worker("creator", "HR_MANAGER")
    with pytest.raises(TransitionForbidden):
        transition(worker, VS.REJECTED, actor, "")  # 403 trước, không phải "Cần ghi lý do"


def test_xet_nguoi_gui_lan_gan_nhat_khong_phai_lan_dau():
    creator = make_user("HR_STAFF")
    first_submitter = make_user("HR_MANAGER")
    manager = make_user("HR_MANAGER")
    second_submitter = make_user("HR_MANAGER")
    worker = make_worker_full(created_by=creator)
    transition(worker, VS.PENDING, first_submitter)
    transition(worker, VS.NEEDS_INFO, manager, "Bổ sung")
    transition(worker, VS.PENDING, second_submitter)
    # Người gửi lần đầu không còn bị chặn; người gửi lần này bị chặn.
    assert can_review(worker, first_submitter)
    assert not can_review(worker, second_submitter)
    with pytest.raises(TransitionForbidden):
        transition(worker, VS.VERIFIED, second_submitter)
    transition(worker, VS.VERIFIED, first_submitter)


def test_nguoi_tra_lai_duoc_duyet_lan_gui_sau_neu_khong_phai_nguoi_gui():
    creator = make_user("HR_STAFF")
    manager = make_user("HR_MANAGER")
    worker = make_worker_full(created_by=creator)
    transition(worker, VS.PENDING, creator)
    transition(worker, VS.NEEDS_INFO, manager, "Bổ sung")
    transition(worker, VS.PENDING, creator)
    transition(worker, VS.VERIFIED, manager)  # người đã trả lại duyệt tiếp được


def test_nguoi_sua_dinh_danh_tro_thanh_nguoi_gui_va_khong_tu_duyet_duoc():
    worker = make_worker_in_status(VS.VERIFIED)
    editor = make_user("HR_MANAGER")
    other = make_user("HR_MANAGER")
    transition(worker, VS.PENDING, editor, trigger=Trigger.IDENTITY_EDIT)
    assert not can_review(worker, editor)
    with pytest.raises(TransitionForbidden):
        transition(worker, VS.VERIFIED, editor)
    assert can_review(worker, other)
    transition(worker, VS.VERIFIED, other)


def test_nguoi_tao_ho_so_van_bi_chan_du_ho_so_ve_cho_duyet_do_nguoi_khac_sua():
    worker = make_worker_in_status(VS.VERIFIED)  # tạo bởi một HR; QL duyệt
    creator_as_reviewer = make_user("HR_MANAGER")
    # Gán người tạo = quản lý để mô phỏng "QL tự nhập hồ sơ".
    Worker.objects.filter(pk=worker.pk).update(created_by=creator_as_reviewer)
    transition(worker, VS.PENDING, make_user("HR_STAFF"), trigger=Trigger.IDENTITY_EDIT)
    with pytest.raises(TransitionForbidden):
        transition(worker, VS.VERIFIED, creator_as_reviewer)


def test_can_review_chi_dung_voi_ho_so_cho_duyet_va_vai_tro_quan_ly():
    worker, _ = pending_worker("neither", "ADMIN")
    assert not can_review(worker, make_user("HR_STAFF"))
    assert not can_review(worker, make_user("VIEWER"))
    assert not can_review(worker, None)
    other_status = make_worker_in_status(VS.DRAFT)
    assert not can_review(other_status, make_user("HR_MANAGER"))


def test_hr_duyet_la_403_du_la_nguoi_khac():
    worker, _ = pending_worker("neither", "HR_STAFF")
    with pytest.raises(TransitionForbidden):
        transition(worker, VS.VERIFIED, make_user("HR_STAFF"))


def test_tu_duyet_khong_phai_loi_nghiep_vu_thuong():
    worker, actor = pending_worker("both", "ADMIN")
    with pytest.raises(TransitionError) as exc:
        transition(worker, VS.VERIFIED, actor)
    assert isinstance(exc.value, TransitionForbidden)
