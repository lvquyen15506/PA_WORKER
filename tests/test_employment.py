"""Tiếp nhận, đổi thông tin làm việc, hợp đồng (Phase 6 bước 4; câu 6, 7, 36; mục IV.5).

Kiểm tra service (quy tắc nghiệp vụ, nhật ký), view (phân quyền khi gọi thẳng URL) và các liên kết
ở danh sách/tab. Kịch bản nghiệm thu 8, 9, 10 chạy bằng Playwright ở scripts/nghiem_thu_phase6.py.
"""

import datetime

import pytest
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.models import AuditLog, AuditPersonalValue
from apps.core.codes import next_code
from apps.core.models import Department, Position, Section, Shift, SystemSetting, Team
from apps.documents.models import WorkerDocument
from apps.employment import services
from apps.employment.models import Contract, Employment, EmploymentHistory
from apps.employment.services import EmploymentError
from apps.workers.models import Worker
from tests.factories import (
    login_client,
    make_application,
    make_user,
    make_worker,
    make_worker_in_status,
)

pytestmark = pytest.mark.django_db
D = datetime.date
TODAY = datetime.date.today()


def hr():
    return make_user("HR_STAFF")


def verified_with_passed(**kwargs):
    worker = make_worker_in_status("VERIFIED")
    app = make_application(worker, "PASSED", result_date=TODAY, **kwargs)
    return worker, app


def structure():
    dep = Department.objects.create(name=f"PB {Department.objects.count()}")
    section = Section.objects.create(department=dep, name="Chuyền 1")
    team = Team.objects.create(section=section, name="Tổ 1")
    position = Position.objects.get_or_create(name="Công nhân lắp ráp")[0]
    shift = Shift.objects.create(name=f"Ca {Shift.objects.count()}")
    return section, team, position, shift


def onboard_data(**overrides):
    _, _, position, _ = structure()
    data = {"received_date": D(2026, 3, 1), "start_date": D(2026, 3, 5), "position": position}
    data.update(overrides)
    return data


def onboarded(status="ACTIVE", **overrides):
    """Công nhân đã tiếp nhận; đưa trạng thái làm việc tới `status` bằng change_employment."""
    worker, app = verified_with_passed()
    section, team, position, shift = structure()
    data = {
        "received_date": D(2026, 3, 1),
        "start_date": D(2026, 3, 5),
        "position": position,
        "section": section,
        "team": team,
        "shift": shift,
    }
    data.update(overrides)
    services.onboard(hr(), app, **data)
    worker.refresh_from_db()
    if status != "AWAITING":
        change(worker, status=status)
    return worker


def employee_in_state(status):
    """Công nhân đã có thông tin làm việc, hồ sơ ở `status` (đi qua workflow)."""
    from tests.factories import make_employment

    worker = make_worker_in_status(status)
    make_employment(worker, "PROBATION")
    Worker.objects.filter(pk=worker.pk).update(employee_code=f"CN-S{worker.pk:05d}")
    worker.refresh_from_db()
    return worker


def change(worker, *, user=None, **overrides):
    emp = Employment.objects.get(worker=worker)
    data = {
        "effective_date": D(2026, 4, 1),
        "section": emp.section,
        "team": emp.team,
        "position": emp.position,
        "shift": emp.shift,
        "manager": emp.manager,
        "work_status": emp.work_status,
    }
    if "status" in overrides:
        data["work_status"] = overrides.pop("status")
    data.update(overrides)
    return services.change_employment(user or hr(), worker, **data)


# ----- Tiếp nhận: điều kiện câu 7 -----
@pytest.mark.parametrize("rec", ["NEW", "SCREENING", "INTERVIEW", "FAILED", "DECLINED"])
def test_chi_tiep_nhan_khi_lan_ung_tuyen_dat(rec):
    worker = make_worker_in_status("VERIFIED")
    app = make_application(worker, rec, result_date=TODAY)
    with pytest.raises(EmploymentError, match="trạng thái Đạt"):
        services.onboard(hr(), app, **onboard_data())
    assert not Employment.objects.filter(worker=worker).exists()
    assert not services.can_onboard(app, worker)


@pytest.mark.parametrize("ver", ["DRAFT", "PENDING", "NEEDS_INFO"])
def test_chi_tiep_nhan_khi_ho_so_da_xac_minh(ver):
    worker = make_worker_in_status(ver)
    app = make_application(worker, "PASSED", result_date=TODAY)
    with pytest.raises(EmploymentError, match="Đã xác minh"):
        services.onboard(hr(), app, **onboard_data())
    assert not services.can_onboard(app, worker)
    assert Worker.objects.get(pk=worker.pk).employee_code is None


