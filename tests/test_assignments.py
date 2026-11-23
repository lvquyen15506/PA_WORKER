"""Đợt làm việc tại công ty khách và lịch sử lương (v1.1; câu 40–45, 48).

Service: một công ty tại một lúc, không chồng lấn, ngày lương trong khoảng đợt, lương chỉ thêm,
chỉ A và Q thêm lương, đợt tự đóng khi nghỉ việc (tests/test_employment.py), cảnh báo 12 tháng
theo chuỗi cùng TÊN công ty bỏ qua địa điểm, bộ lọc danh sách, hạn lưu trữ không phụ thuộc đợt.
"""

import datetime
import re

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.urls import Resolver404, resolve

from apps.audit.models import AuditLog, AuditPersonalValue
from apps.core.models import ClientCompany, Position, SystemSetting
from apps.employment import assignments as svc
from apps.employment.assignments import AssignmentError
from apps.employment.models import Employment, SalaryHistory, WorkAssignment
from apps.workers import indicators
from apps.workers.models import Worker
from tests.factories import (
    login_client,
    make_employment,
    make_user,
    make_worker,
    make_worker_in_status,
)

pytestmark = pytest.mark.django_db
D = datetime.date
TODAY = datetime.date.today()


def days(n):
    return TODAY + datetime.timedelta(days=n)


def hr():
    return make_user("HR_STAFF")


def manager():
    return make_user("HR_MANAGER")


def employee(status="ACTIVE", verification="DRAFT"):
    worker = make_worker_in_status(verification) if verification != "DRAFT" else make_worker()
    make_employment(worker, status)
    Worker.objects.filter(pk=worker.pk).update(employee_code=f"CN-T{worker.pk:05d}")
    worker.refresh_from_db()
    return worker


def company(name="Công ty Mẫu A", location="Tỉnh Một"):
    return ClientCompany.objects.get_or_create(name=name, location=location)[0]


def position():
    return Position.objects.get_or_create(name="Công nhân lắp ráp")[0]


def add(worker, *, user=None, start, end=None, client=None, **kw):
    return svc.add_assignment(
        user or hr(),
        worker,
        client_company=client or company(),
        position=position(),
        start_date=start,
        end_date=end,
        **kw,
    )


def pay(assignment, *, user=None, amount=8_000_000, price=11_000_000, day=None, reason="Ban đầu"):
    return svc.add_salary(
        user or manager(),
        assignment,
        monthly_salary=amount,
        client_unit_price=price,
        effective_date=day or assignment.start_date,
        reason=reason,
    )


# ----- Mỗi lúc một công ty, không chồng lấn -----
def test_them_dot_dau_tien_ghi_nhat_ky_va_cap_nhat_ho_so():
    worker = employee()
    a = add(worker, start=days(-30), note="Ghi chú đợt")
    assert a.end_date is None and a.created_by.role.code == "HR_STAFF"
    entry = AuditLog.objects.get(action="CREATE", object_type="employment.WorkAssignment")
    assert entry.worker_id == worker.pk and "Ghi chú đợt" not in str(entry.changes)
    assert AuditPersonalValue.objects.filter(field_name=f"work_assignments[{a.pk}].note").exists()


def test_dang_co_dot_mo_thi_phai_nhap_ngay_ket_thuc_dot_cu():
    worker = employee()
    old = add(worker, start=days(-60))
    with pytest.raises(AssignmentError) as exc:
        add(worker, start=days(-10), client=company("Công ty B", "Tỉnh Hai"))
    assert "previous_end_date" in exc.value.errors
    assert WorkAssignment.objects.filter(worker=worker).count() == 1
    new = add(
        worker,
        start=days(-10),
        client=company("Công ty B", "Tỉnh Hai"),
        previous_end_date=days(-11),
    )
    old.refresh_from_db()
    assert old.end_date == days(-11) and new.end_date is None
    assert WorkAssignment.objects.filter(worker=worker, end_date__isnull=True).count() == 1
    closed = AuditLog.objects.filter(
        action="UPDATE",
        object_type="employment.WorkAssignment",
        note__contains="chuyển sang đợt mới",
    )
    assert closed.count() == 1


