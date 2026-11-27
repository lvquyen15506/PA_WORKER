"""Sau bàn giao v1.1.1: làm dễ thấy chức năng công ty khách (Phase 6).

1. Sidebar có mục "Công ty khách" (A, Q); Q chỉ xem danh mục này, thêm/sửa/ngừng chỉ A.
2. Tab Quá trình làm việc: chưa có mã NV thì hướng dẫn Tiếp nhận vào làm (+ nút khi đủ điều kiện).
3. Form Tiếp nhận vào làm: phần không bắt buộc "Gán công ty khách ngay", tạo đợt trong cùng
   giao dịch qua add_assignment.
4. Form Thêm đợt: danh mục trống thì hướng dẫn; liên kết thêm công ty chỉ với Admin.
5. Danh sách /ho-so/: chưa có đợt đang diễn ra thì cột Công ty khách hiện "Chưa gán".
"""

import datetime

import pytest

from apps.audit.models import AuditLog
from apps.core.context_processors import build_menu
from apps.core.models import ClientCompany, Department, Position
from apps.employment import services
from apps.employment.models import Employment, EmploymentHistory, WorkAssignment
from apps.employment.services import EmploymentError
from apps.workers.models import Worker
from tests.factories import (
    login_client,
    make_application,
    make_employment,
    make_user,
    make_worker,
    make_worker_in_status,
)

pytestmark = pytest.mark.django_db
D = datetime.date
TODAY = datetime.date.today()
CC_URL = "/cai-dat/danh-muc/cong-ty-khach/"


def company(name="Công ty Mẫu A", location="Tỉnh Một", active=True):
    return ClientCompany.objects.get_or_create(
        name=name, location=location, defaults={"is_active": active}
    )[0]


def position():
    return Position.objects.get_or_create(name="Công nhân lắp ráp")[0]


def verified_with_passed():
    worker = make_worker_in_status("VERIFIED")
    app = make_application(worker, "PASSED", result_date=TODAY)
    return worker, app


def onboard_post(**extra):
    data = {"received_date": "01/03/2026", "start_date": "05/03/2026", "position": position().pk}
    data.update(extra)
    return data


# ----- 1. Sidebar và quyền xem danh mục công ty khách -----
@pytest.mark.parametrize(
    ("role", "shown"),
    [("ADMIN", True), ("HR_MANAGER", True), ("HR_STAFF", False), ("VIEWER", False)],
)
def test_sidebar_co_muc_cong_ty_khach_cho_a_va_q(role, shown):
    urls = [item["url"] for item in build_menu(role, "/")]
    assert (CC_URL in urls) == shown


def test_muc_cong_ty_khach_dang_chon_khi_mo_trang_do_khong_phai_cai_dat():
    menu = {i["url"]: i["active"] for i in build_menu("ADMIN", CC_URL)}
    assert menu[CC_URL] is True and menu["/cai-dat/"] is False


@pytest.mark.parametrize(
    ("role", "status"),
    [("ADMIN", 200), ("HR_MANAGER", 200), ("HR_STAFF", 403), ("VIEWER", 403)],
)
def test_xem_danh_muc_cong_ty_khach_theo_vai_tro(role, status):
    company()
    response = login_client(make_user(role)).get(CC_URL)
    assert response.status_code == status
    if status == 200:
        assert "Công ty Mẫu A" in response.content.decode()


def test_quan_ly_chi_xem_khong_co_nut_them_sua_ngung_va_tab_cai_dat():
    obj = company()
    page = login_client(make_user("HR_MANAGER")).get(CC_URL).content.decode()
    assert "Công ty Mẫu A" in page and "Danh sách chỉ xem" in page
    assert f"{CC_URL}them/" not in page
    assert f"{CC_URL}{obj.pk}/sua/" not in page
    assert f"{CC_URL}{obj.pk}/ngung/" not in page
    assert "/cai-dat/sinh-ma/" not in page  # không có tab Cài đặt


def test_admin_van_thay_day_du_thao_tac():
    obj = company()
    page = login_client(make_user("ADMIN")).get(CC_URL).content.decode()
    assert f"{CC_URL}them/" in page and f"{CC_URL}{obj.pk}/sua/" in page


def test_quan_ly_khong_xem_duoc_danh_muc_khac():
    client = login_client(make_user("HR_MANAGER"))
    assert client.get("/cai-dat/danh-muc/phong-ban/").status_code == 403