@pytest.mark.parametrize("ver", ["REJECTED", "ARCHIVED"])
def test_ho_so_bi_tu_choi_hoac_luu_tru_bi_chan_o_quyen(ver):
    worker = make_worker_in_status(ver)
    app = make_application(worker, "PASSED", result_date=TODAY)
    with pytest.raises(PermissionDenied):
        services.onboard(make_user("ADMIN"), app, **onboard_data())


def test_viewer_khong_tiep_nhan_duoc():
    worker, app = verified_with_passed()
    with pytest.raises(PermissionDenied):
        services.onboard(make_user("VIEWER"), app, **onboard_data())


@pytest.mark.parametrize("role", ["HR_STAFF", "HR_MANAGER", "ADMIN"])
def test_nhan_vien_tiep_nhan_duoc_sinh_ma_nv_cho_trang_thai_nhan_viec(role):
    worker, app = verified_with_passed()
    emp = services.onboard(make_user(role), app, **onboard_data())
    worker.refresh_from_db()
    assert worker.employee_code == "CN-00001"
    assert (emp.work_status, emp.application_id) == ("AWAITING", app.pk)
    hist = EmploymentHistory.objects.get(worker=worker)
    assert hist.change_type == "ONBOARD" and hist.to_work_status == "AWAITING"
    assert hist.effective_date == D(2026, 3, 5)
    assert worker.verification_status == "VERIFIED"  # không đổi bộ trạng thái khác


def test_ma_nv_sinh_dung_cau_hinh_va_khong_trung_ma_da_cap():
    setting = SystemSetting.load()
    setting.employee_code_prefix, setting.employee_code_digits = "NV", 4
    setting.employee_code_use_year = False
    setting.save()
    w1, a1 = verified_with_passed()
    w2, a2 = verified_with_passed()
    Worker.objects.filter(pk=w1.pk).update(employee_code="NV-0001")  # mã cũ nhập từ Excel
    services.onboard(hr(), a2, **onboard_data())
    assert Worker.objects.get(pk=w2.pk).employee_code == "NV-0002"  # bỏ qua mã đã tồn tại
    assert w1.pk != w2.pk and a1.pk != a2.pk


def test_ma_nv_co_nam_theo_cau_hinh():
    setting = SystemSetting.load()
    setting.employee_code_use_year = True
    setting.save()
    worker, app = verified_with_passed()
    services.onboard(hr(), app, **onboard_data())
    year = datetime.datetime.now().year
    assert Worker.objects.get(pk=worker.pk).employee_code == f"CN-{year}-00001"


def test_tiep_nhan_ghi_nhat_ky_cap_ma_va_tao_dong_lam_viec_khong_ho_ten():
    worker, app = verified_with_passed()
    services.onboard(hr(), app, **onboard_data())
    code = Worker.objects.get(pk=worker.pk).employee_code
    issued = AuditLog.objects.get(
        action="UPDATE", object_type="workers.Worker", note__startswith="Cấp mã nhân viên"
    )
    assert issued.changes == {"employee_code": [None, code]} and issued.worker_id == worker.pk
    entry = AuditLog.objects.get(action="CREATE", object_type="employment.Employment")
    assert code in entry.note and worker.full_name not in entry.note + entry.object_repr
    assert entry.worker_id == worker.pk


def test_nguoi_da_co_ma_nv_quay_lai_giu_ma_cu_va_dung_lai_dong_1_1():
    worker = onboarded("ACTIVE")
    old_code = Worker.objects.get(pk=worker.pk).employee_code
    change(worker, status="RESIGNED", resign_date=D(2026, 6, 1), resign_reason="SELF")
    employment_pk = Employment.objects.get(worker=worker).pk
    # Quay lại (câu 6): Lưu trữ → Mở lại hồ sơ → gửi duyệt, duyệt → ứng tuyển Đạt → Tiếp nhận.
    from apps.core.choices import VerificationStatus as VS
    from apps.recruitment import services as recruitment_services
    from apps.workers import services as worker_services
    from apps.workers.workflow import transition

    manager = make_user("HR_MANAGER")
    transition(Worker.objects.get(pk=worker.pk), VS.ARCHIVED, manager, reason="Đã nghỉ việc")
    new_app = worker_services.reopen_worker(
        hr(),
        Worker.objects.get(pk=worker.pk),
        position=Position.objects.first(),
        source=make_application(make_worker()).source,
    )
    submitter = make_user("HR_STAFF")
    transition(Worker.objects.get(pk=worker.pk), VS.PENDING, submitter)
    transition(Worker.objects.get(pk=worker.pk), VS.VERIFIED, make_user("HR_MANAGER"))
    recruitment_services.update_application(
        hr(),
        new_app,
        position=new_app.position,
        source=new_app.source,
        applied_date=new_app.applied_date,
        status="PASSED",
    )
    new_app.refresh_from_db()
    refreshed = Worker.objects.get(pk=worker.pk)
    assert services.can_onboard(new_app, refreshed)
    emp = services.onboard(hr(), new_app, **onboard_data(start_date=D(2026, 9, 1)))
    assert emp.pk == employment_pk  # dùng lại dòng 1-1
    assert emp.work_status == "AWAITING" and emp.resign_date is None and emp.resign_reason == ""
    assert emp.application_id == new_app.pk
    refreshed.refresh_from_db()
    assert refreshed.employee_code == old_code  # giữ mã cũ, không cấp mã mới
    last = EmploymentHistory.objects.filter(worker=worker, change_type="ONBOARD").first()
    assert last.from_work_status == "RESIGNED" and last.to_work_status == "AWAITING"
    assert EmploymentHistory.objects.filter(worker=worker, change_type="ONBOARD").count() == 2


