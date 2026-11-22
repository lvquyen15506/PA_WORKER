"""Tự Lưu trữ hằng ngày: 4 quy tắc của câu 9 (lam-ro-yeu-cau.md), ranh giới và loại trừ."""

import datetime

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.core.choices import VerificationStatus as VS
from apps.core.models import SystemSetting
from apps.workers import jobs
from apps.workers.models import StatusChange, Worker
from apps.workers.retention import ABANDONED_REASON
from tests.factories import (
    at,
    freeze_time,
    make_application,
    make_employment,
    make_worker_full,
    make_worker_in_status,
)

pytestmark = pytest.mark.django_db
D = datetime.date
NOW = at(2026, 11, 22, 12, 0)
TODAY = D(2026, 11, 22)


def status_of(worker):
    return Worker.objects.get(pk=worker.pk).verification_status


def with_employee_code(worker, code):
    Worker.objects.filter(pk=worker.pk).update(employee_code=code)
    return worker


def resigned(worker, resign_date, work_status="RESIGNED"):
    emp = make_employment(worker, work_status)
    emp.resign_date = resign_date
    emp.resign_reason = "SELF"
    emp.save()
    return emp


def run():
    return jobs.auto_archive(now=NOW)


# ----- Quy tắc 1: đã nghỉ việc quá 30 ngày ---------------------------------------------------
@pytest.mark.parametrize("status", [VS.DRAFT, VS.NEEDS_INFO, VS.VERIFIED])
def test_quy_tac_1_nghi_viec_ranh_gioi_30_chua_31_chuyen(status):
    on_limit = make_worker_in_status(status)
    over = make_worker_in_status(status)
    for w, days in ((on_limit, 30), (over, 31)):
        with_employee_code(w, f"CN-{w.pk:05d}")
        resigned(w, TODAY - datetime.timedelta(days=days))
    assert run() == 1
    assert status_of(on_limit) == status
    assert status_of(over) == VS.ARCHIVED


def test_quy_tac_1_chi_khi_trang_thai_lam_viec_la_da_nghi():
    worker = with_employee_code(make_worker_full(), "CN-00001")
    resigned(worker, TODAY - datetime.timedelta(days=400), work_status="SUSPENDED")
    assert run() == 0
    assert status_of(worker) == VS.DRAFT


def test_quy_tac_1_doi_so_ngay_trong_cai_dat():
    setting = SystemSetting.load()
    setting.auto_archive_resigned_days = 10
    setting.save()
    worker = with_employee_code(make_worker_full(), "CN-00001")
    resigned(worker, TODAY - datetime.timedelta(days=11))
    assert run() == 1


# ----- Quy tắc 2: ứng viên không đạt / từ chối quá 30 ngày ------------------------------------
@pytest.mark.parametrize("app_status", ["FAILED", "DECLINED"])
def test_quy_tac_2_ranh_gioi_30_chua_31_chuyen(app_status):
    on_limit = make_worker_full()
    over = make_worker_full()
    make_application(on_limit, app_status, result_date=TODAY - datetime.timedelta(days=30))
    make_application(over, app_status, result_date=TODAY - datetime.timedelta(days=31))
    assert run() == 1
    assert status_of(on_limit) == VS.DRAFT
    assert status_of(over) == VS.ARCHIVED


@pytest.mark.parametrize("status", [VS.DRAFT, VS.NEEDS_INFO, VS.VERIFIED])
def test_quy_tac_2_ap_dung_cho_nhap_can_bo_sung_da_xac_minh(status):
    worker = make_worker_in_status(status)
    make_application(worker, "FAILED", result_date=TODAY - datetime.timedelta(days=60))
    assert run() == 1
    assert status_of(worker) == VS.ARCHIVED


def test_quy_tac_2_chi_xet_lan_ung_tuyen_gan_nhat():
    worker = make_worker_full()
    make_application(
        worker,
        "FAILED",
        result_date=TODAY - datetime.timedelta(days=90),
        applied_date=D(2026, 5, 1),
    )
    make_application(worker, "SCREENING", applied_date=D(2026, 10, 1))  # lần mới đang xử lý
    assert run() == 0
    assert status_of(worker) == VS.DRAFT


