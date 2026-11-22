"""Quản lý tài khoản (chỉ Admin), bảo vệ Admin cuối cùng, phân quyền, nhật ký."""

import datetime

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts import services
from apps.accounts.models import Role, User
from apps.audit.models import AuditLog
from tests.factories import PASSWORD, make_user

pytestmark = pytest.mark.django_db


def login(user):
    client = Client()
    assert (
        client.post("/dang-nhap/", {"username": user.username, "password": PASSWORD}).status_code
        == 302
    )
    return client


# --- phân quyền theo vai trò ---------------------------------------------------------------------
ADMIN_GET = [
    "/tai-khoan/",
    "/tai-khoan/them/",
    "/tai-khoan/lich-su-dang-nhap/",
    "/tai-khoan/{id}/sua/",
]
ADMIN_POST = [
    "/tai-khoan/{id}/khoa/",
    "/tai-khoan/{id}/mo-khoa/",
    "/tai-khoan/{id}/dat-lai-mat-khau/",
]


@pytest.mark.parametrize("role", ["HR_MANAGER", "HR_STAFF", "VIEWER"])
def test_vai_tro_khac_admin_bi_403_o_moi_url_quan_ly_tai_khoan(role):
    target = make_user("HR_STAFF")
    client = login(make_user(role))
    for url in ADMIN_GET:
        assert client.get(url.format(id=target.pk)).status_code == 403, url
    for url in ADMIN_POST:
        assert client.post(url.format(id=target.pk)).status_code == 403, url
        assert client.get(url.format(id=target.pk)).status_code == 403, url
    target.refresh_from_db()
    assert target.is_active
    body = client.get("/tai-khoan/").content.decode()
    assert "Bạn không có quyền thực hiện thao tác này." in body


def test_chua_dang_nhap_chuyen_ve_dang_nhap_o_moi_url_quan_ly():
    target = make_user()
    client = Client()
    for url in ADMIN_GET + ADMIN_POST:
        r = client.get(url.format(id=target.pk))
        assert r.status_code == 302 and r.url.startswith("/dang-nhap/"), url


def test_admin_vao_duoc_va_thay_trang_thai_ba_loai():
    admin = make_user("ADMIN", username="ad")
    make_user(username="khoa", is_active=False)
    tam = make_user(username="tam")
    tam.locked_until = timezone.now() + datetime.timedelta(minutes=10)
    tam.save()
    client = login(admin)
    for url in ("/tai-khoan/", "/tai-khoan/them/", "/tai-khoan/lich-su-dang-nhap/"):
        assert client.get(url).status_code == 200
    body = client.get("/tai-khoan/").content.decode()
    assert "Đang hoạt động" in body and "Bị khóa (Admin khóa)" in body and "Khóa tạm đến" in body


@pytest.mark.parametrize("url", ADMIN_POST)
def test_thao_tac_thay_doi_chi_nhan_post(url):
    admin = make_user("ADMIN")
    target = make_user()
    r = login(admin).get(url.format(id=target.pk))
    assert r.status_code == 405


# --- khóa / mở khóa qua giao diện, kèm nhật ký ------------------------------------------
def test_khoa_tai_khoan_huy_phien_dang_nhap_mo_khoa_khong_song_lai():
    admin = make_user("ADMIN", username="ad")
    target = make_user(username="nv1")
    other = make_user(username="nv2")
    c_target, c_other = login(target), login(other)
    assert c_target.get("/").status_code == 200
    login(admin).post(f"/tai-khoan/{target.pk}/khoa/")
    login(admin).post(f"/tai-khoan/{target.pk}/mo-khoa/")
    assert c_target.get("/").status_code == 302  # phiên cũ đã bị hủy, phải đăng nhập lại
    assert c_other.get("/").status_code == 200  # phiên người khác không bị ảnh hưởng
    assert login(target).get("/").status_code == 200  # đăng nhập mới vẫn được