def test_khong_tiep_nhan_hai_lan_cung_mot_lan_ung_tuyen():
    worker, app = verified_with_passed()
    services.onboard(hr(), app, **onboard_data())
    with pytest.raises(EmploymentError, match="đang có thông tin làm việc"):
        services.onboard(hr(), app, **onboard_data())
    assert Employment.objects.filter(worker=worker).count() == 1
    assert EmploymentHistory.objects.filter(worker=worker).count() == 1


def test_ung_tuyen_khong_thuoc_ho_so_bi_tu_choi():
    worker, _ = verified_with_passed()
    other_app = make_application(make_worker(), "PASSED", result_date=TODAY)
    other_app.worker = make_worker_in_status("VERIFIED")
    with pytest.raises(EmploymentError):
        services.onboard(hr(), other_app, **onboard_data())
    assert worker.pk


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"received_date": None}, "received_date"),
        ({"start_date": None}, "start_date"),
        ({"received_date": D(2026, 3, 9), "start_date": D(2026, 3, 5)}, "start_date"),
        ({"position": None}, "position"),
    ],
)
def test_tiep_nhan_thieu_hoac_sai_ngay_chuc_danh(override, field):
    worker, app = verified_with_passed()
    with pytest.raises(EmploymentError) as exc:
        services.onboard(hr(), app, **onboard_data(**override))
    assert field in exc.value.errors
    assert Worker.objects.get(pk=worker.pk).employee_code is None  # lỗi thì không cấp mã
    assert not Employment.objects.exists()


def test_bo_phan_khong_bat_buoc_nhung_to_phai_thuoc_bo_phan():
    worker, app = verified_with_passed()
    section, team, _, _ = structure()
    other_section = Section.objects.create(department=section.department, name="Chuyền 2")
    with pytest.raises(EmploymentError) as exc:
        services.onboard(hr(), app, **onboard_data(section=other_section, team=team))
    assert exc.value.errors["team"] == "Tổ phải thuộc bộ phận đã chọn."
    with pytest.raises(EmploymentError) as exc:
        services.onboard(hr(), app, **onboard_data(team=team))
    assert exc.value.errors["team"] == "Chọn bộ phận trước khi chọn tổ."
    emp = services.onboard(hr(), app, **onboard_data())  # không bộ phận, không tổ: hợp lệ
    assert emp.section is None and emp.department is None


def test_nguoi_quan_ly_phai_la_cong_nhan_khac_co_ma_nv():
    worker, app = verified_with_passed()
    no_code = make_worker()
    with pytest.raises(EmploymentError) as exc:
        services.onboard(hr(), app, **onboard_data(manager=no_code))
    assert "mã nhân viên" in exc.value.errors["manager"]
    boss = onboarded("ACTIVE")
    emp = services.onboard(hr(), app, **onboard_data(manager=boss))
    assert emp.manager_id == boss.pk
    hist = EmploymentHistory.objects.get(worker=worker)
    assert hist.to_manager_id == boss.pk
    entry = AuditLog.objects.filter(
        object_type="employment.Employment", action="CREATE"
    ).first()  # mới nhất
    assert entry.changes["employment.manager"][1] == boss.employee_code  # chỉ có mã, không họ tên


def test_danh_muc_da_ngung_khong_chon_duoc_khi_tiep_nhan():
    worker, app = verified_with_passed()
    section, _, position, shift = structure()
    Section.objects.filter(pk=section.pk).update(is_active=False)
    Shift.objects.filter(pk=shift.pk).update(is_active=False)
    section.refresh_from_db()
    shift.refresh_from_db()
    with pytest.raises(EmploymentError) as exc:
        services.onboard(hr(), app, **onboard_data(section=section, shift=shift))
    assert set(exc.value.errors) == {"section", "shift"}


# ----- change_employment luôn thêm EmploymentHistory -----
def count_history(worker):
    return EmploymentHistory.objects.filter(worker=worker).count()