def test_ngay_ket_thuc_cua_dot_cu_khong_truoc_ngay_bat_dau_cua_no():
    worker = employee()
    add(worker, start=days(-60))
    with pytest.raises(AssignmentError) as exc:
        add(worker, start=days(-10), previous_end_date=days(-90))
    assert "không được trước ngày bắt đầu" in exc.value.errors["previous_end_date"]


@pytest.mark.parametrize(
    ("start", "end", "ok"),
    [
        (-100, -81, True),  # trước hẳn
        (-100, -80, False),  # cùng ngày kết thúc = chồng lấn (ngày cuối tính cả)
        (-79, -50, False),  # nằm trong đợt có sẵn (-80..-40)
        (-90, -60, False),  # gối đầu
        (-70, None, False),  # đợt mở chồng đợt cũ
        (-40, -20, False),  # bắt đầu đúng ngày kết thúc đợt trước = chồng lấn
        (-39, -20, True),  # ngay ngày sau ngày kết thúc: liền nhau, hợp lệ
        (-30, None, True),  # sau hẳn, đang mở
    ],
)
def test_khong_chong_lan_ngay_voi_dot_khac(start, end, ok):
    worker = employee()
    add(worker, start=days(-80), end=days(-40))
    # ghi đợt thứ hai: nếu đang chờ đóng đợt mở thì không có, đợt đầu đã có ngày kết thúc
    args = {"start": days(start), "end": days(end) if end is not None else None}
    if ok:
        add(worker, client=company("Công ty B", "Tỉnh Hai"), **args)
        assert WorkAssignment.objects.filter(worker=worker).count() == 2
    else:
        with pytest.raises(AssignmentError) as exc:
            add(worker, client=company("Công ty B", "Tỉnh Hai"), **args)
        assert "chồng lấn" in exc.value.errors["start_date"]


def test_ngay_ket_thuc_truoc_ngay_bat_dau_va_thieu_ngay_bat_dau_bi_tu_choi():
    worker = employee()
    with pytest.raises(AssignmentError) as exc:
        add(worker, start=days(-10), end=days(-11))
    assert "Ngày kết thúc không được trước ngày bắt đầu." == exc.value.errors["end_date"]
    with pytest.raises(AssignmentError) as exc:
        add(worker, start=None)
    assert exc.value.errors["start_date"] == "Nhập ngày bắt đầu."
    assert not WorkAssignment.objects.exists()


def test_cong_ty_vi_tri_da_ngung_khong_chon_duoc_va_thieu_thi_bao_loi():
    worker = employee()
    stopped = company("Công ty Ngừng", "Tỉnh X")
    ClientCompany.objects.filter(pk=stopped.pk).update(is_active=False)
    stopped.refresh_from_db()
    with pytest.raises(AssignmentError) as exc:
        add(worker, start=days(-5), client=stopped)
    assert exc.value.errors["client_company"] == "Chọn công ty khách hàng đang sử dụng."
    with pytest.raises(AssignmentError) as exc:
        svc.add_assignment(hr(), worker, client_company=None, position=None, start_date=days(-5))
    assert {"client_company", "position"} <= set(exc.value.errors)


def test_chua_tiep_nhan_hoac_da_nghi_viec_thi_khong_them_dot():
    no_employment = make_worker()
    with pytest.raises(AssignmentError, match="tiếp nhận vào làm trước"):
        add(no_employment, start=days(-5))
    resigned = employee("RESIGNED")
    with pytest.raises(AssignmentError, match="đã nghỉ việc"):
        add(resigned, start=days(-5))


