"""retention_info: 6 căn cứ hạn lưu trữ (lam-ro-yeu-cau.md câu 2) và danh sách chờ hủy."""

import datetime

import pytest
from django.utils import timezone

from apps.core.choices import RetentionBasis as RB
from apps.core.choices import VerificationStatus as VS
from apps.core.models import SystemSetting
from apps.workers.models import Worker
from apps.workers.retention import (
    ABANDONED_REASON,
    RetentionError,
    expired_entries,
    expired_queryset,
    retention_info,
)
from apps.workers.workflow import Trigger, transition
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


def archive_manual(worker, when, user=None):
    with freeze_time(when):
        transition(worker, VS.ARCHIVED, user or worker.created_by)
    worker.refresh_from_db()
    return worker


def archive_by_system(worker, when, reason):
    with freeze_time(when):
        transition(worker, VS.ARCHIVED, None, reason, trigger=Trigger.SYSTEM)
    worker.refresh_from_db()
    return worker


def employee(worker, code="CN-00001"):
    Worker.objects.filter(pk=worker.pk).update(employee_code=code)
    worker.refresh_from_db()
    return worker


def resigned(worker, resign_date):
    emp = make_employment(worker, "RESIGNED")
    emp.resign_date = resign_date
    emp.resign_reason = "SELF"
    emp.save()


# ----- 6 căn cứ ---------------------------------------------------------------------------
def test_can_cu_1_cong_nhan_da_nghi_10_nam_tu_ngay_nghi():
    worker = employee(make_worker_full())
    resigned(worker, D(2020, 6, 15))
    archive_manual(worker, at(2021, 1, 10))
    assert retention_info(worker) == (RB.RESIGNED, D(2030, 6, 15))


def test_can_cu_2_cong_nhan_khong_co_ngay_nghi_10_nam_tu_ngay_luu_tru():
    worker = employee(make_worker_full())
    archive_manual(worker, at(2026, 3, 1))
    assert retention_info(worker) == (RB.EMPLOYEE_OTHER, D(2036, 3, 1))


@pytest.mark.parametrize("status", ["FAILED", "DECLINED"])
def test_can_cu_3_ung_vien_khong_duoc_tuyen_12_thang_tu_ngay_co_ket_qua(status):
    worker = make_worker_full()
    make_application(worker, status, result_date=D(2026, 1, 31))
    archive_manual(worker, at(2026, 6, 1))
    assert retention_info(worker) == (RB.FAILED_CANDIDATE, D(2027, 1, 31))


def test_can_cu_4_ho_so_bi_tu_choi_12_thang_tu_ngay_luu_tru():
    worker = make_worker_in_status(VS.REJECTED)
    archive_manual(worker, at(2026, 2, 28))
    assert retention_info(worker) == (RB.REJECTED, D(2027, 2, 28))


def test_can_cu_5_ho_so_bo_do_12_thang_tu_ngay_luu_tru():
    worker = make_worker_full()
    archive_by_system(worker, at(2026, 3, 15), f"{ABANDONED_REASON} (hồ sơ {worker.worker_code})")
    assert retention_info(worker) == (RB.ABANDONED, D(2027, 3, 15))


def test_can_cu_6_ung_vien_luu_tru_khac_12_thang_tu_ngay_luu_tru():
    worker = make_worker_full()
    archive_manual(worker, at(2026, 3, 15))
    assert retention_info(worker) == (RB.CANDIDATE_OTHER, D(2027, 3, 15))


# ----- thứ tự ưu tiên ---------------------------------------------------------------------
def test_co_ma_nv_thi_can_cu_cong_nhan_di_truoc_du_co_ung_tuyen_khong_dat():
    worker = employee(make_worker_full())
    make_application(worker, "FAILED", result_date=D(2026, 1, 1))
    archive_manual(worker, at(2026, 3, 1))
    assert retention_info(worker).basis == RB.EMPLOYEE_OTHER


def test_khong_dat_di_truoc_bi_tu_choi():
    worker = make_worker_in_status(VS.REJECTED)
    make_application(worker, "FAILED", result_date=D(2026, 1, 31))
    archive_manual(worker, at(2026, 6, 1))
    assert retention_info(worker) == (RB.FAILED_CANDIDATE, D(2027, 1, 31))


def test_bi_tu_choi_di_truoc_bo_do():
    worker = make_worker_in_status(VS.REJECTED)
    archive_by_system(worker, at(2026, 6, 1), f"{ABANDONED_REASON} (hồ sơ x)")
    assert retention_info(worker).basis == RB.REJECTED


def test_chi_xet_lan_ung_tuyen_gan_nhat():
    worker = make_worker_full()
    make_application(worker, "FAILED", result_date=D(2025, 1, 1), applied_date=D(2025, 1, 1))
    make_application(worker, "INTERVIEW", applied_date=D(2026, 2, 1))  # mới hơn, chưa có kết quả
    archive_manual(worker, at(2026, 3, 1))
    assert retention_info(worker) == (RB.CANDIDATE_OTHER, D(2027, 3, 1))


def test_khong_dat_ma_thieu_ngay_ket_qua_roi_xuong_can_cu_sau():
    worker = make_worker_full()
    make_application(worker, "FAILED", result_date=None)
    archive_manual(worker, at(2026, 3, 1))
    assert retention_info(worker).basis == RB.CANDIDATE_OTHER