def test_dieu_chuyen_bo_phan_them_dung_mot_dong_lich_su_giu_dong_cu():
    worker = onboarded("ACTIVE")
    before = count_history(worker)
    old_section = Employment.objects.get(worker=worker).section
    new_section = Section.objects.create(department=old_section.department, name="Chuyền 9")
    hist = change(
        worker,
        section=new_section,
        team=None,
        decision_no="QĐ-01",
        reason="Điều chuyển theo nhu cầu",
    )
    assert count_history(worker) == before + 1
    assert hist.change_type == "TRANSFER"
    assert (hist.from_section, hist.to_section) == (old_section, new_section)
    assert hist.decision_no == "QĐ-01" and hist.from_position is None and hist.to_position is None
    assert Employment.objects.get(worker=worker).section == new_section
    assert EmploymentHistory.objects.filter(
        worker=worker, change_type="ONBOARD"
    ).exists()  # dòng cũ còn


@pytest.mark.parametrize(
    ("what", "expected"),
    [
        ("position", "POSITION_CHANGE"),
        ("shift", "SHIFT_CHANGE"),
        ("status", "STATUS_CHANGE"),
        ("section", "TRANSFER"),
    ],
)
def test_moi_loai_thay_doi_them_dung_mot_dong_va_dung_loai(what, expected):
    worker = onboarded("PROBATION")
    emp = Employment.objects.get(worker=worker)
    values = {
        "position": Position.objects.create(name="Tổ trưởng"),
        "shift": Shift.objects.create(name="Ca đêm"),
        "status": "ACTIVE",
        "section": Section.objects.create(department=emp.section.department, name="BP mới"),
    }
    kwargs = {what: values[what]}
    if what == "section":
        kwargs["team"] = None
    before = count_history(worker)
    hist = change(worker, **kwargs)
    assert count_history(worker) == before + 1 and hist.change_type == expected


def test_khong_co_gi_doi_thi_bao_loi_va_khong_ghi_lich_su_hay_nhat_ky():
    worker = onboarded("ACTIVE")
    before, logs = count_history(worker), AuditLog.objects.count()
    with pytest.raises(EmploymentError, match="Không có thay đổi"):
        change(worker)
    assert count_history(worker) == before and AuditLog.objects.count() == logs


def test_doi_nguoi_quan_ly_co_dong_lich_su_va_nhat_ky_chi_co_ma():
    worker, boss = onboarded("ACTIVE"), onboarded("ACTIVE")
    hist = change(worker, manager=boss)
    assert hist.change_type == "TRANSFER"
    assert (hist.from_manager, hist.to_manager) == (None, boss)
    entry = AuditLog.objects.filter(object_type="employment.Employment", action="UPDATE").first()
    assert entry.changes["employment.manager"] == [None, boss.employee_code]
    assert worker.full_name not in str(entry.changes) + entry.note
    with pytest.raises(EmploymentError) as exc:
        change(worker, manager=worker)
    assert "chính mình" in exc.value.errors["manager"]


def test_nghi_viec_bat_buoc_ngay_va_ly_do_luu_dong_lich_su():
    worker = onboarded("ACTIVE")
    with pytest.raises(EmploymentError) as exc:
        change(worker, status="RESIGNED")
    assert {"resign_date", "resign_reason"} <= set(exc.value.errors)
    with pytest.raises(EmploymentError) as exc:
        change(worker, status="RESIGNED", resign_date=D(2026, 1, 1), resign_reason="SELF")
    assert "không được trước ngày bắt đầu" in exc.value.errors["resign_date"]
    change(
        worker,
        status="RESIGNED",
        resign_date=D(2026, 7, 1),
        resign_reason="CONTRACT_END",
        resign_note="Hết hạn",
    )
    emp = Employment.objects.get(worker=worker)
    assert (emp.work_status, emp.resign_date, emp.resign_reason) == (
        "RESIGNED",
        D(2026, 7, 1),
        "CONTRACT_END",
    )
    assert AuditPersonalValue.objects.filter(field_name="employment.resign_note").exists()


def test_da_nghi_viec_thi_khong_doi_tiep():
    worker = onboarded("ACTIVE")
    change(worker, status="RESIGNED", resign_date=D(2026, 7, 1), resign_reason="SELF")
    with pytest.raises(EmploymentError, match="Mở lại hồ sơ"):
        change(worker, status="ACTIVE")


def test_thong_tin_lam_viec_chua_co_thi_khong_doi_duoc():
    worker = make_worker_in_status("VERIFIED")
    with pytest.raises(EmploymentError, match="tiếp nhận vào làm trước"):
        services.change_employment(
            hr(),
            worker,
            effective_date=TODAY,
            section=None,
            team=None,
            position=Position.objects.create(name="X"),
            shift=None,
            manager=None,
            work_status="ACTIVE",
        )