@pytest.mark.parametrize("role", ["HR_STAFF", "HR_MANAGER", "ADMIN"])
def test_nhan_vien_them_va_sua_dot_viewer_khong(role):
    worker = employee()
    a = add(worker, user=make_user(role), start=days(-10))
    assert svc.update_assignment(
        make_user(role),
        a,
        client_company=a.client_company,
        position=a.position,
        start_date=a.start_date,
        end_date=days(-1),
    )
    with pytest.raises(PermissionDenied):
        add(worker, user=make_user("VIEWER"), start=days(5))
    with pytest.raises(PermissionDenied):
        svc.add_assignment(
            None, worker, client_company=company(), position=position(), start_date=days(5)
        )


@pytest.mark.parametrize("state", ["REJECTED", "ARCHIVED"])
def test_ho_so_bi_tu_choi_hoac_luu_tru_khoa_dot_va_luong(state):
    worker = make_worker_in_status("VERIFIED")
    make_employment(worker, "ACTIVE")
    a = add(worker, start=days(-10))
    row = pay(a)
    from apps.core.choices import VerificationStatus as VS
    from apps.workers.workflow import transition

    if state == "REJECTED":
        worker2 = make_worker_in_status("REJECTED")
        make_employment(worker2, "ACTIVE")
        locked_assignment = WorkAssignment.objects.create(
            worker=worker2,
            client_company=company(),
            position=position(),
            start_date=days(-5),
            created_by=hr(),
        )
        target_worker, target = worker2, locked_assignment
    else:
        make_employment_resigned = Employment.objects.get(worker=worker)
        Employment.objects.filter(pk=make_employment_resigned.pk).update(
            work_status="RESIGNED", resign_date=days(-3), resign_reason="SELF"
        )
        transition(Worker.objects.get(pk=worker.pk), VS.ARCHIVED, manager(), reason="Đã nghỉ")
        target_worker, target = worker, WorkAssignment.objects.get(pk=a.pk)
    admin = make_user("ADMIN")
    with pytest.raises(PermissionDenied):
        add(target_worker, user=admin, start=days(20))
    with pytest.raises(PermissionDenied):
        svc.update_assignment(
            admin,
            target,
            client_company=target.client_company,
            position=target.position,
            start_date=target.start_date,
        )
    with pytest.raises(PermissionDenied):
        pay(target, user=admin)
    assert row.pk


# ----- Sửa đợt -----
def test_sua_dot_ghi_gia_tri_cu_moi_va_khong_doi_thi_khong_ghi():
    worker = employee()
    a = add(worker, start=days(-30), note="cũ")
    kwargs = {
        "client_company": a.client_company,
        "position": a.position,
        "start_date": a.start_date,
        "end_date": None,
        "note": "cũ",
    }
    before = AuditLog.objects.count()
    assert svc.update_assignment(hr(), a, **kwargs) is False
    assert AuditLog.objects.count() == before
    other = company("Công ty C", "Tỉnh Ba")
    assert svc.update_assignment(hr(), a, **{**kwargs, "client_company": other, "note": "mới"})
    entry = AuditLog.objects.filter(
        action="UPDATE", object_type="employment.WorkAssignment"
    ).first()
    assert entry.changes[f"work_assignments[{a.pk}].client_company"] == [
        "Công ty Mẫu A – Tỉnh Một",
        "Công ty C – Tỉnh Ba",
    ]
    assert "mới" not in str(entry.changes)  # ghi chú là trường cá nhân


def test_sua_dot_khong_chong_lan_va_giu_duoc_cong_ty_da_ngung():
    worker = employee()
    first = add(worker, start=days(-100), end=days(-50))
    second = add(worker, start=days(-49), client=company("Công ty B", "Tỉnh Hai"))
    kwargs = {
        "client_company": second.client_company,
        "position": second.position,
        "end_date": None,
        "note": "",
    }
    with pytest.raises(AssignmentError) as exc:
        svc.update_assignment(hr(), second, start_date=days(-60), **kwargs)
    assert "chồng lấn" in exc.value.errors["start_date"]
    ClientCompany.objects.filter(pk=second.client_company_id).update(is_active=False)
    second.refresh_from_db()
    assert svc.update_assignment(
        hr(), second, start_date=days(-48), **kwargs
    )  # giữ công ty đã ngừng
    assert first.pk


