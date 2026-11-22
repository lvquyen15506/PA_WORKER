"""Bảng chuyển trạng thái xác minh (models.md mục 4.1): mọi cặp × mọi vai trò.

Bảng kỳ vọng EXPECTED viết ĐỘC LẬP ở đây (không import TRANSITIONS) để test bắt được lỗi
khi bảng trong code bị sửa sai.
"""

import pytest

from apps.audit.models import AuditLog
from apps.core.choices import VerificationStatus as VS
from apps.workers.models import StatusChange, Worker
from apps.workers.workflow import TransitionError, TransitionForbidden, Trigger, transition
from tests.factories import make_employment, make_user, make_worker_in_status

pytestmark = pytest.mark.django_db

ADMIN, MGR, HR, VIEWER, SYSTEM = "ADMIN", "HR_MANAGER", "HR_STAFF", "VIEWER", "SYSTEM"
STAFF = {ADMIN, MGR, HR}

# (từ, sang) -> tác nhân được phép chuyển THỦ CÔNG hoặc bằng tác vụ hệ thống.
EXPECTED = {
    (VS.DRAFT, VS.PENDING): STAFF,
    (VS.PENDING, VS.VERIFIED): {ADMIN, MGR},
    (VS.PENDING, VS.NEEDS_INFO): {ADMIN, MGR},
    (VS.PENDING, VS.REJECTED): {ADMIN, MGR},
    (VS.NEEDS_INFO, VS.PENDING): STAFF,
    # Đã xác minh -> Chờ duyệt: không có đường thủ công (chỉ khi sửa trường định danh).
    (VS.REJECTED, VS.ARCHIVED): STAFF | {SYSTEM},
    (VS.DRAFT, VS.ARCHIVED): STAFF | {SYSTEM},
    (VS.NEEDS_INFO, VS.ARCHIVED): STAFF | {SYSTEM},
    (VS.VERIFIED, VS.ARCHIVED): {ADMIN, MGR, SYSTEM},
    (VS.ARCHIVED, VS.DRAFT): STAFF,
}

CASES = [(a, b, actor) for a in VS for b in VS for actor in (ADMIN, MGR, HR, VIEWER, SYSTEM)]


def prepare(status):
    """Hồ sơ đủ trường, ở trạng thái `status`, do một HR tạo và gửi duyệt."""
    return make_worker_in_status(status)


def run(worker, to, actor, reason="Lý do thử"):
    if actor == SYSTEM:
        return transition(worker, to, None, reason, trigger=Trigger.SYSTEM)
    user = make_user(actor)  # người mới: khác người tạo, khác người gửi duyệt
    return transition(worker, to, user, reason)


@pytest.mark.parametrize(("src", "dst", "actor"), CASES)
def test_bang_chuyen_trang_thai(src, dst, actor):
    worker = prepare(src)
    assert Worker.objects.get(pk=worker.pk).verification_status == src
    changes_before = StatusChange.objects.count()
    logs_before = AuditLog.objects.count()
    if actor in EXPECTED.get((src, dst), set()):
        change = run(worker, dst, actor)
        worker.refresh_from_db()
        assert worker.verification_status == dst
        assert (change.from_status, change.to_status) == (src, dst)
        assert StatusChange.objects.count() == changes_before + 1
        assert AuditLog.objects.count() == logs_before + 1
        entry = AuditLog.objects.first()
        assert entry.action == (
            "REOPEN" if (src, dst) == (VS.ARCHIVED, VS.DRAFT) else "STATUS_CHANGE"
        )
        assert entry.changes == {"verification_status": [src.value, dst.value]}
        assert entry.object_repr == worker.worker_code
        if actor == SYSTEM:
            assert change.changed_by is None and entry.user is None
            assert entry.actor_label == "Hệ thống"
        else:
            assert change.changed_by.role.code == actor
    else:
        with pytest.raises(TransitionError):
            run(worker, dst, actor)
        worker.refresh_from_db()
        assert worker.verification_status == src
        assert StatusChange.objects.count() == changes_before
        assert AuditLog.objects.count() == logs_before


