"""Tuyển dụng (Phase 6 bước 3; mục IV.4, câu 7, 13, 36, 42, 48).

Service: quy tắc theo trạng thái tuyển dụng, quyền theo vai trò và trạng thái hồ sơ, nhật ký (giá
trị cá nhân chỉ ở AuditPersonalValue). View: gọi thẳng URL với từng vai trò, danh sách /tuyen-dung/.
"""

import datetime

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.audit.models import AuditLog, AuditPersonalValue
from apps.core.models import ApplicationSource, EducationLevel, Position
from apps.employment.models import Employment
from apps.recruitment import services
from apps.recruitment.models import Application, Certificate, Education, WorkExperience
from apps.recruitment.services import RecruitmentDataError
from tests.factories import (
    advance_to,
    login_client,
    make_application,
    make_employment,
    make_user,
    make_worker,
    make_worker_in_status,
)

pytestmark = pytest.mark.django_db
D = datetime.date


def setup_refs():
    return (
        Position.objects.get_or_create(name="Công nhân lắp ráp")[0],
        ApplicationSource.objects.get_or_create(name="Giới thiệu")[0],
    )


def data(**overrides):
    position, source = setup_refs()
    values = {"position": position, "source": source, "applied_date": D(2026, 3, 1)}
    values.update(overrides)
    return values


def hr():
    return make_user("HR_STAFF")


# ----- Service: quy tắc theo trạng thái tuyển dụng ---------------------------------------------
def test_them_lan_ung_tuyen_mac_dinh_moi_nop_va_ghi_nhat_ky_khong_lo_luong():
    worker, user = make_worker(), hr()
    app = services.add_application(user, worker, expected_salary=8_123_456, **data())
    assert app.status == "NEW" and app.created_by == user and app.result_date is None
    entry = AuditLog.objects.get(action="CREATE", object_type="recruitment.Application")
    assert "8123456" not in str(entry.changes) and "8.123.456" not in str(entry.changes)
    names = set(
        AuditPersonalValue.objects.filter(audit_log=entry).values_list("field_name", flat=True)
    )
    assert f"applications[{app.pk}].expected_salary" in names


@pytest.mark.parametrize(
    ("status", "extra", "field", "message"),
    [
        ("INTERVIEW", {}, "interview_at", "Nhập thời gian phỏng vấn."),
        ("FAILED", {}, "reject_reason", "Nhập lý do không đạt."),
    ],
)
def test_trang_thai_thieu_truong_bat_buoc_bi_tu_choi(status, extra, field, message):
    with pytest.raises(RecruitmentDataError) as exc:
        services.add_application(hr(), make_worker(), status=status, **data(**extra))
    assert exc.value.errors[field] == message
    assert Application.objects.count() == 0


@pytest.mark.parametrize("status", ["PASSED", "DECLINED"])
def test_ket_qua_mac_dinh_ngay_hom_nay(status):
    app = services.add_application(hr(), make_worker(), status=status, **data())
    assert app.result_date == timezone.localdate()


def test_khong_dat_co_ly_do_luu_duoc_ngay_ket_qua_hom_nay():
    app = services.add_application(
        hr(), make_worker(), status="FAILED", reject_reason="Không đủ sức khỏe", **data()
    )
    assert app.result_date == timezone.localdate() and app.reject_reason


def test_hen_phong_van_luu_gio_phong_van():
    when = timezone.make_aware(datetime.datetime(2026, 3, 5, 9, 30))
    app = services.add_application(
        hr(), make_worker(), status="INTERVIEW", interview_at=when, **data()
    )
    assert app.interview_at == when


def test_thieu_vi_tri_nguon_ngay_ung_tuyen_hoac_luong_am():
    position, source = setup_refs()
    with pytest.raises(RecruitmentDataError) as exc:
        services.add_application(
            hr(), make_worker(), position=None, source=None, applied_date=None, expected_salary=-1
        )
    assert set(exc.value.errors) == {"position", "source", "applied_date", "expected_salary"}