def test_dat_ngay_ket_thuc_cho_dot_dang_mo_bang_sua():
    worker = employee()
    a = add(worker, start=days(-30))
    svc.update_assignment(
        hr(),
        a,
        client_company=a.client_company,
        position=a.position,
        start_date=a.start_date,
        end_date=days(-1),
    )
    a.refresh_from_db()
    assert a.end_date == days(-1)
    add(worker, start=days(0), client=company("Công ty B", "Tỉnh Hai"))  # giờ thêm đợt mới được


def test_sua_ngay_khong_lam_dong_luong_nam_ngoai_khoang():
    worker = employee()
    a = add(worker, start=days(-60))
    pay(a, day=days(-40))
    kwargs = {"client_company": a.client_company, "position": a.position, "note": ""}
    with pytest.raises(AssignmentError) as exc:
        svc.update_assignment(hr(), a, start_date=days(-30), end_date=None, **kwargs)
    assert "dòng lương" in exc.value.errors["start_date"]
    with pytest.raises(AssignmentError):
        svc.update_assignment(hr(), a, start_date=days(-60), end_date=days(-50), **kwargs)
    assert svc.update_assignment(hr(), a, start_date=days(-45), end_date=days(-30), **kwargs)


# ----- Lương: chỉ thêm, chỉ A và Q -----
@pytest.mark.parametrize(
    ("role", "allowed"),
    [("ADMIN", True), ("HR_MANAGER", True), ("HR_STAFF", False), ("VIEWER", False)],
)
def test_chi_admin_va_quan_ly_them_duoc_luong(role, allowed):
    a = add(employee(), start=days(-30))
    user = make_user(role)
    if allowed:
        assert pay(a, user=user, day=days(-20)).created_by == user
    else:
        with pytest.raises(PermissionDenied):
            pay(a, user=user, day=days(-20))
        assert not SalaryHistory.objects.exists()
    with pytest.raises(PermissionDenied):
        svc.add_salary(
            None, a, monthly_salary=1, effective_date=days(-20), reason="Không đăng nhập"
        )


def test_luong_hop_le_ma_hoa_that_dong_moi_giu_dong_cu():
    worker = employee()
    a = add(worker, start=days(-90))
    first = pay(a, amount=8_123_457, price=11_234_567, day=days(-90))
    second = pay(a, amount=9_000_001, price=None, day=days(-30), reason="Tăng lương theo bậc")
    assert SalaryHistory.objects.filter(assignment=a).count() == 2
    first.refresh_from_db()
    assert (first.monthly_salary, first.client_unit_price) == (8_123_457, 11_234_567)
    assert second.client_unit_price is None and second.worker_id == worker.pk
    with connection.cursor() as cur:
        cur.execute(
            "SELECT monthly_salary_enc, client_unit_price_enc FROM employment_salaryhistory"
        )
        raw = " ".join(v for row in cur.fetchall() for v in row if v)
    for digits in ("8123457", "11234567", "9000001"):
        assert digits not in raw  # SQL thô không thấy số rõ
    assert raw.count("gAAAA") == 3