def test_viewer_bi_tu_choi_moi_chuyen_bang_403():
    worker = prepare(VS.DRAFT)
    with pytest.raises(TransitionForbidden):
        run(worker, VS.PENDING, VIEWER)


def test_cap_khong_co_trong_bang_la_loi_nghiep_vu_khong_phai_403():
    worker = prepare(VS.DRAFT)
    with pytest.raises(TransitionError) as exc:
        run(worker, VS.VERIFIED, ADMIN)
    assert not isinstance(exc.value, TransitionForbidden)
    assert "Không thể chuyển" in exc.value.message


def test_chuyen_sang_chinh_trang_thai_dang_co_bi_tu_choi():
    worker = prepare(VS.DRAFT)
    with pytest.raises(TransitionError):
        run(worker, VS.DRAFT, ADMIN)


def test_sai_vai_tro_la_403():
    worker = prepare(VS.PENDING)
    with pytest.raises(TransitionForbidden):
        run(worker, VS.VERIFIED, HR)


def test_chua_dang_nhap_bi_tu_choi():
    worker = prepare(VS.DRAFT)
    with pytest.raises(TransitionForbidden):
        transition(worker, VS.PENDING, None)


def test_tac_vu_he_thong_khong_duoc_co_nguoi_thuc_hien():
    worker = prepare(VS.DRAFT)
    with pytest.raises(TransitionForbidden):
        transition(worker, VS.ARCHIVED, make_user(ADMIN), trigger=Trigger.SYSTEM)


def test_he_thong_khong_duoc_duyet_hay_gui_duyet():
    for src, dst in [(VS.DRAFT, VS.PENDING), (VS.PENDING, VS.VERIFIED), (VS.ARCHIVED, VS.DRAFT)]:
        worker = prepare(src)
        with pytest.raises(TransitionForbidden):
            transition(worker, dst, None, "x", trigger=Trigger.SYSTEM)


# ----- lý do bắt buộc -------------------------------------------------------------------
@pytest.mark.parametrize("reason", ["", "   ", "\n\t "])
@pytest.mark.parametrize(
    ("src", "dst"),
    [
        (VS.PENDING, VS.NEEDS_INFO),
        (VS.PENDING, VS.REJECTED),
        (VS.VERIFIED, VS.ARCHIVED),
    ],
)
def test_thieu_ly_do_hoac_chi_khoang_trang_bi_chan(src, dst, reason):
    worker = prepare(src)
    with pytest.raises(TransitionError) as exc:
        run(worker, dst, ADMIN, reason=reason)
    assert exc.value.message == "Cần ghi lý do."
    worker.refresh_from_db()
    assert worker.verification_status == src


@pytest.mark.parametrize(
    ("src", "dst", "actor"),
    [
        (VS.DRAFT, VS.PENDING, HR),
        (VS.PENDING, VS.VERIFIED, MGR),
        (VS.NEEDS_INFO, VS.PENDING, HR),
        (VS.REJECTED, VS.ARCHIVED, HR),
        (VS.DRAFT, VS.ARCHIVED, HR),
        (VS.NEEDS_INFO, VS.ARCHIVED, HR),
        (VS.ARCHIVED, VS.DRAFT, HR),
    ],
)
def test_cac_cap_khong_bat_buoc_ly_do_van_chay_khi_de_trong(src, dst, actor):
    worker = prepare(src)
    run(worker, dst, actor, reason="")
    worker.refresh_from_db()
    assert worker.verification_status == dst


def test_ly_do_duoc_cat_khoang_trang_va_luu_o_status_change_va_nhat_ky():
    worker = prepare(VS.PENDING)
    change = run(worker, VS.NEEDS_INFO, MGR, reason="  Bổ sung ảnh CCCD  ")
    assert change.reason == "Bổ sung ảnh CCCD"
    assert AuditLog.objects.first().note == "Bổ sung ảnh CCCD"