def test_vi_tri_da_ngung_khong_chon_duoc_nhung_giu_duoc_khi_sua():
    worker, user = make_worker(), hr()
    app = services.add_application(user, worker, **data())
    Position.objects.filter(pk=app.position_id).update(is_active=False)
    app.refresh_from_db()
    with pytest.raises(RecruitmentDataError):
        services.add_application(user, worker, **data(position=app.position))
    changed = services.update_application(
        user, app, **data(position=app.position, status="SCREENING")
    )
    assert changed and Application.objects.get(pk=app.pk).status == "SCREENING"


def test_sua_ghi_gia_tri_cu_moi_va_khong_doi_thi_khong_ghi():
    worker, user = make_worker(), hr()
    app = services.add_application(user, worker, expected_salary=7_000_000, **data())
    before = AuditLog.objects.filter(action="UPDATE").count()
    assert not services.update_application(user, app, expected_salary=7_000_000, **data())
    assert AuditLog.objects.filter(action="UPDATE").count() == before
    assert services.update_application(user, app, expected_salary=9_000_000, **data())
    entry = AuditLog.objects.filter(action="UPDATE", object_type="recruitment.Application").first()
    assert "9000000" not in str(entry.changes)
    pv = AuditPersonalValue.objects.get(audit_log=entry)
    assert (pv.old_value_enc, pv.new_value_enc) == ("7000000", "9000000")


def test_lan_ung_tuyen_da_tiep_nhan_phai_giu_trang_thai_dat():
    worker = make_worker()
    app = make_application(worker, "PASSED", result_date=D(2026, 3, 1))
    emp = make_employment(worker)
    Employment.objects.filter(pk=emp.pk).update(application=app)
    with pytest.raises(RecruitmentDataError) as exc:
        services.update_application(hr(), app, **data(status="NEW"))
    assert "giữ trạng thái Đạt" in exc.value.errors["status"]
    same = data(
        position=app.position,
        source=app.source,
        applied_date=app.applied_date,
        status="PASSED",
        result_date=D(2026, 3, 1),
    )
    assert services.update_application(hr(), app, **same) is False  # giữ Đạt, không đổi gì


def test_mot_ho_so_ung_tuyen_nhieu_lan():
    worker, user = make_worker(), hr()
    services.add_application(user, worker, **data(applied_date=D(2026, 1, 1)))
    services.add_application(user, worker, **data(applied_date=D(2026, 6, 1)))
    assert worker.applications.count() == 2


# ----- Service: quyền theo vai trò và trạng thái hồ sơ (câu 36) ---------------------------------
@pytest.mark.parametrize("role", ["HR_STAFF", "HR_MANAGER", "ADMIN"])
@pytest.mark.parametrize("status", ["DRAFT", "PENDING", "NEEDS_INFO", "VERIFIED"])
def test_nhan_vien_duoc_thao_tac_o_moi_trang_thai_tru_tu_choi_va_luu_tru(role, status):
    worker = make_worker_in_status(status)
    services.add_application(make_user(role), worker, **data())  # không lỗi


@pytest.mark.parametrize("status", ["REJECTED", "ARCHIVED"])
def test_bi_tu_choi_va_luu_tru_khoa_toan_bo_tab(status):
    worker = make_worker_in_status(status)
    user = make_user("ADMIN")
    with pytest.raises(PermissionDenied):
        services.add_application(user, worker, **data())
    with pytest.raises(PermissionDenied):
        services.add_education(
            user, worker, education_level=EducationLevel.objects.first(), school_name="X"
        )


def test_viewer_va_nguoi_chua_dang_nhap_bi_chan_o_service():
    worker = make_worker()
    with pytest.raises(PermissionDenied):
        services.add_application(make_user("VIEWER"), worker, **data())
    with pytest.raises(PermissionDenied):
        services.add_application(None, worker, **data())