def test_quy_tac_2_khong_ap_dung_khi_da_co_ma_nv_hoac_thieu_ngay_ket_qua():
    employed = with_employee_code(make_worker_full(), "CN-00001")
    make_application(employed, "FAILED", result_date=TODAY - datetime.timedelta(days=90))
    no_date = make_worker_full()
    make_application(no_date, "FAILED", result_date=None)
    assert run() == 0


# ----- Quy tắc 3: bị từ chối quá 30 ngày -----------------------------------------------------
def test_quy_tac_3_bi_tu_choi_ranh_gioi_30_chua_31_chuyen():
    with freeze_time(at(2026, 10, 23)):  # 30 ngày trước NOW
        on_limit = make_worker_in_status(VS.REJECTED)
    with freeze_time(at(2026, 10, 22)):  # 31 ngày trước
        over = make_worker_in_status(VS.REJECTED)
    assert run() == 1
    assert status_of(on_limit) == VS.REJECTED
    assert status_of(over) == VS.ARCHIVED


def test_quy_tac_3_dung_chung_so_ngay_voi_quy_tac_2():
    setting = SystemSetting.load()
    setting.auto_archive_failed_days = 5
    setting.save()
    with freeze_time(at(2026, 11, 16)):
        worker = make_worker_in_status(VS.REJECTED)
    assert run() == 1
    assert status_of(worker) == VS.ARCHIVED


# ----- Quy tắc 4: Nháp / Cần bổ sung bỏ dở 6 tháng --------------------------------------------
@pytest.mark.parametrize("status", [VS.DRAFT, VS.NEEDS_INFO])
def test_quy_tac_4_bo_do_6_thang_ranh_gioi(status):
    # NOW = 22/11/2026: mốc = 22/05/2026. Cập nhật 22/05 chưa quá hạn; 21/05 thì quá.
    with freeze_time(at(2026, 5, 22)):
        on_limit = make_worker_in_status(status)
    with freeze_time(at(2026, 5, 21)):
        over = make_worker_in_status(status)
    assert run() == 1
    assert status_of(on_limit) == status
    assert status_of(over) == VS.ARCHIVED
    change = StatusChange.objects.filter(worker=over, to_status=VS.ARCHIVED).get()
    assert change.changed_by is None
    assert change.reason == f"{ABANDONED_REASON} (hồ sơ {over.worker_code})"


def test_quy_tac_4_co_thay_doi_du_lieu_con_thi_khong_bo_do():
    with freeze_time(at(2026, 1, 1)):
        worker = make_worker_full()
    with freeze_time(at(2026, 11, 1)):
        worker.touch()  # có người thêm/sửa dữ liệu con của hồ sơ
    assert run() == 0
    assert status_of(worker) == VS.DRAFT


def test_quy_tac_4_khong_ap_dung_cho_da_xac_minh_hay_cho_duyet():
    with freeze_time(at(2025, 1, 1)):
        verified = make_worker_in_status(VS.VERIFIED)
        pending = make_worker_in_status(VS.PENDING)
    assert run() == 0
    assert status_of(verified) == VS.VERIFIED and status_of(pending) == VS.PENDING


def test_quy_tac_4_doi_so_thang_trong_cai_dat():
    setting = SystemSetting.load()
    setting.stale_draft_months = 1
    setting.save()
    with freeze_time(at(2026, 10, 21)):
        worker = make_worker_full()
    assert run() == 1
    assert status_of(worker) == VS.ARCHIVED


# ----- Loại trừ chung -------------------------------------------------------------------------
@pytest.mark.parametrize("work", ["PROBATION", "ACTIVE"])
def test_khong_ap_dung_khi_thu_viec_hoac_dang_lam_viec_du_hoi_nhap_tu_excel(work):
    with freeze_time(at(2025, 1, 1)):
        stale_draft = make_worker_full()
    make_employment(stale_draft, work)
    verified = make_worker_in_status(VS.VERIFIED)
    with_employee_code(verified, "CN-00002")
    make_employment(verified, work)
    make_application(verified, "FAILED", result_date=D(2025, 1, 1))
    assert run() == 0
    assert status_of(stale_draft) == VS.DRAFT and status_of(verified) == VS.VERIFIED


@pytest.mark.parametrize("work", ["AWAITING", "SUSPENDED"])
def test_van_ap_dung_khi_cho_nhan_viec_hoac_tam_hoan(work):
    with freeze_time(at(2025, 1, 1)):
        worker = make_worker_full()
    make_employment(worker, work)
    assert run() == 1