@pytest.mark.parametrize("status", ["VERIFIED", "PENDING", "DRAFT", "NEEDS_INFO"])
def test_tab_lam_viec_thao_tac_duoc_o_cac_trang_thai_tru_tu_choi_luu_tru(status):
    """Câu 36: Chờ duyệt chỉ khóa phần được duyệt; tab Quá trình làm việc vẫn thao tác được."""
    worker = employee_in_state(status)
    hist = change(worker, shift=Shift.objects.create(name=f"Ca {status}"))
    assert hist.change_type == "SHIFT_CHANGE"


def test_viewer_va_nguoi_chua_dang_nhap_khoa_tab_lam_viec():
    worker = onboarded("ACTIVE")
    with pytest.raises(PermissionDenied):
        change(worker, user=make_user("VIEWER"), status="SUSPENDED")
    emp = Employment.objects.get(worker=worker)
    with pytest.raises(PermissionDenied):
        services.change_employment(
            None,
            worker,
            effective_date=TODAY,
            section=emp.section,
            team=emp.team,
            position=emp.position,
            shift=emp.shift,
            manager=None,
            work_status="SUSPENDED",
        )


@pytest.mark.parametrize("status", ["REJECTED", "ARCHIVED"])
def test_bi_tu_choi_va_luu_tru_khoa_tab_lam_viec(status):
    worker = employee_in_state(status)
    with pytest.raises(PermissionDenied):
        change(worker, user=make_user("ADMIN"), shift=Shift.objects.create(name="Ca khóa"))


# ----- Nghỉ việc tự đóng đợt làm việc đang mở (câu 40) -----
def test_nghi_viec_tu_dong_dong_dot_dang_mo_vao_ngay_nghi():
    from apps.core.models import ClientCompany
    from apps.employment.models import WorkAssignment

    worker = onboarded("ACTIVE")
    client = ClientCompany.objects.create(name="Công ty Mẫu", location="Tỉnh Mẫu")
    assignment = WorkAssignment.objects.create(
        worker=worker,
        client_company=client,
        position=Position.objects.first(),
        start_date=D(2026, 3, 10),
        created_by=hr(),
    )
    change(worker, status="RESIGNED", resign_date=D(2026, 8, 20), resign_reason="SELF")
    assignment.refresh_from_db()
    assert assignment.end_date == D(2026, 8, 20)
    entry = AuditLog.objects.get(object_type="employment.WorkAssignment", action="UPDATE")
    assert entry.changes[f"work_assignments[{assignment.pk}].end_date"] == [None, "2026-08-20"]


# ----- Hợp đồng -----
def contract_data(**overrides):
    data = {
        "contract_no": "HD-2026-001",
        "contract_type": "FIXED_TERM",
        "signed_date": D(2026, 3, 1),
        "effective_date": D(2026, 3, 5),
        "expiry_date": D(2027, 3, 4),
        "note": "",
    }
    data.update(overrides)
    return data


def pdf(name="hd.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 hop dong gia", content_type="application/pdf")


def test_them_hop_dong_co_tep_tao_tai_lieu_loai_hop_dong_va_ghi_nhat_ky():
    worker = onboarded("ACTIVE")
    contract = services.add_contract(hr(), worker, uploaded=pdf(), **contract_data())
    assert contract.document.document_type.system_code == "CONTRACT"
    assert contract.current_document == contract.document
    assert WorkerDocument.objects.filter(worker=worker).count() == 1
    entry = AuditLog.objects.get(action="CREATE", object_type="employment.Contract")
    assert entry.worker_id == worker.pk and "HD-2026-001" in str(entry.changes)


def test_hop_dong_khong_xac_dinh_thoi_han_bo_ngay_het_han_con_loai_khac_bat_buoc():
    worker = onboarded("ACTIVE")
    c = services.add_contract(
        hr(), worker, **contract_data(contract_type="INDEFINITE", expiry_date=D(2030, 1, 1))
    )
    assert c.expiry_date is None
    with pytest.raises(EmploymentError) as exc:
        services.add_contract(hr(), worker, **contract_data(contract_no="HD-2", expiry_date=None))
    assert exc.value.errors["expiry_date"] == "Nhập ngày hết hạn."
    with pytest.raises(EmploymentError) as exc:
        services.add_contract(
            hr(), worker, **contract_data(contract_no="HD-3", expiry_date=D(2026, 3, 5))
        )
    assert "sau ngày hiệu lực" in exc.value.errors["expiry_date"]


def test_so_hop_dong_khong_trung_ke_ca_khac_hoa_thuong_va_thieu_thi_bao_loi():
    worker = onboarded("ACTIVE")
    services.add_contract(hr(), worker, **contract_data())
    with pytest.raises(EmploymentError) as exc:
        services.add_contract(hr(), worker, **contract_data(contract_no="hd-2026-001"))
    assert exc.value.errors["contract_no"] == "Số hợp đồng này đã được dùng."
    with pytest.raises(EmploymentError) as exc:
        services.add_contract(
            hr(),
            worker,
            **contract_data(
                contract_no="", contract_type="", signed_date=None, effective_date=None
            ),
        )
    assert {"contract_no", "contract_type", "signed_date", "effective_date"} <= set(
        exc.value.errors
    )