def test_nhat_ky_luong_chi_co_tham_chieu_gia_tri_nam_o_audit_personal_value():
    worker = employee()
    a = add(worker, start=days(-30))
    row = pay(a, amount=7_654_321, price=9_876_543, reason="Lý do thử lương")
    entry = AuditLog.objects.get(action="CREATE", object_type="employment.SalaryHistory")
    text = str(entry.changes) + entry.note + entry.object_repr
    assert not any(x in text for x in ("7654321", "7.654.321", "9876543", "Lý do thử lương"))
    values = {
        v.field_name: (v.old_value_enc, v.new_value_enc)
        for v in AuditPersonalValue.objects.filter(audit_log=entry)
    }
    assert values[f"salary_history[{row.pk}].monthly_salary"] == (None, "7654321")
    assert values[f"salary_history[{row.pk}].client_unit_price"] == (None, "9876543")
    assert values[f"salary_history[{row.pk}].reason"] == (None, "Lý do thử lương")
    assert entry.worker_id == worker.pk


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        ({"amount": 0}, "monthly_salary"),
        ({"amount": None}, "monthly_salary"),
        ({"price": 0}, "client_unit_price"),
        ({"reason": "  "}, "reason"),
    ],
)
def test_lương_sai_bi_tu_choi(kwargs, field):
    a = add(employee(), start=days(-30))
    with pytest.raises(AssignmentError) as exc:
        pay(a, **kwargs)
    assert field in exc.value.errors
    assert not SalaryHistory.objects.exists()


def test_ngay_ap_dung_phai_nam_trong_khoang_cua_dot():
    worker = employee()
    a = add(worker, start=days(-60), end=days(-10))
    with pytest.raises(AssignmentError) as exc:
        pay(a, day=days(-61))
    assert "nằm trong đợt làm việc" in exc.value.errors["effective_date"]
    with pytest.raises(AssignmentError):
        pay(a, day=days(-9))
    pay(a, day=days(-60))  # sát biên: được
    pay(a, day=days(-10))


def test_luong_hien_tai_la_dong_ngay_ap_dung_lon_nhat_khong_qua_hom_nay():
    a = add(employee(), start=days(-90))
    pay(a, amount=1_000_000, day=days(-90))
    pay(a, amount=2_000_000, day=days(-30))
    pay(a, amount=3_000_000, day=days(0))
    future_ok = add_future = None
    assert svc.current_salary(a, TODAY).monthly_salary == 3_000_000
    assert svc.current_salary(a, days(-31)).monthly_salary == 1_000_000
    assert svc.current_salary(a, days(-100)) is None
    assert future_ok is None and add_future is None


def test_khong_co_url_sua_hoac_xoa_luong_va_xoa_dot():
    for url in (
        "/dot-lam-viec/1/luong/1/sua/",
        "/dot-lam-viec/1/luong/1/xoa/",
        "/dot-lam-viec/1/xoa/",
        "/luong/1/sua/",
    ):
        with pytest.raises(Resolver404):
            resolve(url)


# ----- Cảnh báo đợt sắp đủ 12 tháng (câu 43, 48) -----
def due(worker=None, **kw):
    info = indicators.assignment_due_info(**kw)
    return info if worker is None else info.get(worker.pk)


def test_mot_dot_sap_du_12_thang_trong_nguong_ngay_canh_bao():
    worker = employee()
    add(worker, start=days(-335))  # đủ 12 tháng sau khoảng 30 ngày
    info = due(worker, days=30)
    assert info is not None and info[1] == days(-335)
    assert info[0] > TODAY and (info[0] - TODAY).days <= 31
    assert due(worker, days=5) is None  # chưa vào ngưỡng 5 ngày
    assert due(employee()) is None  # công nhân khác không có đợt


def test_dot_da_qua_12_thang_van_canh_bao_den_khi_co_ngay_ket_thuc():
    worker = employee()
    a = add(worker, start=days(-500))
    assert due(worker) is not None
    svc.update_assignment(
        hr(),
        a,
        client_company=a.client_company,
        position=a.position,
        start_date=a.start_date,
        end_date=days(-1),
        note="",
    )
    assert due(worker) is None  # đã kết thúc: không còn đợt hiện tại


