"""Đăng nhập, khóa tạm 5 lần sai / 15 phút, Admin khóa, tự đăng xuất, buộc đổi mật khẩu."""

import datetime

import pytest
from django.contrib.sessions.models import Session
from django.test import Client
from django.utils import timezone

from apps.accounts.models import LoginHistory, User
from apps.accounts.services import (
    MSG_ADMIN_LOCKED,
    MSG_BAD_CREDENTIALS,
    generate_temp_password,
    unlock_user,
)
from tests.factories import PASSWORD, make_user

pytestmark = pytest.mark.django_db

NOW = timezone.make_aware(datetime.datetime(2026, 11, 22, 9, 0, 0))


@pytest.fixture
def clock(monkeypatch):
    """Đồng hồ giả điều khiển được: clock.advance(minutes=...)."""

    class Clock:
        now = NOW

        def advance(self, **kw):
            self.now += datetime.timedelta(**kw)

    c = Clock()
    monkeypatch.setattr(timezone, "now", lambda: c.now)
    return c


def post_login(client, username, password):
    return client.post("/dang-nhap/", {"username": username, "password": password})


def test_dang_nhap_dung_vao_trang_chu_va_ghi_lich_su():
    user = make_user(username="hr1")
    client = Client()
    r = post_login(client, "hr1", PASSWORD)
    assert r.status_code == 302 and r.url == "/"
    assert client.get("/").status_code == 200
    h = LoginHistory.objects.get()
    assert (h.user, h.success, h.failure_reason, h.username_attempted) == (user, True, "", "hr1")


def test_sai_mat_khau_thong_bao_chung_va_ghi_lich_su():
    make_user(username="hr1")
    r = post_login(Client(), "hr1", "sai-mat-khau1")
    assert r.status_code == 200 and MSG_BAD_CREDENTIALS in r.content.decode()
    h = LoginHistory.objects.get()
    assert (h.success, h.failure_reason) == (False, "Sai mật khẩu")


def test_ten_khong_ton_tai_cung_thong_bao_chung_user_null():
    r = post_login(Client(), "khong_co", "xyz12345")
    assert MSG_BAD_CREDENTIALS in r.content.decode()
    h = LoginHistory.objects.get()
    assert h.user is None and h.username_attempted == "khong_co" and not h.success


def test_sau_4_lan_sai_chua_khoa_lan_5_khoa_15_phut(clock):
    user = make_user(username="hr1")
    for _ in range(4):
        r = post_login(Client(), "hr1", "sai1sai1")
        assert MSG_BAD_CREDENTIALS in r.content.decode()
    user.refresh_from_db()
    assert user.failed_login_count == 4 and user.locked_until is None
    r = post_login(Client(), "hr1", "sai1sai1")  # lần 5
    user.refresh_from_db()
    assert user.locked_until == clock.now + datetime.timedelta(minutes=15)
    assert "tạm khóa do nhập sai nhiều lần. Thử lại sau 09:15." in r.content.decode()


def test_trong_luc_khoa_tam_mat_khau_dung_van_bi_chan_va_ghi_lich_su(clock):
    make_user(username="hr1")
    for _ in range(5):
        post_login(Client(), "hr1", "sai1sai1")
    clock.advance(minutes=14, seconds=59)
    r = post_login(Client(), "hr1", PASSWORD)
    assert "Thử lại sau 09:15" in r.content.decode()
    last = LoginHistory.objects.order_by("-id").first()
    assert (last.success, last.failure_reason) == (False, "Tài khoản đang khóa tạm")


def test_khoa_tam_tu_het_sau_15_phut_va_dem_ve_0(clock):
    user = make_user(username="hr1")
    for _ in range(5):
        post_login(Client(), "hr1", "sai1sai1")
    clock.advance(minutes=15)
    client = Client()
    assert post_login(client, "hr1", PASSWORD).status_code == 302
    user.refresh_from_db()
    assert user.failed_login_count == 0 and user.locked_until is None


def test_dang_nhap_dung_giua_chung_reset_bo_dem():
    user = make_user(username="hr1")
    for _ in range(3):
        post_login(Client(), "hr1", "sai1sai1")
    post_login(Client(), "hr1", PASSWORD)
    user.refresh_from_db()
    assert user.failed_login_count == 0
    for _ in range(4):  # lại sai 4 lần: chưa khóa
        post_login(Client(), "hr1", "sai1sai1")
    user.refresh_from_db()
    assert user.locked_until is None and user.failed_login_count == 4


def test_het_han_khoa_tam_sai_tiep_dem_lai_tu_1(clock):
    user = make_user(username="hr1")
    for _ in range(5):
        post_login(Client(), "hr1", "sai1sai1")
    clock.advance(minutes=16)
    post_login(Client(), "hr1", "sai1sai1")
    user.refresh_from_db()
    assert user.failed_login_count == 1 and user.locked_until is None


def test_admin_khoa_khong_dang_nhap_duoc_thong_bao_rieng():
    make_user(username="hr1", is_active=False)
    r = post_login(Client(), "hr1", PASSWORD)
    assert MSG_ADMIN_LOCKED in r.content.decode()
    assert LoginHistory.objects.get().failure_reason == "Tài khoản bị Admin khóa"


