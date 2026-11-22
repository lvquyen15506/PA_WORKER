"""Kiểm tra cấu hình nền (Phase 2, bước 1)."""

import pytest
from django.conf import settings
from django.urls import Resolver404, resolve


def test_allowed_hosts_khong_co_dau_sao():
    assert "*" not in settings.ALLOWED_HOSTS


def test_ngon_ngu_va_mui_gio():
    assert settings.LANGUAGE_CODE == "vi"
    assert settings.TIME_ZONE == "Asia/Ho_Chi_Minh"


def test_django_admin_khong_bat():
    assert "django.contrib.admin" not in settings.INSTALLED_APPS


def test_admin_url_khong_ton_tai():
    with pytest.raises(Resolver404):
        resolve("/admin/")


def test_phien_30_phut_va_gia_han_moi_request():
    assert settings.SESSION_COOKIE_AGE == 1800
    assert settings.SESSION_SAVE_EVERY_REQUEST is True


def test_mat_khau_that_dung_pbkdf2():
    """Cấu hình thật không ghi đè PASSWORD_HASHERS: Django mặc định PBKDF2."""
    from django.conf import global_settings

    import config.settings as cfg

    assert not hasattr(cfg, "PASSWORD_HASHERS")
    assert global_settings.PASSWORD_HASHERS[0].endswith("PBKDF2PasswordHasher")


def test_khong_co_media_url_cong_khai():
    """Không khai báo MEDIA_URL: tệp tải lên không có URL public."""
    import config.settings as cfg

    assert not hasattr(cfg, "MEDIA_URL")
    with pytest.raises(Resolver404):
        resolve("/private_media/x.pdf")


def test_allowed_hosts_mac_dinh(monkeypatch):
    """Không đặt ALLOWED_HOSTS trong môi trường thì mặc định chỉ localhost."""
    import importlib

    import config.settings as cfg

    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    reloaded = importlib.reload(cfg)
    try:
        assert reloaded.ALLOWED_HOSTS == ["localhost", "127.0.0.1"]
    finally:
        monkeypatch.undo()
        importlib.reload(cfg)
