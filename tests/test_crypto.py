import base64

import pytest

from apps.core import crypto
from apps.core.keys import KeyConfigError


def test_ma_hoa_khu_hoi():
    token = crypto.encrypt_value("079912345678")
    assert token != "079912345678" and "0799" not in token
    assert crypto.decrypt_value(token) == "079912345678"


def test_none_giu_none_va_chuoi_rong_khu_hoi():
    assert crypto.encrypt_value(None) is None
    assert crypto.decrypt_value(None) is None
    assert crypto.decrypt_value(crypto.encrypt_value("")) == ""


def test_hai_lan_ma_hoa_khac_nhau():
    assert crypto.encrypt_value("abc") != crypto.encrypt_value("abc")


def test_truong_encrypted_text_field():
    f = crypto.EncryptedTextField(null=True)
    stored = f.get_prep_value("Số 1 Đường Giả")
    assert "Giả" not in stored
    assert f.from_db_value(stored, None, None) == "Số 1 Đường Giả"
    assert f.get_prep_value(None) is None
    assert f.from_db_value(None, None, None) is None


def test_sai_khoa_giai_ma_bao_loi_tieng_viet(settings):
    token = crypto.encrypt_value("bí mật")
    settings.FIELD_ENCRYPTION_KEY = base64.urlsafe_b64encode(b"X" * 32).decode()
    with pytest.raises(KeyConfigError, match="FIELD_ENCRYPTION_KEY không khớp"):
        crypto.decrypt_value(token)


def test_hmac_xac_dinh_va_doi_khoa_doi_ket_qua(settings):
    a = crypto.hmac_hash("999000000001")
    assert a == crypto.hmac_hash("999000000001")
    assert len(a) == 64
    settings.HASH_KEY = base64.urlsafe_b64encode(b"Z" * 32).decode()
    assert crypto.hmac_hash("999000000001") != a


def test_chuan_hoa_so_dinh_danh():
    assert crypto.normalize_id_number(" 999 000-000.001 ") == "999000000001"
    assert crypto.compute_id_hash("999 000 000 001") == crypto.compute_id_hash("999000000001")
    assert crypto.compute_id_hash("") is None
    assert crypto.compute_id_hash(None) is None
