"""Kiểm tra trùng: số định danh (lỗi) và SĐT / họ tên + ngày sinh (cảnh báo)."""

import datetime

import pytest
from django.utils import timezone

from apps.workers.duplicates import find_by_id_number, find_similar
from apps.workers.models import IdentityDocument, Worker
from tests.factories import fake_id, make_user, make_worker, make_worker_full

pytestmark = pytest.mark.django_db
D = datetime.date


def with_id(worker, number):
    identity = IdentityDocument.objects.filter(worker=worker).first()
    if identity is None:
        return IdentityDocument.objects.create(worker=worker, id_number_enc=number)
    identity.id_number_enc = number
    identity.save()
    return identity


# ----- Số định danh -----------------------------------------------------------------------
def test_tim_ho_so_theo_so_dinh_danh_bang_gia_tri_bam():
    worker = make_worker_full()
    number = fake_id()
    with_id(worker, number)
    assert find_by_id_number(number) == worker
    assert find_by_id_number(fake_id()) is None


def test_so_dinh_danh_co_khoang_trang_hoac_dau_van_khop():
    worker = make_worker_full()
    with_id(worker, "999123456789")
    assert find_by_id_number("999 1234 5678 9") == worker
    assert find_by_id_number("999.123.456.789") == worker


def test_bo_qua_chinh_ho_so_dang_sua():
    worker = make_worker_full()
    with_id(worker, "999000000001")
    assert find_by_id_number("999000000001", exclude_worker=worker) is None
    assert find_by_id_number("999000000001", exclude_worker=make_worker()) == worker


@pytest.mark.parametrize("empty", ["", None, "   ", "abc"])
def test_so_rong_khong_khop_ho_so_nao(empty):
    with_id(make_worker_full(), "999000000002")
    assert find_by_id_number(empty) is None


def test_ho_so_da_an_danh_khong_con_khop_so_cu():
    worker = make_worker_full()
    with_id(worker, "999000000003")
    IdentityDocument.objects.filter(worker=worker).update(id_number_hash=None)  # như ẩn danh hóa
    assert find_by_id_number("999000000003") is None


# ----- Trùng SĐT / họ tên + ngày sinh -------------------------------------------------------
def test_trung_sdt():
    a = make_worker_full(phone="0911000111")
    matches = find_similar(phone="0911000111")
    assert [(m.worker, m.by_phone, m.by_name_dob) for m in matches] == [(a, True, False)]


def test_trung_ho_ten_khong_dau_va_ngay_sinh_khong_phan_biet_dau_hoa_thuong():
    a = make_worker_full(full_name="Nguyễn Văn An", date_of_birth=D(1990, 1, 2))
    matches = find_similar(full_name="  nguyen VĂN an ", date_of_birth=D(1990, 1, 2))
    assert [(m.worker, m.by_phone, m.by_name_dob) for m in matches] == [(a, False, True)]


def test_chi_trung_ten_khong_trung_ngay_sinh_thi_khong_tinh():
    make_worker_full(full_name="Nguyễn Văn An", date_of_birth=D(1990, 1, 2))
    assert find_similar(full_name="Nguyen Van An", date_of_birth=D(1990, 1, 3)) == []
    assert find_similar(full_name="Nguyen Van An") == []  # thiếu ngày sinh: không so khớp tên


def test_trung_ca_hai_thi_mot_dong_hai_co():
    a = make_worker_full(full_name="Trần Thị Bình", phone="0911000222", date_of_birth=D(1992, 3, 4))
    matches = find_similar(
        phone="0911000222", full_name="Tran Thi Binh", date_of_birth=D(1992, 3, 4)
    )
    assert len(matches) == 1
    assert (matches[0].worker, matches[0].by_phone, matches[0].by_name_dob) == (a, True, True)


def test_sdt_rong_khong_khop_ho_so_nao():
    make_worker(phone="0911000333")
    assert find_similar(phone="") == []
    assert find_similar(phone="   ") == []


def test_bo_qua_chinh_ho_so_va_ho_so_da_an_danh():
    me = make_worker_full(phone="0911000444")
    gone = make_worker_full(phone="0911000444")
    Worker.objects.filter(pk=gone.pk).update(anonymized_at=timezone.now())
    other = make_worker_full(phone="0911000444")
    matches = find_similar(phone="0911000444", exclude_worker=me)
    assert [m.worker for m in matches] == [other]


def test_gioi_han_so_ket_qua_va_sap_theo_ma():
    for _ in range(14):
        make_worker(phone="0911000555", created_by=make_user())
    matches = find_similar(phone="0911000555")
    assert len(matches) == 10
    codes = [m.worker.worker_code for m in matches]
    assert codes == sorted(codes)
