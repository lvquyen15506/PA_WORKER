import base64
import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core import crypto, keys
from apps.core.keys import KeyConfigError


def _b64(n, ch=b"x"):
    return base64.urlsafe_b64encode(ch * n).decode()


def test_dung_dinh_dang_khong_loi():
    keys.check_format()


@pytest.mark.parametrize(
    "ten, gia_tri, thong_bao",
    [
        ("FIELD_ENCRYPTION_KEY", "", "Thiếu khóa mã hóa FIELD_ENCRYPTION_KEY"),
        ("HASH_KEY", "", "Thiếu khóa băm HASH_KEY"),
        ("FIELD_ENCRYPTION_KEY", "khong-phai-khoa", "FIELD_ENCRYPTION_KEY trong tệp .env sai"),
        ("FIELD_ENCRYPTION_KEY", _b64(16), "sai định dạng"),
        ("HASH_KEY", _b64(8), "HASH_KEY trong tệp .env sai định dạng"),
    ],
)
def test_thieu_hoac_sai_dinh_dang(settings, ten, gia_tri, thong_bao):
    setattr(settings, ten, gia_tri)
    with pytest.raises(KeyConfigError, match=thong_bao):
        keys.check_format()


def test_lenh_check_keys_format(settings):
    out = io.StringIO()
    call_command("check_keys", "--format", stdout=out)
    assert "đúng định dạng" in out.getvalue()
    settings.HASH_KEY = ""
    with pytest.raises(CommandError, match="Thiếu khóa băm HASH_KEY"):
        call_command("check_keys", "--format")


def test_key_check_khop():
    keys.verify_key_check(keys.KEY_CHECK_TEXT, keys.key_check_hash())


def test_key_check_sai_field_key(settings):
    token = crypto.encrypt_value(keys.KEY_CHECK_TEXT)
    stored_hash = keys.key_check_hash()
    settings.FIELD_ENCRYPTION_KEY = _b64(32, b"X")
    with pytest.raises(KeyConfigError, match="FIELD_ENCRYPTION_KEY không khớp"):
        keys.verify_key_check(crypto.decrypt_value(token), stored_hash)


def test_key_check_chi_sai_hash_key(settings):
    """Dữ liệu vẫn giải mã được nhưng HASH_KEY sai: phải bị chặn riêng."""
    stored_hash = keys.key_check_hash()
    settings.HASH_KEY = _b64(32, b"Z")
    with pytest.raises(KeyConfigError, match="HASH_KEY không khớp"):
        keys.verify_key_check(keys.KEY_CHECK_TEXT, stored_hash)


def test_key_check_chuoi_giai_ma_khac():
    with pytest.raises(KeyConfigError, match="FIELD_ENCRYPTION_KEY không khớp"):
        keys.verify_key_check("chuoi-khac", keys.key_check_hash())


def test_key_check_hash_rong_la_khong_khop():
    with pytest.raises(KeyConfigError, match="HASH_KEY không khớp"):
        keys.verify_key_check(keys.KEY_CHECK_TEXT, None)