def test_quan_ly_khong_them_sua_ngung_duoc_cong_ty_khach():
    obj = company()
    client = login_client(make_user("HR_MANAGER"))
    assert client.get(f"{CC_URL}them/").status_code == 403
    response = client.post(f"{CC_URL}them/", {"name": "Công ty Mẫu B", "location": "Tỉnh Hai"})
    assert response.status_code == 403
    assert not ClientCompany.objects.filter(name="Công ty Mẫu B").exists()
    assert client.post(f"{CC_URL}{obj.pk}/sua/", {"name": "X", "location": "Y"}).status_code == 403
    assert client.post(f"{CC_URL}{obj.pk}/ngung/").status_code == 403
    obj.refresh_from_db()
    assert obj.name == "Công ty Mẫu A" and obj.is_active


def test_admin_them_cong_ty_khach_ghi_nhat_ky():
    client = login_client(make_user("ADMIN"))
    response = client.post(f"{CC_URL}them/", {"name": "Công ty Mẫu C", "location": "Tỉnh Ba"})
    assert response.status_code == 302
    obj = ClientCompany.objects.get(name="Công ty Mẫu C")
    assert AuditLog.objects.filter(action="CREATE", object_id=str(obj.pk)).exists()


# ----- 2. Tab Quá trình làm việc khi chưa có mã NV -----
TAB_TEXT = "Muốn gán công ty khách, cần Tiếp nhận vào làm trước"


def tab(worker, role="HR_STAFF"):
    client = login_client(make_user(role))
    return client.get(f"/ho-so/{worker.pk}/?tab=lam-viec").content.decode()


def test_tab_chua_co_ma_nv_hien_huong_dan_va_nut_khi_du_dieu_kien():
    worker, app = verified_with_passed()
    page = tab(worker)
    assert TAB_TEXT in page and "Đạt" in page and "Đã xác minh" in page
    assert f"/ung-tuyen/{app.pk}/tiep-nhan/" in page


def test_tab_chua_du_dieu_kien_chi_hien_huong_dan_khong_co_nut():
    worker = make_worker_in_status("PENDING")
    app = make_application(worker, "PASSED", result_date=TODAY)
    page = tab(worker)
    assert TAB_TEXT in page
    assert f"/ung-tuyen/{app.pk}/tiep-nhan/" not in page


def test_tab_viewer_thay_huong_dan_nhung_khong_co_nut():
    worker, app = verified_with_passed()
    page = tab(worker, "VIEWER")
    assert TAB_TEXT in page
    assert f"/ung-tuyen/{app.pk}/tiep-nhan/" not in page


def test_tab_da_co_ma_nv_khong_hien_huong_dan():
    worker = make_worker()
    make_employment(worker, "ACTIVE")
    Worker.objects.filter(pk=worker.pk).update(employee_code=f"CN-V{worker.pk:05d}")
    assert TAB_TEXT not in tab(worker)


# ----- 3. Tiếp nhận + gán công ty khách ngay (cùng giao dịch) -----
def test_tiep_nhan_khong_gan_cong_ty_van_nhu_cu():
    worker, app = verified_with_passed()
    client = login_client(make_user("HR_STAFF"))
    page = client.get(f"/ung-tuyen/{app.pk}/tiep-nhan/").content.decode()
    assert "Gán công ty khách ngay (không bắt buộc)" in page
    assert client.post(f"/ung-tuyen/{app.pk}/tiep-nhan/", onboard_post()).status_code == 302
    assert Employment.objects.filter(worker=worker).exists()
    assert not WorkAssignment.objects.filter(worker=worker).exists()


def test_tiep_nhan_co_gan_cong_ty_tao_dot_va_ghi_nhat_ky():
    worker, app = verified_with_passed()
    cc = company()
    client = login_client(make_user("HR_STAFF"))
    response = client.post(
        f"/ung-tuyen/{app.pk}/tiep-nhan/",
        onboard_post(
            assign_client_company=cc.pk,
            assign_position=position().pk,
            assign_start_date="05/03/2026",
        ),
    )
    assert response.status_code == 302
    worker.refresh_from_db()
    assert worker.employee_code
    asg = WorkAssignment.objects.get(worker=worker)
    assert asg.client_company == cc and asg.start_date == D(2026, 3, 5) and asg.end_date is None
    assert AuditLog.objects.filter(action="CREATE", note="Thêm đợt làm việc").exists()


@pytest.mark.parametrize(
    ("extra", "field_msg"),
    [
        ({"assign_position": "P", "assign_start_date": "05/03/2026"}, "Chọn công ty khách hàng"),
        ({"assign_client_company": "C"}, "Chọn vị trí tại công ty khách."),
        ({"assign_client_company": "C", "assign_position": "P"}, "Nhập ngày bắt đầu tại công ty"),
    ],
)
def test_form_gan_cong_ty_thieu_truong_bao_loi_khong_luu_gi(extra, field_msg):
    worker, app = verified_with_passed()
    cc, pos = company(), position()
    data = {k: {"C": cc.pk, "P": pos.pk}.get(v, v) for k, v in extra.items()}
    client = login_client(make_user("HR_STAFF"))
    response = client.post(f"/ung-tuyen/{app.pk}/tiep-nhan/", onboard_post(**data))
    assert response.status_code == 200
    assert field_msg in response.content.decode()
    assert not Employment.objects.filter(worker=worker).exists()
    worker.refresh_from_db()
    assert not worker.employee_code