def test_chua_co_thong_tin_lam_viec_thi_chua_them_hop_dong():
    worker = make_worker_in_status("VERIFIED")
    with pytest.raises(EmploymentError, match="chưa có thông tin làm việc"):
        services.add_contract(hr(), worker, **contract_data())


def test_tep_hop_dong_sai_dinh_dang_bi_tu_choi_va_khong_tao_hop_dong():
    worker = onboarded("ACTIVE")
    bad = SimpleUploadedFile("hd.pdf", b"khong phai pdf that", content_type="application/pdf")
    with pytest.raises(EmploymentError) as exc:
        services.add_contract(hr(), worker, uploaded=bad, **contract_data())
    assert "file" in exc.value.errors
    assert not Contract.objects.exists() and not WorkerDocument.objects.exists()


def test_cho_duyet_khong_tai_duoc_tep_nhung_van_them_duoc_hop_dong_khong_tep():
    worker = employee_in_state("PENDING")
    with pytest.raises(EmploymentError) as exc:
        services.add_contract(hr(), worker, uploaded=pdf(), **contract_data())
    assert "file" in exc.value.errors and not Contract.objects.exists()
    services.add_contract(hr(), worker, **contract_data())  # không tệp: được
    assert Contract.objects.count() == 1


def test_sua_hop_dong_ghi_gia_tri_cu_moi_gan_tep_moi_giu_tep_cu():
    worker = onboarded("ACTIVE")
    contract = services.add_contract(
        hr(), worker, uploaded=pdf(), **contract_data(note="Ghi chú cũ")
    )
    first_doc = contract.document
    assert services.update_contract(
        hr(),
        contract,
        uploaded=pdf("moi.pdf"),
        **contract_data(note="Ghi chú mới", expiry_date=D(2027, 6, 1)),
    )
    contract.refresh_from_db()
    assert contract.document_id != first_doc.pk and contract.expiry_date == D(2027, 6, 1)
    assert WorkerDocument.objects.filter(worker=worker).count() == 2  # tệp cũ vẫn ở tab Tài liệu
    pv = (
        AuditPersonalValue.objects.filter(field_name=f"contracts[{contract.pk}].note")
        .order_by("id")
        .last()
    )
    assert (pv.old_value_enc, pv.new_value_enc) == ("Ghi chú cũ", "Ghi chú mới")
    assert not services.update_contract(
        hr(), contract, **contract_data(note="Ghi chú mới", expiry_date=D(2027, 6, 1))
    )


def test_hop_dong_viewer_va_ho_so_khoa_bi_chan():
    worker = onboarded("ACTIVE")
    with pytest.raises(PermissionDenied):
        services.add_contract(make_user("VIEWER"), worker, **contract_data())
    archived = make_worker_in_status("ARCHIVED")
    with pytest.raises(PermissionDenied):
        services.add_contract(make_user("ADMIN"), archived, **contract_data())


# ----- View: phân quyền khi gọi thẳng URL -----
def form_post(**extra):
    _, _, position, _ = structure()
    data = {"received_date": "01/03/2026", "start_date": "05/03/2026", "position": position.pk}
    data.update(extra)
    return data


@pytest.mark.parametrize(
    ("role", "status"), [("HR_STAFF", 302), ("HR_MANAGER", 302), ("ADMIN", 302), ("VIEWER", 403)]
)
def test_view_tiep_nhan_theo_vai_tro(role, status):
    worker, app = verified_with_passed()
    client = login_client(make_user(role))
    response = client.post(f"/ung-tuyen/{app.pk}/tiep-nhan/", form_post())
    assert response.status_code == status
    assert Employment.objects.filter(worker=worker).exists() == (status == 302)


def test_view_tiep_nhan_khi_chua_du_dieu_kien_chuyen_ve_tab_kem_thong_bao():
    worker = make_worker_in_status("PENDING")
    app = make_application(worker, "PASSED", result_date=TODAY)
    client = login_client(make_user("ADMIN"))
    response = client.post(f"/ung-tuyen/{app.pk}/tiep-nhan/", form_post(), follow=True)
    assert "Chỉ tiếp nhận vào làm khi" in response.content.decode()
    assert not Employment.objects.exists()


def test_view_tiep_nhan_sai_ngay_hien_loi_tieng_viet():
    worker, app = verified_with_passed()
    client = login_client(make_user("HR_STAFF"))
    response = client.post(
        f"/ung-tuyen/{app.pk}/tiep-nhan/",
        form_post(received_date="09/03/2026", manager_code="ZZZ-1"),
    )
    page = response.content.decode()
    assert response.status_code == 200
    assert "Không tìm thấy công nhân có mã nhân viên này." in page
    assert not Employment.objects.exists()
    response = client.post(f"/ung-tuyen/{app.pk}/tiep-nhan/", form_post(received_date="09/03/2026"))
    assert "Ngày bắt đầu không được trước ngày tiếp nhận." in response.content.decode()