def test_dat_lai_mat_khau_huy_phien_dang_nhap_cu():
    admin = make_user("ADMIN", username="ad")
    target = make_user(username="nv1")
    c_target = login(target)
    assert c_target.get("/").status_code == 200
    login(admin).post(f"/tai-khoan/{target.pk}/dat-lai-mat-khau/")
    r = c_target.get("/")
    assert r.status_code == 302 and r.url.startswith("/dang-nhap/")


def test_session_engine_la_csdl_vi_end_sessions_phu_thuoc():
    from django.conf import settings

    assert settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"


def test_admin_khoa_va_mo_khoa_ghi_nhat_ky():
    admin = make_user("ADMIN", username="ad")
    target = make_user(username="nv1")
    client = login(admin)
    assert client.post(f"/tai-khoan/{target.pk}/khoa/").status_code == 302
    target.refresh_from_db()
    assert target.is_active is False
    assert client.post(f"/tai-khoan/{target.pk}/mo-khoa/").status_code == 302
    target.refresh_from_db()
    assert target.is_active is True
    actions = list(
        AuditLog.objects.order_by("id").values_list("action", "actor_label", "object_repr")
    )
    assert actions == [("ACCOUNT_LOCK", "ad", "nv1"), ("ACCOUNT_UNLOCK", "ad", "nv1")]


# --- bảo vệ Admin cuối cùng (câu 29), từng trường hợp -------------------------------------
def test_admin_khong_tu_khoa_minh():
    admin = make_user("ADMIN")
    make_user("ADMIN")  # còn Admin khác: vẫn không được tự khóa
    with pytest.raises(services.AccountError, match="chính mình"):
        services.lock_user(admin, admin)
    admin.refresh_from_db()
    assert admin.is_active


def test_admin_khong_tu_doi_vai_tro_cua_minh():
    admin = make_user("ADMIN")
    make_user("ADMIN")
    with pytest.raises(services.AccountError, match="chính mình"):
        services.update_user(admin, admin, full_name="X", role=Role.objects.get(code="VIEWER"))
    admin.refresh_from_db()
    assert admin.role.code == "ADMIN"


def test_admin_tu_sua_ho_ten_van_duoc_khi_giu_nguyen_vai_tro():
    admin = make_user("ADMIN")
    services.update_user(admin, admin, full_name="Họ Tên Mới", role=admin.role)
    admin.refresh_from_db()
    assert admin.full_name == "Họ Tên Mới"


def test_khong_khoa_duoc_admin_cuoi_cung_dang_hoat_dong():
    actor = make_user("ADMIN", is_active=False)  # Admin đã bị khóa không tính là đang hoạt động
    last = make_user("ADMIN", username="cuoi")
    with pytest.raises(services.AccountError, match="ít nhất một Admin đang hoạt động"):
        services.lock_user(actor, last)
    last.refresh_from_db()
    assert last.is_active


def test_khong_ha_vai_tro_admin_cuoi_cung():
    actor = make_user("ADMIN", is_active=False)
    last = make_user("ADMIN", username="cuoi")
    with pytest.raises(services.AccountError, match="ít nhất một Admin đang hoạt động"):
        services.update_user(actor, last, full_name="X", role=Role.objects.get(code="HR_STAFF"))
    last.refresh_from_db()
    assert last.role.code == "ADMIN"


def test_khoa_va_ha_vai_tro_admin_khi_con_admin_khac_thi_duoc():
    a1, a2, a3 = (make_user("ADMIN") for _ in range(3))
    services.lock_user(a1, a2)
    assert not User.objects.get(pk=a2.pk).is_active
    services.update_user(a1, a3, full_name="X", role=Role.objects.get(code="HR_STAFF"))
    assert User.objects.get(pk=a3.pk).role.code == "HR_STAFF"
    # Giờ chỉ còn a1 là Admin hoạt động: không ai khóa/hạ được a1 (a2 bị khóa nên không còn quyền;
    # kiểm tra ở tầng dịch vụ với actor bất kỳ).
    with pytest.raises(services.AccountError):
        services.lock_user(a3, a1)


