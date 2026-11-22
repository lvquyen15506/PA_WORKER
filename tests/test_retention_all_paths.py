"""Mọi hồ sơ Lưu trữ đều tính được ngày hết hạn, qua MỌI đường vào Lưu trữ (câu 2, models.md 4.6).

Các đường: chuyển tay từ Nháp / Cần bổ sung / Bị từ chối / Đã xác minh (có và không có mã NV,
có và không có ngày nghỉ); 4 quy tắc tự Lưu trữ; mở lại rồi Lưu trữ lại; dữ liệu mẫu seed_demo.
"""

import datetime
import io

import pytest
from django.core.management import call_command
from django.db.models import Q

from apps.core.choices import RetentionBasis as RB
from apps.core.choices import VerificationStatus as VS
from apps.workers import jobs
from apps.workers.models import Worker
from apps.workers.retention import retention_info
from apps.workers.workflow import transition
from tests.factories import (
    at,
    freeze_time,
    make_application,
    make_employment,
    make_user,
    make_worker_full,
    make_worker_in_status,
)

pytestmark = pytest.mark.django_db
D = datetime.date
NOW = at(2026, 11, 22, 12, 0)
TODAY = D(2026, 11, 22)
MANAGER_REASON = "Đã đóng hồ sơ"


def code(worker):
    Worker.objects.filter(pk=worker.pk).update(employee_code=f"CN-T{worker.pk:05d}")
    worker.refresh_from_db()


def resign(worker, resign_date):
    emp = make_employment(worker, "RESIGNED")
    emp.resign_date, emp.resign_reason = resign_date, "SELF"
    emp.save()


def archive_by_hand(worker):
    manager = make_user("HR_MANAGER")
    transition(worker, VS.ARCHIVED, manager, MANAGER_REASON)


def path_manual_draft():
    w = make_worker_in_status(VS.DRAFT)
    transition(w, VS.ARCHIVED, w.created_by)
    return w, RB.CANDIDATE_OTHER


def path_manual_needs_info():
    w = make_worker_in_status(VS.NEEDS_INFO)
    transition(w, VS.ARCHIVED, w.created_by)
    return w, RB.CANDIDATE_OTHER


def path_manual_rejected():
    w = make_worker_in_status(VS.REJECTED)
    transition(w, VS.ARCHIVED, w.created_by)
    return w, RB.REJECTED


def path_manual_verified_candidate():
    w = make_worker_in_status(VS.VERIFIED)
    archive_by_hand(w)
    return w, RB.CANDIDATE_OTHER


def path_manual_verified_candidate_failed():
    w = make_worker_in_status(VS.VERIFIED)
    make_application(w, "DECLINED", result_date=D(2026, 9, 1))
    archive_by_hand(w)
    return w, RB.FAILED_CANDIDATE


def path_manual_verified_employee_no_resign_date():
    w = make_worker_in_status(VS.VERIFIED)
    code(w)
    make_employment(w, "SUSPENDED")
    archive_by_hand(w)
    return w, RB.EMPLOYEE_OTHER


def path_manual_verified_employee_resigned():
    w = make_worker_in_status(VS.VERIFIED)
    code(w)
    resign(w, D(2026, 10, 1))
    archive_by_hand(w)
    return w, RB.RESIGNED


def path_manual_verified_employee_without_employment_row():
    w = make_worker_in_status(VS.VERIFIED)
    code(w)  # có mã NV nhưng chưa có dòng Employment (dữ liệu nhập dở)
    archive_by_hand(w)
    return w, RB.EMPLOYEE_OTHER


def path_auto_rule_1_resigned():
    w = make_worker_full()
    code(w)
    resign(w, TODAY - datetime.timedelta(days=45))
    assert jobs.auto_archive(now=NOW) == 1
    return w, RB.RESIGNED


def path_auto_rule_2_failed():
    w = make_worker_full()
    make_application(w, "FAILED", result_date=TODAY - datetime.timedelta(days=45))
    assert jobs.auto_archive(now=NOW) == 1
    return w, RB.FAILED_CANDIDATE