def test_loi_dot_lam_viec_huy_ca_tiep_nhan_trong_cung_giao_dich():
    """Đợt sai (ngày kết thúc dù có — ở đây: công ty đã ngừng) -> không tạo gì, không cấp mã."""
    worker, app = verified_with_passed()
    stopped = company("Công ty Ngừng", active=False)
    with pytest.raises(EmploymentError) as exc:
        services.onboard(
            make_user("HR_STAFF"),
            app,
            received_date=D(2026, 3, 1),
            start_date=D(2026, 3, 5),
            position=position(),
            assignment={
                "client_company": stopped,
                "position": position(),
                "start_date": D(2026, 3, 5),
            },
        )
    assert "assign_client_company" in exc.value.errors
    worker.refresh_from_db()
    assert not worker.employee_code
    assert not Employment.objects.filter(worker=worker).exists()
    assert not EmploymentHistory.objects.filter(worker=worker).exists()
    assert not WorkAssignment.objects.filter(worker=worker).exists()


def test_form_tiep_nhan_chi_liet_ke_cong_ty_dang_dung():
    worker, app = verified_with_passed()
    company("Công ty Đang Dùng")
    company("Công ty Đã Ngừng", active=False)
    page = login_client(make_user("HR_STAFF")).get(f"/ung-tuyen/{app.pk}/tiep-nhan/")
    page = page.content.decode()
    assert "Công ty Đang Dùng" in page and "Công ty Đã Ngừng" not in page


def test_viewer_khong_tiep_nhan_va_khong_gan_duoc():
    worker, app = verified_with_passed()
    cc = company()
    response = login_client(make_user("VIEWER")).post(
        f"/ung-tuyen/{app.pk}/tiep-nhan/",
        onboard_post(
            assign_client_company=cc.pk,
            assign_position=position().pk,
            assign_start_date="05/03/2026",
        ),
    )
    assert response.status_code == 403
    assert not WorkAssignment.objects.exists()


# ----- 4. Form Thêm đợt khi danh mục công ty khách trống -----
def employee():
    worker = make_worker()
    make_employment(worker, "ACTIVE")
    Worker.objects.filter(pk=worker.pk).update(employee_code=f"CN-W{worker.pk:05d}")
    return worker


EMPTY_TEXT = "Danh mục công ty khách hàng chưa có công ty nào đang sử dụng."


@pytest.mark.parametrize(
    ("role", "link"), [("ADMIN", True), ("HR_MANAGER", False), ("HR_STAFF", False)]
)
def test_them_dot_khi_danh_muc_trong_hien_huong_dan_lien_ket_chi_admin(role, link):
    company("Công ty Đã Ngừng", active=False)  # chỉ có công ty đã ngừng = coi như trống
    worker = employee()
    page = login_client(make_user(role)).get(f"/ho-so/{worker.pk}/dot-lam-viec/them/")
    page = page.content.decode()
    assert EMPTY_TEXT in page
    assert (f"{CC_URL}them/" in page) == link


def test_them_dot_khi_co_cong_ty_khong_hien_huong_dan():
    company()
    worker = employee()
    page = login_client(make_user("ADMIN")).get(f"/ho-so/{worker.pk}/dot-lam-viec/them/")
    assert EMPTY_TEXT not in page.content.decode()


# ----- 5. Danh sách /ho-so/: "Chưa gán" -----
def test_danh_sach_cot_cong_ty_khach_trong_hien_chua_gan():
    from apps.employment.assignments import add_assignment

    Department.objects.get_or_create(name="PB Mẫu")
    free = make_worker(full_name="Giả Tự Do")
    assigned = employee()
    add_assignment(
        make_user("HR_STAFF"),
        assigned,
        client_company=company("Công ty Mẫu Gán"),
        position=position(),
        start_date=TODAY - datetime.timedelta(days=5),
    )
    response = login_client(make_user("HR_STAFF")).get("/ho-so/?reset=1", follow=True)
    page = response.content.decode()
    assert free.full_name in page and assigned.worker_code
    # Mỗi dòng một ô Công ty khách: một dòng "Chưa gán", một dòng tên công ty.
    import re

    cells = [c.strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", page, re.S)]
    assert cells.count("Chưa gán") == 1
    assert "Công ty Mẫu Gán" in page
