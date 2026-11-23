"""seed_demo: 4 tài khoản, danh mục, ~500 hồ sơ giả đúng quy tắc (Phase 2 bước 7)."""

import datetime
import io
from collections import Counter

import pytest
from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.core.crypto import compute_id_hash
from apps.core.models import CodeSequence, Department, Section
from apps.core.text import compute_name_search
from apps.documents.models import WorkerDocument
from apps.employment.models import Contract, Employment, EmploymentHistory
from apps.recruitment.models import Application
from apps.workers.models import IdentityDocument, StatusChange, Worker

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()


def seed(*args):
    out = io.StringIO()
    call_command("seed_demo", *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def seeded():
    out = seed()
    return out


# --- tài khoản và mật khẩu tạm -------------------------------------------------------------
def test_bon_tai_khoan_mat_khau_tam_ngau_nhien_in_mot_lan(seeded):
    users = {u.username: u for u in User.objects.select_related("role")}
    assert set(users) == {"admin", "quanly", "hr", "viewer"}
    assert {u.role.code for u in users.values()} == {"ADMIN", "HR_MANAGER", "HR_STAFF", "VIEWER"}
    assert all(u.must_change_password for u in users.values())  # có ít nhất 1 Quản lý nhân sự
    passwords = {}
    for line in seeded.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] in users:
            passwords[parts[0]] = parts[1]
    assert set(passwords) == set(users)
    assert len(set(passwords.values())) == 4  # mỗi tài khoản một mật khẩu riêng
    for name, temp in passwords.items():
        assert users[name].check_password(temp)
        assert temp not in users[name].password  # chỉ lưu băm
        assert temp not in str(users[name].password)
    # Không lọt vào nhật ký (mọi cột) hay bất kỳ bảng nào có chữ.
    for entry in AuditLog.objects.all():
        text = f"{entry.note}{entry.changes}{entry.object_repr}{entry.actor_label}"
        assert not any(temp in text for temp in passwords.values())


def test_chay_lai_khong_nhan_doi_khong_doi_mat_khau_va_reset_in_lai(seeded):
    before = {u.username: u.password for u in User.objects.all()}
    counts = (
        Worker.objects.count(),
        IdentityDocument.objects.count(),
        StatusChange.objects.count(),
    )
    second = seed()
    assert "không tạo thêm" in second
    assert "MẬT KHẨU TẠM" not in second and "giữ nguyên mật khẩu" in second
    assert counts == (
        Worker.objects.count(),
        IdentityDocument.objects.count(),
        StatusChange.objects.count(),
    )
    assert before == {u.username: u.password for u in User.objects.all()}
    third = seed("--reset-passwords")
    assert third.count("\n  ") == 4  # in lại 4 mật khẩu mới
    assert before != {u.username: u.password for u in User.objects.all()}
    assert all(User.objects.get(username=u).must_change_password for u in before)


# --- hồ sơ, định danh, băm -----------------------------------------------------------------
def test_500_ho_so_cccd_gia_bat_dau_999_ma_hoa_va_bam_dung(seeded):
    assert Worker.objects.count() == 500
    idents = list(IdentityDocument.objects.select_related("worker"))
    assert len(idents) == 500
    numbers = [i.id_number_enc for i in idents]
    assert all(n.startswith("999") and len(n) == 12 and n.isdigit() for n in numbers)
    assert len(set(numbers)) == 500
    # name_search và id_number_hash tính bằng đúng hàm của save(), không rỗng
    for i in idents:
        assert i.worker.name_search and i.worker.name_search == compute_name_search(
            i.worker.full_name
        )
        assert i.id_number_hash == compute_id_hash(i.id_number_enc)
    # tìm theo băm ra đúng một hồ sơ
    sample = idents[123]
    found = IdentityDocument.objects.filter(id_number_hash=compute_id_hash(sample.id_number_enc))
    assert [f.worker_id for f in found] == [sample.worker_id]
    # cột mã hóa trong CSDL không chứa số rõ
    with connection.cursor() as cur:
        cur.execute("SELECT id_number_enc, permanent_address_enc FROM workers_identitydocument")
        for enc, addr in cur.fetchall():
            assert enc.startswith("gAAAA") and addr.startswith("gAAAA")
    assert all(not w.anonymized_at for w in Worker.objects.all())
    assert WorkerDocument.objects.count() == 0  # Phase 2 không tạo tệp