def path_auto_rule_3_rejected():
    with freeze_time(at(2026, 9, 1)):
        w = make_worker_in_status(VS.REJECTED)
    assert jobs.auto_archive(now=NOW) == 1
    return w, RB.REJECTED


def path_auto_rule_4_abandoned():
    with freeze_time(at(2025, 12, 1)):
        w = make_worker_full()
    assert jobs.auto_archive(now=NOW) == 1
    return w, RB.ABANDONED


def path_auto_rule_4_abandoned_needs_info():
    with freeze_time(at(2025, 12, 1)):
        w = make_worker_in_status(VS.NEEDS_INFO)
    assert jobs.auto_archive(now=NOW) == 1
    return w, RB.ABANDONED


def path_reopen_then_archive_again():
    w = make_worker_in_status(VS.ARCHIVED)
    transition(w, VS.DRAFT, w.created_by)
    make_application(w, "NEW")
    transition(w, VS.ARCHIVED, w.created_by)
    return w, RB.CANDIDATE_OTHER


def path_reopen_then_auto_archive():
    w = make_worker_in_status(VS.ARCHIVED)
    transition(w, VS.DRAFT, w.created_by)
    make_application(w, "DECLINED", result_date=TODAY - datetime.timedelta(days=50))
    assert jobs.auto_archive(now=NOW) == 1
    return w, RB.FAILED_CANDIDATE


PATHS = [
    path_manual_draft,
    path_manual_needs_info,
    path_manual_rejected,
    path_manual_verified_candidate,
    path_manual_verified_candidate_failed,
    path_manual_verified_employee_no_resign_date,
    path_manual_verified_employee_resigned,
    path_manual_verified_employee_without_employment_row,
    path_auto_rule_1_resigned,
    path_auto_rule_2_failed,
    path_auto_rule_3_rejected,
    path_auto_rule_4_abandoned,
    path_auto_rule_4_abandoned_needs_info,
    path_reopen_then_archive_again,
    path_reopen_then_auto_archive,
]


@pytest.mark.parametrize("build", PATHS, ids=[p.__name__ for p in PATHS])
def test_moi_duong_vao_luu_tru_deu_tinh_duoc_ngay_het_han(build):
    worker, expected_basis = build()
    worker.refresh_from_db()
    assert worker.verification_status == VS.ARCHIVED
    info = retention_info(worker)
    assert info.expires_on is not None
    assert info.basis == expected_basis
    assert info.expires_on > D(2026, 1, 1)


def test_du_6_can_cu_deu_xuat_hien_trong_cac_duong_di():
    # Bảo đảm bộ đường đi phủ đủ 6 căn cứ (không bỏ sót căn cứ nào).
    seen = {build()[1] for build in PATHS}
    assert seen == set(RB)


def test_quet_toan_bo_ho_so_luu_tru_trong_csdl():
    for build in PATHS:
        build()
    archived = Worker.objects.filter(verification_status=VS.ARCHIVED)
    assert archived.count() >= len(PATHS)
    for worker in archived:
        info = retention_info(worker)
        assert info.expires_on and info.basis in RB.values


def test_du_lieu_mau_seed_demo_moi_ho_so_luu_tru_deu_tinh_duoc():
    call_command("seed_demo", "--count", "120", stdout=io.StringIO())
    archived = Worker.objects.filter(verification_status=VS.ARCHIVED)
    assert archived.exists()
    bases = set()
    for worker in archived:
        info = retention_info(worker)
        assert info.expires_on is not None, worker.worker_code
        bases.add(info.basis)
    assert bases, "seed_demo không có hồ sơ Lưu trữ nào"
    # Mọi hồ sơ Lưu trữ có đúng một lần chuyển gần nhất sang Lưu trữ trong lịch sử.
    assert not archived.exclude(Q(status_changes__to_status=VS.ARCHIVED)).exists()