# ----- Đã xác minh -> Lưu trữ: chặn khi đang làm việc ----------------------------------
@pytest.mark.parametrize("work", ["PROBATION", "ACTIVE"])
@pytest.mark.parametrize("src", [VS.VERIFIED, VS.DRAFT, VS.NEEDS_INFO, VS.REJECTED])
def test_chan_luu_tru_khi_thu_viec_hoac_dang_lam_viec(src, work):
    worker = prepare(src)
    make_employment(worker, work)
    for actor in (ADMIN, MGR):
        with pytest.raises(TransitionError) as exc:
            run(worker, VS.ARCHIVED, actor)
        assert not isinstance(exc.value, TransitionForbidden)
        assert "Thử việc hoặc Đang làm việc" in exc.value.message
    with pytest.raises(TransitionError):
        transition(worker, VS.ARCHIVED, None, trigger=Trigger.SYSTEM)
    worker.refresh_from_db()
    assert worker.verification_status == src


@pytest.mark.parametrize("work", ["AWAITING", "SUSPENDED", "RESIGNED", None])
def test_cho_luu_tru_khi_cho_nhan_viec_tam_hoan_da_nghi_hoac_chua_co_employment(work):
    worker = prepare(VS.VERIFIED)
    if work:
        make_employment(worker, work)
    run(worker, VS.ARCHIVED, MGR, reason="Đã đóng hồ sơ")
    worker.refresh_from_db()
    assert worker.verification_status == VS.ARCHIVED


def test_hr_khong_luu_tru_ho_so_da_xac_minh_la_403_du_khong_di_lam():
    worker = prepare(VS.VERIFIED)
    with pytest.raises(TransitionForbidden):
        run(worker, VS.ARCHIVED, HR, reason="x")


# ----- Đã xác minh -> Chờ duyệt: chỉ qua IDENTITY_EDIT ----------------------------------
def test_da_xac_minh_ve_cho_duyet_chi_di_qua_sua_truong_dinh_danh():
    worker = prepare(VS.VERIFIED)
    for actor in (ADMIN, MGR, HR):
        with pytest.raises(TransitionForbidden):
            run(worker, VS.PENDING, actor)
    editor = make_user(HR)
    change = transition(
        worker,
        VS.PENDING,
        editor,
        "bỏ qua",
        trigger=Trigger.IDENTITY_EDIT,
        identity_fields=["họ tên"],
    )
    worker.refresh_from_db()
    assert worker.verification_status == VS.PENDING
    assert change.changed_by == editor
    assert change.reason == "Sửa trường định danh: họ tên"  # lý do tự điền, bỏ qua lý do truyền vào


def test_sua_dinh_danh_mac_dinh_ghi_du_ba_truong_va_khong_chua_ho_ten():
    worker = prepare(VS.VERIFIED)
    change = transition(worker, VS.PENDING, make_user(HR), trigger=Trigger.IDENTITY_EDIT)
    assert change.reason == "Sửa trường định danh: họ tên, ngày sinh, số CCCD"
    assert worker.full_name not in change.reason


def test_sua_dinh_danh_viewer_hoac_he_thong_bi_tu_choi():
    worker = prepare(VS.VERIFIED)
    with pytest.raises(TransitionForbidden):
        transition(worker, VS.PENDING, make_user(VIEWER), trigger=Trigger.IDENTITY_EDIT)
    with pytest.raises(TransitionForbidden):
        transition(worker, VS.PENDING, None, trigger=Trigger.SYSTEM)


def test_chi_di_qua_sua_dinh_danh_cho_dung_cap_da_xac_minh_cho_duyet():
    # IDENTITY_EDIT không dùng được để đi các cặp khác.
    worker = prepare(VS.DRAFT)
    with pytest.raises(TransitionForbidden):
        transition(worker, VS.PENDING, make_user(HR), trigger=Trigger.IDENTITY_EDIT)