def test_ma_ho_so_ma_nhan_vien_va_bo_dem(seeded):
    codes = list(Worker.objects.values_list("worker_code", flat=True))
    assert len(set(codes)) == 500
    employees = list(
        Worker.objects.exclude(employee_code=None).values_list("employee_code", flat=True)
    )
    assert len(employees) == len(set(employees)) == Employment.objects.count()
    assert CodeSequence.objects.get(code_type="WORKER").last_number == 500
    assert CodeSequence.objects.get(code_type="EMPLOYEE").last_number == len(employees)


def test_danh_muc_khoi_van_phong_va_nhan_vien_van_phong(seeded):
    dep = Department.objects.get(name="Khối văn phòng")
    assert Section.objects.filter(department=dep, name="Văn phòng").exists()
    assert Employment.objects.filter(section__name="Văn phòng").exists()
    for emp in Employment.objects.select_related("team", "section"):
        assert emp.team is None or emp.team.section_id == emp.section_id  # tổ thuộc bộ phận


def test_ly_do_va_nhat_ky_khong_chua_ho_ten(seeded):
    names = [w.full_name for w in Worker.objects.all()]
    reasons = " | ".join(StatusChange.objects.exclude(reason="").values_list("reason", flat=True))
    logs = " | ".join(f"{a.note}{a.object_repr}" for a in AuditLog.objects.all())
    for name in names:
        assert name not in reasons and name not in logs
    assert "seed_demo" in logs
    assert AuditLog.objects.filter(object_type="core.SeedDemo").count() == 1


# --- trải đều trạng thái, ngày tháng đúng thứ tự -------------------------------------------
def test_du_cac_bo_trang_thai(seeded):
    assert set(Worker.objects.values_list("verification_status", flat=True)) == {
        "DRAFT",
        "PENDING",
        "NEEDS_INFO",
        "VERIFIED",
        "REJECTED",
        "ARCHIVED",
    }
    assert set(Employment.objects.values_list("work_status", flat=True)) == {
        "AWAITING",
        "PROBATION",
        "ACTIVE",
        "SUSPENDED",
        "RESIGNED",
    }
    assert set(Application.objects.values_list("status", flat=True)) == {
        "NEW",
        "SCREENING",
        "INTERVIEW",
        "PASSED",
        "FAILED",
        "DECLINED",
    }


def test_lich_su_trang_thai_lien_mach_dung_thu_tu_va_nguoi_duyet(seeded):
    by_worker = {}
    for sc in StatusChange.objects.order_by("changed_at", "id"):
        by_worker.setdefault(sc.worker_id, []).append(sc)
    workers = {w.pk: w for w in Worker.objects.all()}
    assert set(by_worker) == set(workers)
    for pk, chain in by_worker.items():
        w = workers[pk]
        assert chain[0].from_status == "" and chain[0].to_status == "DRAFT"
        assert chain[0].changed_at > w.created_at  # tạo < mọi thay đổi
        for a, b in zip(chain, chain[1:], strict=False):
            assert b.from_status == a.to_status and b.changed_at > a.changed_at
        assert chain[-1].to_status == w.verification_status
        assert w.updated_at >= w.created_at
        submitter = None
        for sc in chain:
            if sc.to_status == "PENDING":
                submitter = sc.changed_by
            if sc.from_status == "PENDING":  # duyệt / trả lại / từ chối: không tự duyệt
                assert sc.changed_by not in (None, w.created_by, submitter)
            if sc.to_status == "ARCHIVED" and sc.changed_by is None:
                assert sc.reason  # tự động Lưu trữ luôn có lý do


