"""Trang Duyệt hồ sơ: hàng đợi Chờ duyệt, chỉ Admin và Quản lý nhân sự."""

import re

import pytest

from apps.core.choices import VerificationStatus as VS
from tests.factories import (
    at,
    freeze_time,
    login_client,
    make_document,
    make_user,
    make_worker_full,
    make_worker_in_status,
)

pytestmark = pytest.mark.django_db


def queue(role="HR_MANAGER", query="", user=None):
    client = login_client(user or make_user(role))
    response = client.get("/duyet-ho-so/" + query)
    assert response.status_code == 200
    return response.content.decode()


def submitted(created_by=None, when=None, **kw):
    """Hồ sơ Chờ duyệt, gửi lúc `when`."""
    worker = make_worker_full(created_by=created_by or make_user("HR_STAFF"), **kw)
    from apps.workers.workflow import transition

    with freeze_time(when or at(2026, 11, 1)):
        transition(worker, VS.PENDING, worker.created_by)
    return worker


@pytest.mark.parametrize("role", ["ADMIN", "HR_MANAGER"])
def test_quan_ly_va_admin_xem_duoc(role):
    assert "Duyệt hồ sơ" in queue(role)


@pytest.mark.parametrize("role", ["HR_STAFF", "VIEWER"])
def test_hr_va_viewer_bi_403(role):
    assert login_client(make_user(role)).get("/duyet-ho-so/").status_code == 403


def test_chua_dang_nhap_chuyen_ve_dang_nhap():
    from django.test import Client

    response = Client().get("/duyet-ho-so/")
    assert response.status_code == 302 and response["Location"].startswith("/dang-nhap/")


def test_chi_liet_ke_ho_so_cho_duyet():
    pending = submitted(full_name="Đang Chờ Duyệt")
    others = [make_worker_in_status(s) for s in (VS.DRAFT, VS.NEEDS_INFO, VS.VERIFIED, VS.REJECTED)]
    page = queue()
    assert pending.worker_code in page
    assert not [w for w in others if w.worker_code in page]


def test_cu_nhat_truoc():
    newer = submitted(when=at(2026, 11, 10))
    oldest = submitted(when=at(2026, 10, 1))
    middle = submitted(when=at(2026, 10, 20))
    page = queue()
    order = sorted((newer, oldest, middle), key=lambda w: page.index(w.worker_code))
    assert order == [oldest, middle, newer]


def test_cot_nguoi_gui_ngay_gui_va_nhan_thieu_giay_to():
    sender = make_user("HR_STAFF")
    worker = submitted(created_by=sender, when=at(2026, 11, 5))
    page = queue()
    row = re.search(rf"<tr>(?:(?!</tr>).)*{worker.worker_code}.*?</tr>", page, re.S).group(0)
    assert sender.full_name in row and "05/11/2026" in row and "Thiếu giấy tờ" in row
    for code in ("CCCD_FRONT", "CCCD_BACK", "PORTRAIT", "CV"):
        make_document(worker, code)
    row = re.search(rf"<tr>(?:(?!</tr>).)*{worker.worker_code}.*?</tr>", queue(), re.S).group(0)
    assert "Thiếu giấy tờ" not in row


def test_nguoi_gui_la_nguoi_gui_lan_gan_nhat_khong_phai_lan_dau():
    from apps.workers.workflow import transition

    creator, second = make_user("HR_STAFF"), make_user("HR_MANAGER")
    worker = make_worker_full(created_by=creator)
    transition(worker, VS.PENDING, creator)
    transition(worker, VS.NEEDS_INFO, make_user("ADMIN"), "Bổ sung")
    transition(worker, VS.PENDING, second)
    row = re.search(rf"<tr>(?:(?!</tr>).)*{worker.worker_code}.*?</tr>", queue(), re.S).group(0)
    assert second.full_name in row and creator.full_name not in row


def test_dong_cua_chinh_minh_co_ghi_chu_khong_duyet_duoc():
    from apps.workers.workflow import transition

    me = make_user("HR_MANAGER")
    created_by_me = make_worker_full(created_by=me)
    transition(created_by_me, VS.PENDING, make_user("HR_STAFF"))  # tôi tạo, người khác gửi
    sent_by_me = make_worker_full(created_by=make_user("HR_STAFF"))
    transition(sent_by_me, VS.PENDING, me)  # người khác tạo, tôi gửi
    other = submitted(created_by=make_user("HR_STAFF"))  # không liên quan tới tôi
    page = queue(user=me)
    note = "Bạn không duyệt được hồ sơ này"

    def row(worker):
        return re.search(rf"<tr>(?:(?!</tr>).)*{worker.worker_code}.*?</tr>", page, re.S).group(0)

    assert note in row(created_by_me) and note in row(sent_by_me)
    assert note not in row(other)


def test_loc_theo_nguoi_gui_va_khoang_ngay():
    a, b = make_user("HR_STAFF"), make_user("HR_STAFF")
    wa = submitted(created_by=a, when=at(2026, 10, 5))
    wb = submitted(created_by=b, when=at(2026, 11, 5))
    page = queue(query=f"?nguoi_gui={a.pk}")
    assert wa.worker_code in page and wb.worker_code not in page
    page = queue(query="?tu_ngay=01/11/2026")
    assert wb.worker_code in page and wa.worker_code not in page
    page = queue(query="?den_ngay=31/10/2026")
    assert wa.worker_code in page and wb.worker_code not in page
    page = queue(query="?tu_ngay=01/10/2026&den_ngay=30/11/2026")
    assert wa.worker_code in page and wb.worker_code in page


def test_ngay_sai_dinh_dang_bao_loi_khong_sap_trang():
    worker = submitted()
    page = queue(query="?tu_ngay=hom-qua")
    assert "Nhập ngày đúng định dạng dd/mm/yyyy." in page and worker.worker_code in page


def test_hang_doi_rong_hien_thong_bao():
    assert "Không có hồ sơ chờ duyệt." in queue()


def test_phan_trang_20_dong():
    for i in range(23):
        submitted(when=at(2026, 10, 1, 8, i))
    page = queue(query="?trang=2")
    assert "Hiển thị 21–23 / 23" in page


def test_nut_xem_dan_den_trang_chi_tiet():
    worker = submitted()
    assert f"/ho-so/{worker.pk}/" in queue()