def test_dot_ket_thuc_truoc_ngay_du_han_khong_canh_bao():
    worker = employee()
    add(worker, start=days(-340), end=days(10))  # kết thúc trước ngày đủ hạn (~ngày 25)
    assert due(worker, days=30) is None


def test_chuoi_hai_dot_lien_nhau_cung_ten_khac_dia_diem_cong_don_tu_dau_chuoi():
    worker = employee()
    add(worker, start=days(-400), end=days(-201), client=company("Công ty An", "Bình Dương"))
    add(
        worker, start=days(-200), client=company("công ty  AN", "Đồng Nai")
    )  # liền nhau, khác địa điểm
    info = due(worker)
    assert info is not None
    assert info[1] == days(-400)  # tính từ đầu chuỗi, không phải đợt hiện tại
    assert info[2].client_company.location == "Đồng Nai"


def test_cach_hai_ngay_hoac_khac_ten_hoac_khac_dau_thi_dut_chuoi():
    for second_name, gap in (("Công ty An", 2), ("Công ty Bình", 1), ("Cong ty An", 1)):
        worker = employee()
        add(
            worker,
            start=days(-400),
            end=days(-201),
            client=company("Công ty An", f"Tỉnh {second_name}{gap}"),
        )
        add(
            worker,
            start=days(-201 + gap),
            client=company(second_name, f"Tỉnh khác {second_name}{gap}"),
        )
        # chuỗi đứt: chỉ đợt hiện tại (~200 ngày) nên chưa tới 12 tháng
        assert due(worker) is None, (second_name, gap)
    liền = employee()
    add(liền, start=days(-400), end=days(-201), client=company("Công ty An", "X1"))
    add(liền, start=days(-200), client=company("Công ty An", "X2"))  # cách 1 ngày: liền
    assert due(liền) is not None


def test_cau_hinh_so_thang_va_ngay_canh_bao_co_tac_dung():
    worker = employee()
    add(worker, start=days(-200))
    assert due(worker) is None  # mặc định 12 tháng, 30 ngày
    setting = SystemSetting.load()
    setting.assignment_limit_months = 7
    setting.save()
    assert due(worker) is not None  # 7 tháng từ 200 ngày trước: sắp/đã đủ
    assert due(worker, months=12) is None


def test_loc_danh_sach_dot_sap_du_han_va_thong_bao_o_tab():
    near, far = employee(), employee()
    add(near, start=days(-340), client=company("Công ty Gần", "A"))
    add(far, start=days(-30), client=company("Công ty Xa", "B"))
    client = login_client(hr())
    page = client.get("/ho-so/?dot_sap_du_han=1").content.decode()
    assert near.employee_code in page and far.employee_code not in page
    tab = client.get(f"/ho-so/{near.pk}/?tab=lam-viec").content.decode()
    assert "đủ thời hạn vào" in tab and "Sắp hết hạn" in tab
    other = client.get(f"/ho-so/{far.pk}/?tab=lam-viec").content.decode()
    assert "đủ thời hạn vào" not in other


# ----- Lọc danh sách theo công ty khách, chưa có bộ phận -----
def test_loc_theo_cong_ty_khach_chi_theo_dot_dang_dien_ra():
    a, b, past = employee(), employee(), employee()
    target = company("Công ty Lọc", "Tỉnh Lọc")
    add(a, start=days(-20), client=target)
    add(b, start=days(-20), client=company("Công ty Khác", "Tỉnh Khác"))
    add(past, start=days(-100), end=days(-50), client=target)  # đợt đã kết thúc: không tính
    page = login_client(hr()).get(f"/ho-so/?cong_ty_khach={target.pk}").content.decode()
    assert (
        a.employee_code in page and b.employee_code not in page and past.employee_code not in page
    )