def test_ngay_ung_tuyen_lam_viec_hop_dong_dung_thu_tu_logic(seeded):
    for app in Application.objects.select_related("worker"):
        assert app.applied_date >= timezone.localtime(app.worker.created_at).date()
        if app.result_date:
            assert app.result_date > app.applied_date
        assert (app.status == "FAILED") == bool(app.reject_reason)
    for emp in Employment.objects.select_related("application"):
        assert emp.received_date >= emp.application.result_date
        assert emp.start_date >= emp.received_date
        assert emp.received_date <= TODAY
        assert (emp.work_status == "RESIGNED") == (emp.resign_date is not None)
        if emp.resign_date:
            assert emp.resign_date > emp.start_date and emp.resign_date <= TODAY
            assert emp.resign_reason
        if emp.start_date > TODAY:
            assert emp.work_status == "AWAITING"
    for wid, rows in _group(EmploymentHistory.objects.order_by("effective_date", "id")).items():
        assert rows[0].change_type == "ONBOARD" and rows[0].from_work_status == ""
        status = rows[0].to_work_status
        for r in rows[1:]:
            if r.change_type == "STATUS_CHANGE":
                assert r.from_work_status == status
                status = r.to_work_status
        assert Employment.objects.get(worker_id=wid).work_status == status
    for c in Contract.objects.all():
        assert c.signed_date <= c.effective_date
        assert c.expiry_date is None or c.expiry_date > c.effective_date
        c.clean()


def _group(qs):
    out = {}
    for row in qs:
        out.setdefault(row.worker_id, []).append(row)
    return out


def test_ngay_tre_deu_18_thang_va_moi_thang_trong_12_thang_co_du_lieu(seeded):
    oldest = min(timezone.localtime(w.created_at).date() for w in Worker.objects.all())
    assert TODAY - oldest <= datetime.timedelta(days=548)

    def month_start(back):
        y, m = TODAY.year, TODAY.month - back
        while m <= 0:
            y, m = y - 1, m + 12
        return datetime.date(y, m, 1)

    for back in range(12):
        lo = month_start(back)
        hi = month_start(back - 1) if back else TODAY + datetime.timedelta(days=1)
        created = Worker.objects.filter(created_at__date__gte=lo, created_at__date__lt=hi).count()
        started = Employment.objects.filter(start_date__gte=lo, start_date__lt=hi).count()
        resigned = Employment.objects.filter(resign_date__gte=lo, resign_date__lt=hi).count()
        assert created >= 1, f"không có hồ sơ tạo trong tháng {lo}"
        assert started >= 1, f"không có người vào làm trong tháng {lo}"
        assert resigned >= 0


def test_hop_dong_va_cccd_sap_het_han_co_du_lieu(seeded):
    soon = TODAY + datetime.timedelta(days=30)
    assert Contract.objects.filter(expiry_date__gte=TODAY, expiry_date__lte=soon).count() >= 1
    assert (
        IdentityDocument.objects.filter(expiry_date__gte=TODAY, expiry_date__lte=soon).count() >= 1
    )
    # 18 tuổi: có người dưới 18 (nhóm tuổi Dưới 18), không ai dưới 15
    youngest = max(w.date_of_birth for w in Worker.objects.all())
    assert TODAY.year - youngest.year >= 15
    assert any((TODAY - w.date_of_birth).days < 18 * 365 for w in Worker.objects.all())


def test_ho_so_luu_tru_du_6_can_cu_va_khop_quy_tac_tu_luu_tru(seeded):
    archived = Worker.objects.filter(verification_status="ARCHIVED")
    emp = {e.worker_id: e for e in Employment.objects.all()}
    last_app = {}
    for a in Application.objects.order_by("applied_date", "id"):
        last_app[a.worker_id] = a
    chains = _group(StatusChange.objects.order_by("changed_at", "id"))
    basis = Counter()
    for w in archived:
        e, a, chain = emp.get(w.pk), last_app[w.pk], chains[w.pk]
        reasons = " ".join(c.reason for c in chain)
        if e and e.resign_date:
            basis["RESIGNED"] += 1
        elif e:
            basis["EMPLOYEE_OTHER"] += 1
        elif a.status in ("FAILED", "DECLINED") and a.result_date:
            basis["FAILED_CANDIDATE"] += 1
        elif any(c.to_status == "REJECTED" for c in chain):
            basis["REJECTED"] += 1
        elif "bỏ dở" in reasons:
            basis["ABANDONED"] += 1
        else:
            basis["CANDIDATE_OTHER"] += 1
    assert set(basis) == {
        "RESIGNED",
        "EMPLOYEE_OTHER",
        "FAILED_CANDIDATE",
        "REJECTED",
        "ABANDONED",
        "CANDIDATE_OTHER",
    }
    # Dữ liệu khớp 4 quy tắc tự Lưu trữ: không hồ sơ nào đáng lẽ đã bị Lưu trữ mà vẫn chưa
    limit = TODAY - datetime.timedelta(days=30)
    for w in Worker.objects.exclude(verification_status="ARCHIVED").exclude(
        verification_status="PENDING"
    ):
        e, a = emp.get(w.pk), last_app[w.pk]
        working = e and e.work_status in ("PROBATION", "ACTIVE")
        if working:
            continue
        if e and e.resign_date:
            assert e.resign_date > limit, w.worker_code
        if not e and a.status in ("FAILED", "DECLINED"):
            assert a.result_date > limit, w.worker_code
        if w.verification_status == "REJECTED":
            rejected_at = [c for c in chains[w.pk] if c.to_status == "REJECTED"][-1].changed_at
            assert rejected_at.date() > limit, w.worker_code
        if w.verification_status in ("DRAFT", "NEEDS_INFO"):
            assert (TODAY - timezone.localtime(w.updated_at).date()).days < 183, w.worker_code