@pytest.mark.parametrize("role", ["HR_STAFF", "HR_MANAGER", "ADMIN"])
def test_view_ghi_nhan_thay_doi_va_hop_dong_nhan_vien_duoc(role):
    worker = onboarded("ACTIVE")
    client = login_client(make_user(role))
    emp = Employment.objects.get(worker=worker)
    post = {
        "effective_date": "01/04/2026",
        "section": emp.section_id,
        "team": emp.team_id,
        "position": emp.position_id,
        "shift": "",
        "manager_code": "",
        "work_status": "SUSPENDED",
    }
    assert client.get(f"/ho-so/{worker.pk}/lam-viec/thay-doi/").status_code == 200
    assert client.post(f"/ho-so/{worker.pk}/lam-viec/thay-doi/", post).status_code == 302
    assert Employment.objects.get(worker=worker).work_status == "SUSPENDED"
    contract_post = {
        "contract_no": f"HD-{role}",
        "contract_type": "FIXED_TERM",
        "signed_date": "01/03/2026",
        "effective_date": "05/03/2026",
        "expiry_date": "04/03/2027",
        "file": pdf(),
    }
    assert client.post(f"/ho-so/{worker.pk}/hop-dong/them/", contract_post).status_code == 302
    contract = Contract.objects.get(contract_no=f"HD-{role}")
    assert contract.document_id
    assert client.get(f"/hop-dong/{contract.pk}/sua/").status_code == 200


def test_view_viewer_goi_thang_moi_url_lam_viec_bi_403():
    worker = onboarded("ACTIVE")
    contract = services.add_contract(hr(), worker, **contract_data())
    viewer = login_client(make_user("VIEWER"))
    for url in (
        f"/ho-so/{worker.pk}/lam-viec/thay-doi/",
        f"/ho-so/{worker.pk}/hop-dong/them/",
        f"/hop-dong/{contract.pk}/sua/",
    ):
        assert viewer.get(url).status_code == 403, url
        assert viewer.post(url, {}).status_code == 403, url
    assert (
        viewer.post(f"/ung-tuyen/{make_application(worker).pk}/tiep-nhan/", {}).status_code == 403
    )


def test_view_thay_doi_khong_doi_gi_bao_loi_chung_va_ho_so_luu_tru_403():
    worker = onboarded("ACTIVE")
    emp = Employment.objects.get(worker=worker)
    client = login_client(make_user("ADMIN"))
    same = {
        "effective_date": "01/04/2026",
        "section": emp.section_id,
        "team": emp.team_id,
        "position": emp.position_id,
        "shift": emp.shift_id,
        "manager_code": "",
        "work_status": "ACTIVE",
    }
    response = client.post(f"/ho-so/{worker.pk}/lam-viec/thay-doi/", same)
    assert (
        response.status_code == 200
        and "Không có thay đổi nào để ghi nhận." in response.content.decode()
    )
    archived = make_worker_in_status("ARCHIVED")
    assert client.get(f"/ho-so/{archived.pk}/lam-viec/thay-doi/").status_code == 403


# ----- Tab và danh sách -----
def test_tab_lam_viec_nut_theo_vai_tro_va_lich_su_hien_nguoi_quan_ly_to_ca():
    worker = onboarded("ACTIVE")
    boss = onboarded("ACTIVE")
    change(worker, manager=boss)
    page = login_client(hr()).get(f"/ho-so/{worker.pk}/?tab=lam-viec").content.decode()
    assert "Ghi nhận thay đổi" in page and "Thêm hợp đồng" in page
    assert f"Người quản lý: — → {boss.employee_code}" in page
    viewer = (
        login_client(make_user("VIEWER")).get(f"/ho-so/{worker.pk}/?tab=lam-viec").content.decode()
    )
    assert "Ghi nhận thay đổi" not in viewer and "Thêm hợp đồng" not in viewer


def test_nut_tiep_nhan_chi_hien_khi_dat_va_da_xac_minh():
    worker, app = verified_with_passed()
    page = login_client(hr()).get(f"/ho-so/{worker.pk}/?tab=tuyen-dung").content.decode()
    assert f"/ung-tuyen/{app.pk}/tiep-nhan/" in page and "Tiếp nhận vào làm" in page
    pending = make_worker_in_status("PENDING")
    make_application(pending, "PASSED", result_date=TODAY)
    page = login_client(hr()).get(f"/ho-so/{pending.pk}/?tab=tuyen-dung").content.decode()
    assert "Tiếp nhận vào làm" not in page
    failed = make_worker_in_status("VERIFIED")
    make_application(failed, "FAILED", result_date=TODAY)
    page = login_client(hr()).get(f"/ho-so/{failed.pk}/?tab=tuyen-dung").content.decode()
    assert "Tiếp nhận vào làm" not in page