def test_admin_mo_khoa_duoc_ca_hai_kieu_khoa(clock):
    admin = make_user("ADMIN", username="ad")
    tam = make_user(username="tam")
    for _ in range(5):
        post_login(Client(), "tam", "sai1sai1")
    unlock_user(admin, tam)
    assert post_login(Client(), "tam", PASSWORD).status_code == 302
    cung = make_user(username="cung", is_active=False)
    cung.failed_login_count, cung.locked_until = 5, clock.now + datetime.timedelta(minutes=5)
    cung.save()
    unlock_user(admin, cung)
    cung.refresh_from_db()
    assert (cung.is_active, cung.locked_until, cung.failed_login_count) == (True, None, 0)
    assert post_login(Client(), "cung", PASSWORD).status_code == 302


def test_dang_nhap_dang_hoat_dong_bi_khoa_giua_phien_thi_bi_dang_xuat():
    user = make_user(username="hr1")
    client = Client()
    post_login(client, "hr1", PASSWORD)
    assert client.get("/").status_code == 200
    User.objects.filter(pk=user.pk).update(is_active=False)
    assert client.get("/").status_code == 302  # về trang đăng nhập


def test_phien_30_phut_tu_dang_xuat_va_gia_han_moi_request():
    make_user(username="hr1")
    client = Client()
    post_login(client, "hr1", PASSWORD)
    client.get("/")
    assert client.session.get_expiry_age() == 1800
    # Mỗi request kéo dài phiên thêm 30 phút từ lúc đó.
    s = Session.objects.get()
    s.expire_date = timezone.now() + datetime.timedelta(minutes=5)
    s.save()
    client.get("/")
    assert Session.objects.get().expire_date > timezone.now() + datetime.timedelta(minutes=29)
    # Quá hạn: bị yêu cầu đăng nhập lại.
    Session.objects.update(expire_date=timezone.now() - datetime.timedelta(minutes=1))
    r = client.get("/")
    assert r.status_code == 302 and r.url.startswith("/dang-nhap/")


def test_chua_dang_nhap_bi_chuyen_ve_dang_nhap_kem_next():
    r = Client().get("/tai-khoan/")
    assert r.status_code == 302 and r.url == "/dang-nhap/?next=/tai-khoan/"


def test_next_ngoai_trang_bi_bo():
    make_user(username="hr1")
    r = Client().post(
        "/dang-nhap/?next=https://evil.example", {"username": "hr1", "password": PASSWORD}
    )
    assert r.url == "/"


def test_must_change_password_chuyen_huong_moi_url_tru_dang_xuat():
    make_user(username="moi", must_change=True)
    client = Client()
    post_login(client, "moi", PASSWORD)
    for url in ("/", "/gioi-thieu/", "/tai-khoan/", "/tai-khoan/lich-su-dang-nhap/"):
        r = client.get(url)
        assert r.status_code == 302 and r.url == "/doi-mat-khau/", url
    assert client.get("/doi-mat-khau/").status_code == 200
    assert client.post("/dang-xuat/").status_code == 302


def test_doi_mat_khau_lan_dau_bo_co_bat_buoc_va_khong_bi_dang_xuat():
    user = make_user(username="moi", must_change=True)
    client = Client()
    post_login(client, "moi", PASSWORD)
    r = client.post(
        "/doi-mat-khau/",
        {
            "old_password": PASSWORD,
            "new_password1": "MatKhauMoi99",
            "new_password2": "MatKhauMoi99",
        },
    )
    assert r.status_code == 302 and r.url == "/"
    user.refresh_from_db()
    assert user.must_change_password is False and user.check_password("MatKhauMoi99")
    assert client.get("/").status_code == 200


@pytest.mark.parametrize(
    "mat_khau, thong_bao",
    [
        ("Ab1", "quá ngắn"),
        ("chuoichuoichuoi", "cả chữ và số"),
        ("12345678901", "cả chữ và số"),
        ("Mk123456a", "phải khác"),
    ],
)
def test_doi_mat_khau_yeu_bi_tu_choi(mat_khau, thong_bao):
    user = make_user(username="moi", must_change=True)
    client = Client()
    post_login(client, "moi", PASSWORD)
    r = client.post(
        "/doi-mat-khau/",
        {"old_password": PASSWORD, "new_password1": mat_khau, "new_password2": mat_khau},
    )
    assert r.status_code == 200 and thong_bao in r.content.decode()
    user.refresh_from_db()
    assert user.must_change_password is True and user.check_password(PASSWORD)


def test_sai_mat_khau_hien_tai_khi_doi():
    make_user(username="moi", must_change=True)
    client = Client()
    post_login(client, "moi", PASSWORD)
    r = client.post(
        "/doi-mat-khau/",
        {
            "old_password": "khong-dung1",
            "new_password1": "MatKhauMoi99",
            "new_password2": "MatKhauMoi99",
        },
    )
    assert "Mật khẩu hiện tại không đúng." in r.content.decode()


def test_dang_xuat_chi_nhan_post():
    make_user(username="hr1")
    client = Client()
    post_login(client, "hr1", PASSWORD)
    assert client.get("/dang-xuat/").status_code == 405
    assert client.post("/dang-xuat/").status_code == 302
    assert client.get("/").status_code == 302


def test_mat_khau_tam_sinh_ngau_nhien_dat_yeu_cau():
    seen = {generate_temp_password() for _ in range(50)}
    assert len(seen) == 50
    from apps.accounts.validators import LetterAndDigitValidator

    for p in seen:
        assert len(p) == 12
        LetterAndDigitValidator().validate(p)
        assert not set("lIO01") & set(p)