# --- v1.1: công ty khách, đợt làm việc, lương, bộ phận không bắt buộc -----------------------------
def test_v11_cong_ty_khach_dot_lam_viec_va_luong_hop_le(seeded):
    from apps.core.models import ClientCompany
    from apps.employment.models import SalaryHistory, WorkAssignment

    names = Counter(ClientCompany.objects.values_list("name", flat=True))
    assert len(names) >= 4 and any(n >= 2 for n in names.values())  # có tên ở nhiều địa điểm
    assignments = list(WorkAssignment.objects.select_related("worker"))
    assert len(assignments) > 200
    open_per_worker = Counter(a.worker_id for a in assignments if a.end_date is None)
    assert max(open_per_worker.values()) == 1  # mỗi công nhân tối đa một đợt đang mở
    by_worker = {}
    for a in assignments:
        assert a.end_date is None or a.end_date >= a.start_date
        by_worker.setdefault(a.worker_id, []).append(a)
    for rows in by_worker.values():  # không chồng lấn ngày
        rows.sort(key=lambda a: a.start_date)
        for first, second in zip(rows, rows[1:], strict=False):
            assert first.end_date is not None and first.end_date < second.start_date
    emp_status = {e.worker_id: e.work_status for e in Employment.objects.all()}
    assert all(emp_status[w] != "AWAITING" for w in by_worker)  # chưa nhận việc thì chưa có đợt
    salaries = list(SalaryHistory.objects.select_related("assignment"))
    assert len(salaries) >= len(assignments) * 0.9
    for s in salaries:  # lương nằm trong khoảng đợt, cùng hồ sơ với đợt
        a = s.assignment
        assert s.worker_id == a.worker_id and s.effective_date >= a.start_date
        assert a.end_date is None or s.effective_date <= a.end_date
        assert s.monthly_salary >= 5_500_000


def test_v11_luong_ma_hoa_trong_csdl_va_nhat_ky_khong_chua_so_luong(seeded):
    from apps.employment.models import SalaryHistory

    with connection.cursor() as cur:
        cur.execute(
            "SELECT monthly_salary_enc, client_unit_price_enc FROM employment_salaryhistory"
        )
        for monthly, price in cur.fetchall():
            assert monthly.startswith("gAAAA") and (price is None or price.startswith("gAAAA"))
    assert SalaryHistory.objects.exists()
    logs = " | ".join(f"{a.note}{a.changes}{a.object_repr}" for a in AuditLog.objects.all())
    assert "salary" not in logs.lower()  # seed không ghi nhật ký giá trị lương


def test_v11_co_cong_nhan_khong_bo_phan_va_dot_sap_du_12_thang(seeded):
    from apps.workers import indicators

    assert Employment.objects.filter(section__isnull=True).exists()
    assert not Employment.objects.filter(team__isnull=False, section__isnull=True).exists()
    due = indicators.assignment_due_info()
    assert len(due) >= 3  # đủ dữ liệu cho thẻ việc cần làm và bộ lọc ở Phase 7