def test_nguoi_dung_go_tay_chu_bo_do_khong_tinh_la_bo_do():
    worker = make_worker_full()
    with freeze_time(at(2026, 3, 1)):
        transition(worker, VS.ARCHIVED, worker.created_by, ABANDONED_REASON)
    assert retention_info(worker).basis == RB.CANDIDATE_OTHER


def test_ngay_chuyen_luu_tru_tinh_theo_gio_viet_nam():
    # 18:30 UTC ngày 28/02 = 01:30 ngày 01/03 giờ Việt Nam.
    worker = make_worker_full()
    when = datetime.datetime(2026, 2, 28, 18, 30, tzinfo=datetime.UTC)
    archive_manual(worker, when)
    assert retention_info(worker).expires_on == D(2027, 3, 1)


def test_mo_lai_roi_luu_tru_lai_lay_lan_gan_nhat():
    worker = make_worker_full()
    archive_manual(worker, at(2025, 1, 10))
    with freeze_time(at(2025, 6, 1)):
        transition(worker, VS.DRAFT, worker.created_by)
    archive_manual(worker, at(2026, 4, 20))
    assert retention_info(worker) == (RB.CANDIDATE_OTHER, D(2027, 4, 20))


# ----- cấu hình ---------------------------------------------------------------------------
def test_doi_cau_hinh_thoi_han():
    setting = SystemSetting.load()
    setting.failed_retention_months = 6
    setting.resigned_retention_years = 5
    setting.save()
    a = make_worker_full()
    archive_manual(a, at(2026, 3, 1))
    b = employee(make_worker_full(), "CN-00002")
    archive_manual(b, at(2026, 3, 1))
    assert retention_info(a).expires_on == D(2026, 9, 1)
    assert retention_info(b).expires_on == D(2031, 3, 1)


# ----- lỗi --------------------------------------------------------------------------------
@pytest.mark.parametrize("status", [VS.DRAFT, VS.PENDING, VS.NEEDS_INFO, VS.VERIFIED, VS.REJECTED])
def test_ho_so_chua_luu_tru_bao_loi(status):
    worker = make_worker_in_status(status)
    with pytest.raises(RetentionError):
        retention_info(worker)


def test_luu_tru_ma_khong_co_lich_su_chuyen_bao_loi():
    from apps.workers.models import StatusChange

    worker = make_worker_in_status(VS.ARCHIVED)
    # Mô phỏng dữ liệu hỏng: xóa lịch sử bằng SQL thô (ORM chặn xóa bảng chỉ-thêm).
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute("DELETE FROM workers_statuschange WHERE worker_id = %s", [worker.pk])
    assert not StatusChange.objects.filter(worker=worker).exists()
    with pytest.raises(RetentionError, match="lịch sử"):
        retention_info(worker)


# ----- danh sách chờ hủy -------------------------------------------------------------------
def archived_with_expiry(expires_on):
    """Hồ sơ ứng viên Lưu trữ có ngày hết hạn đúng bằng expires_on (12 tháng từ ngày lưu trữ)."""
    start = D(expires_on.year - 1, expires_on.month, min(expires_on.day, 28))
    worker = make_worker_full()
    archive_manual(worker, at(start.year, start.month, start.day))
    assert retention_info(worker).expires_on == expires_on
    return worker


def test_chi_hon_ngay_het_han_moi_vao_danh_sach_cho_huy():
    today = D(2026, 11, 22)
    on_day = archived_with_expiry(D(2026, 11, 22))  # hết hạn đúng hôm nay: còn lưu
    yesterday = archived_with_expiry(D(2026, 11, 21))  # quá hạn từ hôm qua
    future = archived_with_expiry(D(2026, 11, 23))
    pks = [w.pk for w, _ in expired_entries(today)]
    assert pks == [yesterday.pk]
    assert on_day.pk not in pks and future.pk not in pks


def test_danh_sach_cho_huy_sap_theo_ngay_het_han_va_co_can_cu():
    first = archived_with_expiry(D(2026, 1, 5))
    second = archived_with_expiry(D(2026, 3, 5))
    entries = expired_entries(D(2026, 11, 22))
    assert [w.pk for w, _ in entries] == [first.pk, second.pk]
    assert {info.basis for _, info in entries} == {RB.CANDIDATE_OTHER}
    assert list(expired_queryset(D(2026, 11, 22)).order_by("pk")) == [first, second]


def test_danh_sach_cho_huy_bo_ho_so_da_an_danh_va_chua_luu_tru():
    old = archived_with_expiry(D(2026, 1, 5))
    anonymized = archived_with_expiry(D(2026, 1, 6))
    Worker.objects.filter(pk=anonymized.pk).update(anonymized_at=timezone.now())
    make_worker_in_status(VS.VERIFIED)
    make_worker_in_status(VS.DRAFT)
    assert [w.pk for w, _ in expired_entries(D(2026, 11, 22))] == [old.pk]


def test_cho_huy_khong_phai_trang_thai_ho_so_van_la_luu_tru():
    worker = archived_with_expiry(D(2026, 1, 5))
    assert expired_entries(D(2026, 11, 22))
    worker.refresh_from_db()
    assert worker.verification_status == VS.ARCHIVED