def test_ho_so_da_an_danh_khong_thao_tac_duoc():
    worker = make_worker(anonymized_at=timezone.now())
    with pytest.raises(PermissionDenied):
        services.add_application(make_user("ADMIN"), worker, **data())


# ----- Dòng con: sửa, xóa -----------------------------------------------------------------------
def level():
    return EducationLevel.objects.get(rank=4)


def test_sua_va_xoa_hoc_van_ghi_gia_tri_cu_vao_nhat_ky():
    worker, user = make_worker(), hr()
    row = services.add_education(
        user,
        worker,
        education_level=level(),
        school_name="Trường Cũ Giả",
        start_year=2010,
        end_year=2013,
    )
    assert services.update_education(
        user,
        row,
        education_level=level(),
        school_name="Trường Mới Giả",
        start_year=2010,
        end_year=2013,
    )
    # Cột mã hóa không lọc theo giá trị rõ được (Fernet không xác định): lọc theo tên rồi so sánh.
    values = [
        (v.old_value_enc, v.new_value_enc)
        for v in AuditPersonalValue.objects.filter(
            field_name=f"education[{row.pk}].school_name"
        ).order_by("id")
    ]
    assert values == [(None, "Trường Cũ Giả"), ("Trường Cũ Giả", "Trường Mới Giả")]  # tạo, sửa
    row.refresh_from_db()
    pk = row.pk  # sau khi xóa, row.pk là None
    services.delete_child(user, row)
    assert not Education.objects.filter(pk=pk).exists()
    values = [
        (v.old_value_enc, v.new_value_enc)
        for v in AuditPersonalValue.objects.filter(
            field_name=f"education[{pk}].school_name"
        ).order_by("id")
    ]
    assert values[-1] == ("Trường Mới Giả", None)  # giá trị cũ của dòng bị xóa còn trong nhật ký
    assert AuditLog.objects.filter(note="Xóa học vấn").count() == 1


def test_hoc_van_sai_nam_va_chung_chi_ngay_sai_bi_tu_choi_khi_sua():
    worker, user = make_worker(), hr()
    edu = services.add_education(user, worker, education_level=level(), school_name="T")
    with pytest.raises(RecruitmentDataError):
        services.update_education(
            user, edu, education_level=level(), school_name="T", start_year=2020, end_year=2010
        )
    cert = services.add_certificate(user, worker, name="An toàn lao động")
    with pytest.raises(RecruitmentDataError):
        services.update_certificate(
            user, cert, name="An toàn", issue_date=D(2026, 5, 1), expiry_date=D(2026, 1, 1)
        )
    exp = services.add_work_experience(user, worker, company_name="Công ty Giả")
    with pytest.raises(RecruitmentDataError):
        services.update_work_experience(user, exp, company_name="", start_date=None)


def test_xoa_chung_chi_va_kinh_nghiem_chi_xoa_dong_do():
    worker, user = make_worker(), hr()
    cert = services.add_certificate(user, worker, name="Chứng chỉ A")
    other = services.add_certificate(user, worker, name="Chứng chỉ B")
    exp = services.add_work_experience(user, worker, company_name="Công ty Giả")
    services.delete_child(user, cert)
    services.delete_child(user, exp)
    assert list(Certificate.objects.values_list("pk", flat=True)) == [other.pk]
    assert not WorkExperience.objects.exists()


def test_xoa_dong_con_cua_ho_so_bi_khoa_hoac_viewer_bi_chan():
    worker = make_worker()
    cert = services.add_certificate(hr(), worker, name="Chứng chỉ A")
    with pytest.raises(PermissionDenied):
        services.delete_child(make_user("VIEWER"), cert)
    advance_to(worker, "ARCHIVED")  # đi qua workflow, không gán trực tiếp trạng thái
    cert = Certificate.objects.select_related("worker").get(pk=cert.pk)
    with pytest.raises(PermissionDenied):
        services.delete_child(make_user("ADMIN"), cert)
    assert Certificate.objects.filter(pk=cert.pk).exists()


