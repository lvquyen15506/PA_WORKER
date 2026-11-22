"""Ràng buộc của model core/accounts và kiểm tra khóa đầy đủ (Phase 2 bước 3a)."""

import base64
import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction

from apps.accounts.models import Role, User
from apps.core import keys
from apps.core.models import (
    CodeSequence,
    Department,
    DocumentType,
    Section,
    SystemSetting,
    Team,
)

pytestmark = pytest.mark.django_db


def test_bo_phan_trung_ten_trong_cung_phong_ban_bi_chan():
    d1 = Department.objects.create(name="Sản xuất")
    d2 = Department.objects.create(name="Kho")
    Section.objects.create(department=d1, name="Lắp ráp")
    Section.objects.create(department=d2, name="Lắp ráp")  # khác phòng ban: được
    with pytest.raises(IntegrityError), transaction.atomic():
        Section.objects.create(department=d1, name="Lắp ráp")


def test_to_trung_ten_trong_cung_bo_phan_bi_chan():
    d = Department.objects.create(name="Sản xuất")
    s = Section.objects.create(department=d, name="Lắp ráp")
    Team.objects.create(section=s, name="Tổ 1")
    with pytest.raises(IntegrityError), transaction.atomic():
        Team.objects.create(section=s, name="Tổ 1")


def test_ten_phong_ban_duy_nhat():
    Department.objects.create(name="Sản xuất")
    with pytest.raises(IntegrityError), transaction.atomic():
        Department.objects.create(name="Sản xuất")


def test_system_code_rong_thanh_null_nhieu_dong_duoc():
    a = DocumentType.objects.create(name="Loại A", system_code="")
    b = DocumentType.objects.create(name="Loại B", system_code="")
    assert a.system_code is None and b.system_code is None
    with pytest.raises(IntegrityError), transaction.atomic():
        DocumentType.objects.create(name="Loại C", system_code="PORTRAIT")  # trùng mã có sẵn


def test_cai_dat_luon_pk_1_va_khong_xoa():
    s = SystemSetting(worker_code_prefix="XX")
    s.save()
    assert s.pk == 1 and SystemSetting.objects.count() == 1
    with pytest.raises(ValueError):
        SystemSetting.load().delete()


def test_code_sequence_duy_nhat_theo_loai_va_nam():
    CodeSequence.objects.create(code_type="WORKER", year=2026)
    CodeSequence.objects.create(code_type="WORKER", year=2027)
    CodeSequence.objects.create(code_type="EMPLOYEE", year=0)
    with pytest.raises(IntegrityError), transaction.atomic():
        CodeSequence.objects.create(code_type="WORKER", year=2026)


def test_vai_tro_duy_nhat_va_user_bat_buoc_vai_tro():
    with pytest.raises(IntegrityError), transaction.atomic():
        Role.objects.create(code="ADMIN", name="Trùng")
    u = User.objects.create(
        username="a1", full_name="Người Giả", role=Role.objects.get(code="ADMIN")
    )
    assert u.must_change_password is True
    assert u.failed_login_count == 0 and u.locked_until is None and u.is_active is True
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create(username="a2", full_name="X", role=None)


# --- check_keys đầy đủ -------------------------------------------------------------
def _run():
    out = io.StringIO()
    call_command("check_keys", stdout=out)
    return out.getvalue()


def test_check_keys_lan_dau_ghi_gia_tri_kiem_tra_roi_khop():
    assert "Đã ghi giá trị kiểm tra" in _run()
    assert "khớp với dữ liệu" in _run()
    assert "khớp với dữ liệu" in _run()  # chạy lại nhiều lần không đổi


def test_check_keys_cot_enc_khong_luu_ban_ro():
    _run()
    with connection.cursor() as cur:
        cur.execute("SELECT key_check_enc, key_check_hash FROM core_systemsetting WHERE id = 1")
        enc, h = cur.fetchone()
    assert keys.KEY_CHECK_TEXT not in enc
    assert h == keys.key_check_hash()


def test_check_keys_sai_field_key(settings):
    _run()
    settings.FIELD_ENCRYPTION_KEY = base64.urlsafe_b64encode(b"X" * 32).decode()
    with pytest.raises(CommandError, match="FIELD_ENCRYPTION_KEY không khớp"):
        _run()


def test_check_keys_chi_sai_hash_key(settings):
    _run()
    settings.HASH_KEY = base64.urlsafe_b64encode(b"Z" * 32).decode()
    with pytest.raises(CommandError, match="HASH_KEY không khớp"):
        _run()


def test_check_keys_khong_ghi_de_gia_tri_da_co(settings):
    _run()
    before = SystemSetting.objects.values_list("key_check_hash", flat=True).get()
    settings.HASH_KEY = base64.urlsafe_b64encode(b"Z" * 32).decode()
    with pytest.raises(CommandError):
        _run()
    assert SystemSetting.objects.values_list("key_check_hash", flat=True).get() == before


def test_check_keys_chi_mot_cot_co_gia_tri_bi_tu_choi():
    SystemSetting.objects.filter(pk=1).update(key_check_hash=keys.key_check_hash())
    with pytest.raises(CommandError, match="không khớp"):
        _run()
