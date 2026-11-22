"""Sinh mã hồ sơ / mã nhân viên (Phase 2 bước 6)."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connection
from django.utils import timezone

from apps.core.codes import bump_sequence, format_code, next_code
from apps.core.models import CodeSequence, SystemSetting
from tests.factories import make_worker

pytestmark = pytest.mark.django_db
YEAR = timezone.localtime().year


def test_dinh_dang_mac_dinh_ma_ho_so_co_nam_ma_nhan_vien_khong_nam():
    assert next_code("WORKER") == f"HS-{YEAR}-00001"
    assert next_code("EMPLOYEE") == "CN-00001"


def test_tang_don_dieu():
    codes = [next_code("WORKER") for _ in range(5)]
    assert codes == [f"HS-{YEAR}-{i:05d}" for i in range(1, 6)]
    assert CodeSequence.objects.get(code_type="WORKER", year=YEAR).last_number == 5


def test_hai_bo_dem_doc_lap():
    next_code("WORKER")
    next_code("WORKER")
    assert next_code("EMPLOYEE") == "CN-00001"


def test_bo_qua_ma_da_ton_tai_cau_27():
    make_worker(worker_code=f"HS-{YEAR}-00001")
    make_worker(worker_code=f"HS-{YEAR}-00002")
    assert next_code("WORKER") == f"HS-{YEAR}-00003"
    w = make_worker()
    w.employee_code = "CN-00001"
    w.save()
    assert next_code("EMPLOYEE") == "CN-00002"


def test_doi_tien_to_chi_anh_huong_ma_cap_sau():
    a = next_code("WORKER")
    s = SystemSetting.load()
    s.worker_code_prefix, s.worker_code_digits, s.worker_code_use_year = "PA", 4, False
    s.save()
    b = next_code("WORKER")
    assert a == f"HS-{YEAR}-00001" and b == "PA-0001"
    s.worker_code_prefix, s.worker_code_use_year, s.worker_code_digits = "HS", True, 5
    s.save()
    assert next_code("WORKER") == f"HS-{YEAR}-00002"  # bộ đếm năm cũ tiếp tục, mã cũ giữ nguyên


def test_ma_vuot_do_dai_20_bi_chan_va_khong_tieu_so():
    s = SystemSetting.load()
    s.worker_code_prefix, s.worker_code_digits = "TIENTOQUA", 8
    s.save()
    with pytest.raises(ValueError, match="dài quá"):
        next_code("WORKER")
    assert not CodeSequence.objects.filter(code_type="WORKER", last_number__gt=0).exists()


def test_so_lon_hon_so_chu_so_van_cap_duoc():
    s = SystemSetting.load()
    s.employee_code_digits = 3
    s.save()
    CodeSequence.objects.create(code_type="EMPLOYEE", year=0, last_number=999)
    assert next_code("EMPLOYEE") == "CN-1000"


def test_format_code():
    assert format_code("HS", 2026, 123, 5) == "HS-2026-00123"
    assert format_code("CN", 0, 456, 5) == "CN-00456"


def test_ma_cu_khop_dinh_dang_day_bo_dem_khac_dinh_dang_khong_dung_den():
    assert bump_sequence("EMPLOYEE", "CN-00456") is True
    assert next_code("EMPLOYEE") == "CN-00457"
    assert bump_sequence("EMPLOYEE", "NV2019-A12") is False
    assert bump_sequence("EMPLOYEE", "CN-00010") is True  # không bao giờ giảm
    assert next_code("EMPLOYEE") == "CN-00458"
    assert bump_sequence("WORKER", f"HS-{YEAR}-00040") is True
    assert next_code("WORKER") == f"HS-{YEAR}-00041"


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_song_song_nhieu_luong_khong_trung_ma():
    """8 luồng, mỗi luồng cấp 6 mã bằng kết nối riêng: 48 mã khác nhau, liền số."""
    start = threading.Barrier(8)

    def worker():
        try:
            start.wait()
            return [next_code("WORKER") for _ in range(6)]
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = [f.result() for f in [pool.submit(worker) for _ in range(8)]]
    codes = [c for r in results for c in r]
    assert len(codes) == 48 and len(set(codes)) == 48
    assert sorted(codes) == [f"HS-{YEAR}-{i:05d}" for i in range(1, 49)]