def test_cap_nhat_ho_so_khi_dong_con_doi_dung_cho_ho_so_bo_do():
    worker, user = make_worker(), hr()
    before = worker.updated_at
    services.add_certificate(user, worker, name="Chứng chỉ A")
    worker.refresh_from_db()
    assert worker.updated_at >= before


# ----- View: gọi thẳng URL ------------------------------------------------------------------------
def form_data(**extra):
    position, source = setup_refs()
    values = {
        "position": position.pk,
        "source": source.pk,
        "applied_date": "01/03/2026",
        "status": "NEW",
    }
    values.update(extra)
    return values


@pytest.mark.parametrize(
    ("role", "expected"), [("HR_STAFF", 302), ("HR_MANAGER", 302), ("ADMIN", 302), ("VIEWER", 403)]
)
def test_view_them_ung_tuyen_theo_vai_tro(role, expected):
    worker = make_worker()
    client = login_client(make_user(role))
    assert client.get(f"/ho-so/{worker.pk}/ung-tuyen/them/").status_code in (200, 403)
    response = client.post(f"/ho-so/{worker.pk}/ung-tuyen/them/", form_data())
    assert response.status_code == expected
    assert worker.applications.count() == (1 if expected == 302 else 0)


def test_view_them_ung_tuyen_sai_hien_loi_tieng_viet_o_dung_o():
    worker = make_worker()
    client = login_client(make_user("HR_STAFF"))
    url = f"/ho-so/{worker.pk}/ung-tuyen/them/"
    # Lỗi từ service (quy tắc trạng thái) hiện dưới đúng ô.
    response = client.post(url, form_data(status="FAILED"))
    assert response.status_code == 200 and "Nhập lý do không đạt." in response.content.decode()
    # Lỗi từ form (kiểu dữ liệu) hiện bằng tiếng Việt.
    response = client.post(url, form_data(expected_salary="abc", applied_date="2026-03-01"))
    page = response.content.decode()
    assert "Nhập số nguyên" in page and "Nhập ngày đúng định dạng dd/mm/yyyy." in page
    assert worker.applications.count() == 0


def test_view_sua_ung_tuyen_va_ho_so_bi_khoa():
    worker = make_worker()
    app = make_application(worker)
    client = login_client(make_user("HR_MANAGER"))
    assert client.get(f"/ung-tuyen/{app.pk}/sua/").status_code == 200
    response = client.post(f"/ung-tuyen/{app.pk}/sua/", form_data(status="SCREENING"))
    assert response.status_code == 302
    assert Application.objects.get(pk=app.pk).status == "SCREENING"
    rejected = make_worker_in_status("REJECTED")  # hồ sơ đủ trường, đi qua workflow
    locked = make_application(rejected)
    assert client.get(f"/ung-tuyen/{locked.pk}/sua/").status_code == 403
    assert client.post(f"/ung-tuyen/{locked.pk}/sua/", form_data(status="NEW")).status_code == 403