def test_khong_bao_gio_ap_dung_cho_cho_duyet():
    worker = make_worker_in_status(VS.PENDING)
    with_employee_code(worker, "CN-00001")
    resigned(worker, D(2020, 1, 1))
    make_application(worker, "FAILED", result_date=D(2020, 1, 1))
    assert run() == 0
    assert status_of(worker) == VS.PENDING


def test_khong_dung_ho_so_da_luu_tru_hoac_da_an_danh():
    archived = make_worker_in_status(VS.ARCHIVED)
    make_application(archived, "FAILED", result_date=D(2020, 1, 1))
    anonymized = make_worker_full()
    make_application(anonymized, "FAILED", result_date=D(2020, 1, 1))
    Worker.objects.filter(pk=anonymized.pk).update(anonymized_at=timezone.now())
    logs = AuditLog.objects.count()
    assert run() == 0
    assert AuditLog.objects.count() == logs


# ----- Ghi nhận, idempotent, ưu tiên ----------------------------------------------------------
def test_nguoi_thuc_hien_la_he_thong_va_ly_do_chi_co_ma_ho_so():
    worker = make_worker_full()
    make_application(worker, "FAILED", result_date=TODAY - datetime.timedelta(days=45))
    assert run() == 1
    change = StatusChange.objects.get(worker=worker, to_status=VS.ARCHIVED)
    assert change.changed_by is None and change.from_status == VS.DRAFT
    assert worker.worker_code in change.reason and worker.full_name not in change.reason
    entry = AuditLog.objects.filter(action="STATUS_CHANGE").first()
    assert (entry.user, entry.actor_label) == (None, "Hệ thống")
    assert worker.full_name not in entry.note + entry.object_repr


def test_chay_lai_khong_doi_gi_nua():
    worker = make_worker_full()
    make_application(worker, "FAILED", result_date=TODAY - datetime.timedelta(days=45))
    assert run() == 1
    changes, logs = StatusChange.objects.count(), AuditLog.objects.count()
    assert run() == 0
    assert (StatusChange.objects.count(), AuditLog.objects.count()) == (changes, logs)


def test_quy_tac_dung_truoc_thang_vi_khop_nhieu_quy_tac():
    with freeze_time(at(2025, 1, 1)):  # cũng thỏa quy tắc 4
        worker = make_worker_full()
    make_application(worker, "DECLINED", result_date=TODAY - datetime.timedelta(days=40))
    assert run() == 1
    change = StatusChange.objects.get(worker=worker, to_status=VS.ARCHIVED)
    assert "không đạt hoặc từ chối" in change.reason  # quy tắc 2, không phải "bỏ dở"


def test_loi_o_mot_ho_so_khong_chan_ho_so_khac(monkeypatch):
    bad = make_worker_full()
    good = make_worker_full()
    for w in (bad, good):
        make_application(w, "FAILED", result_date=TODAY - datetime.timedelta(days=45))
    original = jobs.transition

    def flaky(worker, *args, **kwargs):
        if worker.pk == bad.pk:
            raise RuntimeError("hỏng")
        return original(worker, *args, **kwargs)

    monkeypatch.setattr(jobs, "transition", flaky)
    assert run() == 1
    assert status_of(bad) == VS.DRAFT and status_of(good) == VS.ARCHIVED


def test_ho_so_doi_trang_thai_giua_chung_bi_bo_qua_khong_bao_loi(monkeypatch):
    worker = make_worker_full()
    make_application(worker, "FAILED", result_date=TODAY - datetime.timedelta(days=45))
    candidates = jobs._archive_candidates(NOW)
    assert worker.pk in candidates
    # Giữa lúc tính danh sách và lúc chuyển, người dùng đã gửi duyệt hồ sơ.
    from apps.workers.workflow import transition

    transition(worker, VS.PENDING, worker.created_by)
    monkeypatch.setattr(jobs, "_archive_candidates", lambda now: candidates)
    assert run() == 0
    assert status_of(worker) == VS.PENDING


def test_run_daily_jobs_goi_auto_archive():
    worker = make_worker_full()
    make_application(worker, "FAILED", result_date=TODAY - datetime.timedelta(days=45))
    result = jobs.run_daily_jobs(now=NOW)
    assert result["auto_archived"] == 1 and status_of(worker) == VS.ARCHIVED