# ----- Mở lại hồ sơ ---------------------------------------------------------------------
def test_mo_lai_ghi_reopen_va_ve_nhap():
    worker = prepare(VS.ARCHIVED)
    run(worker, VS.DRAFT, HR)
    assert AuditLog.objects.first().action == "REOPEN"
    worker.refresh_from_db()
    assert worker.verification_status == VS.DRAFT


def test_mo_lai_bi_chan_khi_da_an_danh():
    from django.utils import timezone

    worker = prepare(VS.ARCHIVED)
    Worker.objects.filter(pk=worker.pk).update(anonymized_at=timezone.now())
    for actor in (ADMIN, MGR, HR):
        with pytest.raises(TransitionError) as exc:
            run(worker, VS.DRAFT, actor)
        assert "ẩn danh" in exc.value.message
    worker.refresh_from_db()
    assert worker.verification_status == VS.ARCHIVED


# ----- Lý do hệ thống tự điền ------------------------------------------------------------
def test_he_thong_tu_luu_tru_tu_dien_ly_do_chi_co_ma_ho_so():
    worker = prepare(VS.DRAFT)
    change = transition(worker, VS.ARCHIVED, None, trigger=Trigger.SYSTEM)
    assert worker.worker_code in change.reason
    assert worker.full_name not in change.reason
    entry = AuditLog.objects.first()
    assert worker.full_name not in entry.note + entry.object_repr + str(entry.changes)


def test_he_thong_giu_ly_do_cua_tac_vu_neu_co():
    worker = prepare(VS.DRAFT)
    change = transition(worker, VS.ARCHIVED, None, "Hồ sơ bỏ dở", trigger=Trigger.SYSTEM)
    assert change.reason == "Hồ sơ bỏ dở"


# ----- Toàn vẹn --------------------------------------------------------------------------
def test_dong_ho_so_trong_bo_nho_duoc_cap_nhat_sau_khi_chuyen():
    worker = prepare(VS.DRAFT)
    before = worker.updated_at
    transition(worker, VS.PENDING, worker.created_by)
    assert worker.verification_status == VS.PENDING
    assert worker.updated_at > before


def test_chuyen_dua_tren_trang_thai_hien_tai_trong_csdl_khong_theo_doi_tuong_cu():
    # Hai người cầm cùng một hồ sơ: người thứ hai dùng bản cũ (còn Nháp) nhưng CSDL đã Chờ duyệt.
    first = prepare(VS.DRAFT)
    stale = Worker.objects.get(pk=first.pk)
    transition(first, VS.PENDING, first.created_by)
    assert stale.verification_status == VS.DRAFT
    with pytest.raises(TransitionError):
        transition(stale, VS.PENDING, first.created_by)  # Chờ duyệt -> Chờ duyệt
    assert StatusChange.objects.filter(worker=first, to_status=VS.PENDING).count() == 1


def test_loi_giua_chung_hoan_tac_ca_trang_thai_lan_status_change(monkeypatch):
    import apps.workers.workflow as wf

    worker = prepare(VS.DRAFT)
    changes_before = StatusChange.objects.count()

    def boom(*args, **kwargs):
        raise RuntimeError("hỏng nhật ký")

    monkeypatch.setattr(wf, "log", boom)
    with pytest.raises(RuntimeError):
        transition(worker, VS.PENDING, worker.created_by)
    assert Worker.objects.get(pk=worker.pk).verification_status == VS.DRAFT
    assert StatusChange.objects.count() == changes_before


def test_trang_thai_khong_hop_le_bi_tu_choi():
    worker = prepare(VS.DRAFT)
    with pytest.raises(ValueError):
        transition(worker, "NOT_A_STATUS", worker.created_by)
