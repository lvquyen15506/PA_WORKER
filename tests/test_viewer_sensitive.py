"""Viewer không nhận trường nhạy cảm (câu 13) trong HTML trả về, kể cả mảnh HTMX.

Trường nhạy cảm: số CCCD đầy đủ, CMND cũ, địa chỉ thường trú, quê quán, nơi đăng ký khai sinh,
ảnh CCCD (liên kết xem/tải tài liệu), mức lương mong muốn. Viewer vẫn thấy SĐT, nơi ở hiện tại và
số CCCD dạng che. Có nhóm đối chứng HR để chứng minh test không rỗng.
"""

import pytest

from apps.core.text import mask_id_number
from apps.workers.models import Worker
from tests.factories import (
    SENSITIVE,
    login_client,
    make_sensitive_worker,
    make_user,
)

pytestmark = pytest.mark.django_db

FORBIDDEN = [
    SENSITIVE["id_number"],
    SENSITIVE["old_id_number"],
    SENSITIVE["permanent_address"],
    SENSITIVE["hometown"],
    SENSITIVE["birth_registration_place"],
    SENSITIVE["salary_text"],
    str(SENSITIVE["salary"]),
    SENSITIVE["file_name"],
]
TABS = ["ca-nhan", "tuyen-dung", "lam-viec", "tai-lieu", "lich-su"]
STATUSES = ["DRAFT", "PENDING", "VERIFIED"]


def html(client, url, method="get"):
    response = getattr(client, method)(url)
    return response, response.content.decode()


@pytest.fixture
def worker():
    return make_sensitive_worker()


@pytest.mark.parametrize("tab", TABS)
def test_viewer_cac_tab_khong_chua_truong_nhay_cam(worker, tab):
    response, page = html(login_client(make_user("VIEWER")), f"/ho-so/{worker.pk}/?tab={tab}")
    assert response.status_code == 200
    leaked = [value for value in FORBIDDEN if value in page]
    assert leaked == []
    assert "/tai-lieu/" not in page  # không có liên kết xem/tải tệp nào


@pytest.mark.parametrize("status", STATUSES)
def test_viewer_o_moi_trang_thai_khong_thay_truong_nhay_cam(status):
    worker = make_sensitive_worker(status)
    client = login_client(make_user("VIEWER"))
    for tab in TABS:
        _, page = html(client, f"/ho-so/{worker.pk}/?tab={tab}")
        assert [v for v in FORBIDDEN if v in page] == [], (status, tab)


def test_viewer_van_thay_sdt_noi_o_hien_tai_va_so_cccd_da_che(worker):
    _, page = html(login_client(make_user("VIEWER")), f"/ho-so/{worker.pk}/")
    assert worker.phone in page and worker.current_address in page
    assert mask_id_number(SENSITIVE["id_number"]) in page  # 9993••••9265
    # Nhãn của trường nhạy cảm bị bỏ hẳn, không để ô trống.
    for label in ("Số CMND cũ", "Nơi thường trú", "Quê quán", "Nơi đăng ký khai sinh"):
        assert label not in page


def test_viewer_tab_tuyen_dung_khong_co_cot_muc_luong(worker):
    _, page = html(login_client(make_user("VIEWER")), f"/ho-so/{worker.pk}/?tab=tuyen-dung")
    assert "Mức lương mong muốn" not in page
    assert "Trường Giả" in page  # học vấn vẫn thấy


def test_viewer_tab_tai_lieu_thay_loai_ngay_trang_thai_nhung_khong_ten_tep_hay_lien_ket(worker):
    _, page = html(login_client(make_user("VIEWER")), f"/ho-so/{worker.pk}/?tab=tai-lieu")
    assert "CCCD mặt trước" in page and "Chưa xác minh" in page
    assert "Tên tệp" not in page and "Thao tác" not in page


def test_viewer_danh_sach_khong_chua_truong_nhay_cam(worker):
    client = login_client(make_user("VIEWER"))
    for url in ("/ho-so/", "/ho-so/?q=" + worker.worker_code):
        _, page = html(client, url)
        assert [v for v in FORBIDDEN if v in page] == []


# ----- Mảnh HTMX và trang phụ: Viewer đều bị 403 --------------------------------------------
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/ho-so/{id}/cccd-day-du/"),
        ("get", "/ho-so/{id}/lich-su/chi-tiet/"),
        ("post", "/ho-so/kiem-tra-trung/"),
        ("get", "/ho-so/{id}/sua/"),
        ("get", "/ho-so/{id}/dong-y/"),
        ("get", "/ho-so/{id}/dong-y/mau-in/"),
        ("get", "/ho-so/{id}/tai-lieu/them/"),
        ("get", "/ho-so/them/"),
        ("get", "/ho-so/them/nhap-tay/"),
        ("get", "/duyet-ho-so/"),
    ],
)
def test_viewer_goi_thang_manh_htmx_hoac_trang_phu_bi_403(worker, method, path):
    client = login_client(make_user("VIEWER"))
    response = getattr(client, method)(path.format(id=worker.pk))
    assert response.status_code == 403
    page = response.content.decode()
    assert [v for v in FORBIDDEN if v in page] == []


def test_viewer_khong_tim_duoc_theo_so_cccd_va_khong_biet_ho_so_co_ton_tai(worker):
    client = login_client(make_user("VIEWER"))
    _, page = html(client, f"/ho-so/?q={SENSITIVE['id_number']}")
    assert worker.worker_code not in page and "Không có hồ sơ phù hợp." in page


# ----- Nhóm đối chứng: HR thấy đúng các giá trị đó ---------------------------------------------
def test_doi_chung_hr_thay_cac_truong_nhay_cam_nen_test_o_tren_khong_rong(worker):
    client = login_client(make_user("HR_STAFF"))
    _, personal = html(client, f"/ho-so/{worker.pk}/")
    for value in (
        SENSITIVE["permanent_address"],
        SENSITIVE["hometown"],
        SENSITIVE["birth_registration_place"],
    ):
        assert value in personal
    assert mask_id_number(SENSITIVE["id_number"]) in personal
    assert SENSITIVE["id_number"] not in personal  # HR cũng chỉ thấy dạng che cho tới khi bấm
    assert "Hiện số đầy đủ" in personal
    _, recruit = html(client, f"/ho-so/{worker.pk}/?tab=tuyen-dung")
    assert SENSITIVE["salary_text"] in recruit and "Mức lương mong muốn" in recruit
    _, documents = html(client, f"/ho-so/{worker.pk}/?tab=tai-lieu")
    assert SENSITIVE["file_name"] in documents and "/tai-xuong/" in documents
    response, full = html(client, f"/ho-so/{worker.pk}/cccd-day-du/", "post")
    assert response.status_code == 200
    assert SENSITIVE["id_number"] in full and SENSITIVE["old_id_number"] in full


def test_doi_chung_hr_tim_theo_so_cccd(worker):
    _, page = html(login_client(make_user("HR_STAFF")), f"/ho-so/?q={SENSITIVE['id_number']}")
    assert Worker.objects.get(pk=worker.pk).full_name in page
    # Số chỉ xuất hiện một lần: ô tìm kiếm echo lại chữ người dùng vừa gõ; bảng không in số CCCD.
    assert page.count(SENSITIVE["id_number"]) == 1