def test_hop_dong_het_han_sau_20_ngay_co_nhan_sap_het_han_va_loc_danh_sach():
    """Kịch bản 10 ở Phase 6: nhãn ở tab và liên kết ?hop_dong_sap_het_han=1 của thẻ Dashboard."""
    worker = onboarded("ACTIVE")
    soon = TODAY + datetime.timedelta(days=20)
    services.add_contract(
        hr(),
        worker,
        **contract_data(effective_date=soon - datetime.timedelta(days=365), expiry_date=soon),
    )
    other = onboarded("ACTIVE")
    services.add_contract(
        hr(),
        other,
        **contract_data(
            contract_no="HD-XA",
            effective_date=TODAY,
            expiry_date=TODAY + datetime.timedelta(days=400),
        ),
    )
    client = login_client(hr())
    page = client.get(f"/ho-so/{worker.pk}/?tab=lam-viec").content.decode()
    assert "Sắp hết hạn" in page
    other_page = client.get(f"/ho-so/{other.pk}/?tab=lam-viec").content.decode()
    assert "Sắp hết hạn" not in other_page
    listing = client.get("/ho-so/?hop_dong_sap_het_han=1").content.decode()
    assert worker.employee_code in listing and other.employee_code not in listing


def test_ngung_bo_phan_trong_danh_sach_khong_vo_khi_bo_phan_rong():
    worker, app = verified_with_passed()
    services.onboard(hr(), app, **onboard_data())
    page = login_client(hr()).get("/ho-so/").content.decode()
    assert worker.worker_code in page or Worker.objects.get(pk=worker.pk).employee_code in page
    detail = login_client(hr()).get(f"/ho-so/{worker.pk}/?tab=lam-viec").content.decode()
    assert "Chức danh" in detail and "Chờ nhận việc" in detail


def test_next_code_sau_tiep_nhan_khong_cap_lai_ma_da_dung():
    worker, app = verified_with_passed()
    services.onboard(hr(), app, **onboard_data())
    used = Worker.objects.get(pk=worker.pk).employee_code
    assert next_code("EMPLOYEE") != used


# ----- Form điền sẵn giá trị hiện có (hồi quy: view truyền `request.POST or None`) -----
def test_form_tiep_nhan_dien_san_chuc_danh_cua_lan_ung_tuyen():
    worker, app = verified_with_passed()
    page = login_client(hr()).get(f"/ung-tuyen/{app.pk}/tiep-nhan/").content.decode()
    assert f'<option value="{app.position_id}" selected>' in page


def test_form_sua_hop_dong_va_thay_doi_dien_san_gia_tri_hien_co():
    worker = onboarded("ACTIVE")
    contract = services.add_contract(hr(), worker, **contract_data(note="Ghi chú hiện có"))
    client = login_client(hr())
    page = client.get(f"/hop-dong/{contract.pk}/sua/").content.decode()
    assert 'value="HD-2026-001"' in page and "Ghi chú hiện có" in page
    assert 'value="05/03/2026"' in page and 'value="04/03/2027"' in page
    emp = Employment.objects.get(worker=worker)
    page = client.get(f"/ho-so/{worker.pk}/lam-viec/thay-doi/").content.decode()
    assert f'<option value="{emp.position_id}" selected>' in page
    assert '<option value="ACTIVE" selected>' in page


def test_form_sua_ung_tuyen_hoc_van_chung_chi_kinh_nghiem_dien_san():
    from apps.core.models import EducationLevel
    from apps.recruitment import services as rs

    worker = make_worker()
    app = rs.add_application(
        hr(),
        worker,
        position=Position.objects.create(name="Vị trí điền sẵn"),
        source=make_application(make_worker()).source,
        applied_date=D(2026, 3, 1),
        expected_salary=7_500_000,
    )
    edu = rs.add_education(
        hr(),
        worker,
        education_level=EducationLevel.objects.get(rank=4),
        school_name="Trường điền sẵn",
    )
    cert = rs.add_certificate(hr(), worker, name="Chứng chỉ điền sẵn")
    exp = rs.add_work_experience(hr(), worker, company_name="Công ty điền sẵn")
    client = login_client(hr())
    assert 'value="7500000"' in client.get(f"/ung-tuyen/{app.pk}/sua/").content.decode()
    assert 'value="Trường điền sẵn"' in client.get(f"/hoc-van/{edu.pk}/sua/").content.decode()
    assert 'value="Chứng chỉ điền sẵn"' in client.get(f"/chung-chi/{cert.pk}/sua/").content.decode()
    assert 'value="Công ty điền sẵn"' in client.get(f"/kinh-nghiem/{exp.pk}/sua/").content.decode()