def test_cot_cong_ty_khach_hien_ten_va_dia_diem_dot_hien_tai():
    worker = employee()
    add(worker, start=days(-20), client=company("Công ty Cột", "Tỉnh Cột"))
    page = login_client(hr()).get("/ho-so/").content.decode()
    assert "Công ty Cột – Tỉnh Cột" in page and ">Công ty khách<" in page
    header = re.search(r"<thead>.*?</thead>", page, re.S).group(0)
    assert "Bộ phận" not in header  # cột Bộ phận của bảng đã được thay thế


def test_loc_chua_co_bo_phan_va_co_bo_phan_co_the_chon():
    from apps.core.models import Department, Section

    with_section, without = employee(), employee()
    Employment.objects.filter(worker=without).update(section=None)
    section = Employment.objects.get(worker=with_section).section
    client = login_client(hr())
    page = client.get("/ho-so/?bo_phan=chua-co").content.decode()
    assert without.employee_code in page and with_section.employee_code not in page
    page = client.get(f"/ho-so/?bo_phan={section.pk}").content.decode()
    assert with_section.employee_code in page and without.employee_code not in page
    options = client.get("/ho-so/").content.decode()
    assert 'value="chua-co"' in options and "Chưa có bộ phận" in options
    assert Department.objects.exists() and Section.objects.exists()


# ----- Hạn lưu trữ không phụ thuộc đợt làm việc (câu 44) -----
def test_han_luu_tru_theo_ngay_nghi_viec_khong_theo_ngay_ket_thuc_dot():
    from apps.workers import retention
    from tests.test_anonymize import rich_worker

    worker, _ = rich_worker()
    before = retention.retention_info(worker)
    assert before.basis == "RESIGNED" and before.expires_on == datetime.date(2036, 1, 1)
    a = WorkAssignment.objects.create(
        worker=worker,
        client_company=company(),
        position=position(),
        start_date=D(2019, 1, 1),
        end_date=D(2019, 12, 31),  # đợt kết thúc từ lâu, trước ngày nghỉ việc
        created_by=hr(),
    )
    assert retention.retention_info(worker) == before
    WorkAssignment.objects.filter(pk=a.pk).update(end_date=D(2025, 6, 30))
    assert retention.retention_info(worker) == before  # đổi ngày kết thúc đợt cũng không đổi hạn


# ----- View -----
def form(**extra):
    data = {
        "client_company": company().pk,
        "position": position().pk,
        "start_date": days(-5).strftime("%d/%m/%Y"),
    }
    data.update(extra)
    return data


def test_view_them_sua_dot_nhan_vien_duoc_viewer_403():
    worker = employee()
    staff = login_client(hr())
    assert staff.get(f"/ho-so/{worker.pk}/dot-lam-viec/them/").status_code == 200
    response = staff.post(f"/ho-so/{worker.pk}/dot-lam-viec/them/", form())
    assert response.status_code == 302
    a = WorkAssignment.objects.get(worker=worker)
    assert staff.get(f"/dot-lam-viec/{a.pk}/sua/").status_code == 200
    viewer = login_client(make_user("VIEWER"))
    for url in (f"/ho-so/{worker.pk}/dot-lam-viec/them/", f"/dot-lam-viec/{a.pk}/sua/"):
        assert viewer.get(url).status_code == 403 and viewer.post(url, form()).status_code == 403


def test_view_them_dot_khi_dang_mo_hien_loi_o_dung_o_roi_luu_duoc_khi_nhap_ngay_dong():
    worker = employee()
    add(worker, start=days(-50))
    staff = login_client(hr())
    url = f"/ho-so/{worker.pk}/dot-lam-viec/them/"
    other = company("Công ty B", "Tỉnh Hai").pk
    response = staff.post(url, form(client_company=other, start_date=days(-5).strftime("%d/%m/%Y")))
    assert (
        response.status_code == 200
        and "Nhập ngày kết thúc của đợt đó." in response.content.decode()
    )
    response = staff.post(
        url,
        form(
            client_company=other,
            start_date=days(-5).strftime("%d/%m/%Y"),
            previous_end_date=days(-6).strftime("%d/%m/%Y"),
        ),
    )
    assert response.status_code == 302 and WorkAssignment.objects.filter(worker=worker).count() == 2