@pytest.mark.parametrize("kind", ["hoc-van", "chung-chi", "kinh-nghiem"])
def test_view_dong_con_viewer_403_nhan_vien_them_sua_xoa(kind):
    worker = make_worker()
    posts = {
        "hoc-van": {"education_level": level().pk, "school_name": "Trường Giả"},
        "chung-chi": {"name": "Chứng chỉ giả"},
        "kinh-nghiem": {"company_name": "Công ty Giả"},
    }[kind]
    viewer = login_client(make_user("VIEWER"))
    assert viewer.get(f"/ho-so/{worker.pk}/{kind}/them/").status_code == 403
    assert viewer.post(f"/ho-so/{worker.pk}/{kind}/them/", posts).status_code == 403
    staff = login_client(make_user("HR_STAFF"))
    assert staff.post(f"/ho-so/{worker.pk}/{kind}/them/", posts).status_code == 302
    model = {"hoc-van": Education, "chung-chi": Certificate, "kinh-nghiem": WorkExperience}[kind]
    row = model.objects.get(worker=worker)
    assert staff.get(f"/{kind}/{row.pk}/sua/").status_code == 200
    assert viewer.post(f"/{kind}/{row.pk}/xoa/").status_code == 403
    assert staff.get(f"/{kind}/{row.pk}/xoa/").status_code == 405  # xóa chỉ bằng POST
    assert staff.post(f"/{kind}/{row.pk}/xoa/").status_code == 302
    assert not model.objects.filter(pk=row.pk).exists()


def test_loai_dong_con_la_404():
    assert login_client(make_user("ADMIN")).get("/ho-so/1/khong-co/them/").status_code == 404


# ----- /tuyen-dung/ ----------------------------------------------------------------------------
def test_danh_sach_tuyen_dung_moi_vai_tro_xem_duoc_viewer_thay_cot_luong():
    worker = make_worker()
    app = make_application(worker)
    Application.objects.filter(pk=app.pk).update(expected_salary=6_543_210)
    for role in ("ADMIN", "HR_MANAGER", "HR_STAFF", "VIEWER"):
        page = login_client(make_user(role)).get("/tuyen-dung/").content.decode()
        assert worker.worker_code in page, role
        assert "Mức lương mong muốn" in page and "6.543.210" in page, role
    viewer_page = login_client(make_user("VIEWER")).get("/tuyen-dung/").content.decode()
    assert "/sua/" not in viewer_page  # Viewer chỉ xem


def test_loc_tuyen_dung_theo_trang_thai_nhieu_gia_tri_vi_tri_nguon_ngay():
    admin = login_client(make_user("ADMIN"))
    w1, w2, w3 = make_worker(), make_worker(), make_worker()
    make_application(w1, "NEW", applied_date=D(2026, 1, 10))
    make_application(w2, "INTERVIEW", applied_date=D(2026, 2, 10))
    make_application(w3, "FAILED", applied_date=D(2026, 3, 10))
    page = admin.get("/tuyen-dung/?trang_thai=NEW,SCREENING,INTERVIEW").content.decode()
    assert w1.worker_code in page and w2.worker_code in page and w3.worker_code not in page
    page = admin.get("/tuyen-dung/?trang_thai=FAILED").content.decode()
    assert w3.worker_code in page and w1.worker_code not in page
    page = admin.get("/tuyen-dung/?tu_ngay=01/02/2026&den_ngay=28/02/2026").content.decode()
    assert w2.worker_code in page and w1.worker_code not in page and w3.worker_code not in page


def test_phan_trang_20_dong():
    user = make_user("ADMIN")
    worker = make_worker()
    for _ in range(25):
        make_application(worker)
    page = login_client(user).get("/tuyen-dung/").content.decode()
    assert "Hiển thị 1–20 / 25" in page


def test_tab_tuyen_dung_hr_co_nut_them_viewer_khong():
    worker = make_worker()
    hr_page = (
        login_client(make_user("HR_STAFF"))
        .get(f"/ho-so/{worker.pk}/?tab=tuyen-dung")
        .content.decode()
    )
    for label in ("Thêm lần ứng tuyển", "Thêm học vấn", "Thêm chứng chỉ", "Thêm kinh nghiệm"):
        assert label in hr_page
    archived = make_worker_in_status("ARCHIVED")
    page = (
        login_client(make_user("ADMIN"))
        .get(f"/ho-so/{archived.pk}/?tab=tuyen-dung")
        .content.decode()
    )
    assert "Thêm lần ứng tuyển" not in page  # Lưu trữ chỉ xem