def test_giao_dien_bao_loi_khi_khoa_chinh_minh():
    admin = make_user("ADMIN")
    client = login(admin)
    r = client.post(f"/tai-khoan/{admin.pk}/khoa/", follow=True)
    assert "Bạn không thể khóa hoặc đổi vai trò của chính mình." in r.content.decode()
    admin.refresh_from_db()
    assert admin.is_active


def test_sua_chinh_minh_o_giao_dien_khoa_o_vai_tro_va_may_chu_van_chan():
    admin = make_user("ADMIN")
    make_user("ADMIN")
    client = login(admin)
    html = client.get(f"/tai-khoan/{admin.pk}/sua/").content.decode()
    assert "disabled" in html.split('name="role"')[1].split(">")[0] or "disabled" in html
    viewer = Role.objects.get(code="VIEWER")
    client.post(f"/tai-khoan/{admin.pk}/sua/", {"full_name": "Tên", "role": viewer.pk})
    admin.refresh_from_db()
    assert admin.role.code == "ADMIN"  # ô vai trò bị khóa nên giá trị gửi lên bị bỏ qua


# --- tạo tài khoản, đặt lại mật khẩu ----------------------------------------------------
def test_tao_tai_khoan_hien_mat_khau_tam_mot_lan_va_ghi_nhat_ky():
    admin = make_user("ADMIN", username="ad")
    client = login(admin)
    role = Role.objects.get(code="HR_STAFF")
    r = client.post(
        "/tai-khoan/them/", {"username": "nv_moi", "full_name": "Người Mới Giả", "role": role.pk}
    )
    assert r.status_code == 200
    temp = r.context["temp"]
    assert temp in r.content.decode()
    user = User.objects.get(username="nv_moi")
    assert user.must_change_password and user.check_password(temp) and user.password != temp
    # Không lọt vào nhật ký, thông báo hay phiên.
    for entry in AuditLog.objects.all():
        assert temp not in f"{entry.note}{entry.changes}{entry.object_repr}"
    assert temp not in str(client.session.items())
    assert temp not in client.get("/tai-khoan/").content.decode()  # trang sau không còn hiện


def test_tao_tai_khoan_trung_ten_bi_tu_choi():
    make_user("ADMIN", username="ad")
    make_user(username="da_co")
    client = login(User.objects.get(username="ad"))
    role = Role.objects.get(code="VIEWER")
    r = client.post("/tai-khoan/them/", {"username": "da_co", "full_name": "X", "role": role.pk})
    assert "Tên đăng nhập này đã có." in r.content.decode()


def test_dat_lai_mat_khau_tam_buoc_doi_va_ghi_nhat_ky():
    admin = make_user("ADMIN", username="ad")
    target = make_user(username="nv1")
    client = login(admin)
    r = client.post(f"/tai-khoan/{target.pk}/dat-lai-mat-khau/")
    temp = r.context["temp"]
    target.refresh_from_db()
    assert target.must_change_password and target.check_password(temp)
    assert not target.check_password(PASSWORD)
    entry = AuditLog.objects.get(action="PASSWORD_RESET")
    assert entry.object_repr == "nv1" and temp not in entry.note


def test_lich_su_dang_nhap_loc_theo_ten_va_ket_qua():
    admin = make_user("ADMIN", username="ad")
    make_user(username="nv1")
    Client().post("/dang-nhap/", {"username": "nv1", "password": "sai1sai1"})
    Client().post("/dang-nhap/", {"username": "nv1", "password": PASSWORD})
    client = login(admin)
    body = client.get("/tai-khoan/lich-su-dang-nhap/?username=nv1&result=fail").content.decode()
    assert body.count("Thất bại") >= 1 and "Thành công</span>" not in body.split("<tbody>")[1]