def test_view_luong_hr_va_viewer_403_admin_quan_ly_luu_duoc():
    worker = employee()
    a = add(worker, start=days(-30))
    url = f"/dot-lam-viec/{a.pk}/luong/them/"
    body = {
        "monthly_salary": "8500000",
        "client_unit_price": "",
        "effective_date": days(-10).strftime("%d/%m/%Y"),
        "reason": "Thiết lập ban đầu",
    }
    for role in ("HR_STAFF", "VIEWER"):
        client = login_client(make_user(role))
        assert client.get(url).status_code == 403
        assert client.post(url, body).status_code == 403
    assert not SalaryHistory.objects.exists()
    for role in ("HR_MANAGER", "ADMIN"):
        client = login_client(make_user(role))
        assert client.get(url).status_code == 200
        assert client.post(url, {**body, "monthly_salary": "8500001"}).status_code == 302
    assert SalaryHistory.objects.filter(assignment=a).count() == 2


def test_view_luong_sai_hien_loi_tieng_viet_va_form_dien_san_tu_dong_gan_nhat():
    worker = employee()
    a = add(worker, start=days(-30))
    pay(a, amount=7_000_000, price=9_500_000, day=days(-20))
    client = login_client(manager())
    url = f"/dot-lam-viec/{a.pk}/luong/them/"
    page = client.get(url).content.decode()
    assert 'value="7000000"' in page and 'value="9500000"' in page  # khoản kia giữ giá trị cũ
    response = client.post(url, {"monthly_salary": "abc", "effective_date": "x", "reason": ""})
    page = response.content.decode()
    assert "Nhập số nguyên" in page and "Nhập ngày đúng định dạng dd/mm/yyyy." in page
    assert "Nhập lý do thay đổi." in page
    response = client.post(
        url,
        {
            "monthly_salary": "8000000",
            "effective_date": (TODAY - datetime.timedelta(days=60)).strftime("%d/%m/%Y"),
            "reason": "Sai ngày",
        },
    )
    assert "nằm trong đợt làm việc" in response.content.decode()


def test_tab_moi_vai_tro_xem_luong_va_don_gia_chi_quan_ly_co_nut_ghi_nhan():
    worker = employee()
    a = add(worker, start=days(-30), note="Ghi chú riêng của đợt")
    pay(a, amount=8_765_432, price=12_345_678, reason="Lý do tăng lương riêng")
    for role in ("ADMIN", "HR_MANAGER", "HR_STAFF", "VIEWER"):
        page = (
            login_client(make_user(role)).get(f"/ho-so/{worker.pk}/?tab=lam-viec").content.decode()
        )
        assert "8.765.432" in page and "12.345.678" in page, role  # mọi vai trò xem được
        can = role in ("ADMIN", "HR_MANAGER")
        assert ("Ghi nhận thay đổi lương" in page) == can, role
        staff = role != "VIEWER"
        assert ("Ghi chú riêng của đợt" in page) == staff, role  # trường cá nhân chỉ nhân viên
        assert ("Lý do tăng lương riêng" in page) == staff, role
        assert ("Thêm đợt làm việc" in page) == staff, role
        assert "/dot-lam-viec/" not in page or staff or "/luong/" not in page


def test_viewer_thay_luong_cua_dot_hien_tai_tu_v11():
    """Câu 42, 48: lương mở cho Viewer (trường nhạy cảm khác kiểm ở test_viewer_sensitive)."""
    worker = employee()
    a = add(worker, start=days(-30))
    pay(a, amount=6_543_210)
    page = (
        login_client(make_user("VIEWER")).get(f"/ho-so/{worker.pk}/?tab=lam-viec").content.decode()
    )
    assert "6.543.210" in page
