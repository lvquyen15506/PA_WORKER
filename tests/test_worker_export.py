"""Xuất Excel danh sách /ho-so/xuat-excel/ (Phase 7, bước 5; kịch bản nghiệm thu 13)."""

import io
import re

import pytest
from django.utils import timezone
from openpyxl import load_workbook

from apps.audit.models import AuditLog
from apps.core.choices import VerificationStatus as VS
from apps.core.crypto import compute_id_hash  # noqa: F401  (đảm bảo khóa mã hóa test sẵn sàng)
from apps.core.models import ClientCompany, Position
from apps.employment import assignments as svc
from apps.employment.models import Employment
from apps.workers import export
from apps.workers.models import IdentityDocument, Worker
from tests.factories import (
    login_client,
    make_user,
    make_worker_full,
    make_worker_in_status,
)
from tests.test_dashboard import days, employ, total

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate()
ALL = ["ADMIN", "HR_MANAGER", "HR_STAFF"]


def export_rows(response):
    book = load_workbook(io.BytesIO(response.content), data_only=False)
    return [[c.value for c in row] for row in book.active.iter_rows()]


def get_export(role="HR_STAFF", query=""):
    response = login_client(make_user(role)).get("/ho-so/xuat-excel/" + query)
    assert response.status_code == 200
    return response


def list_total(query, role="HR_STAFF"):
    page = login_client(make_user(role)).get("/ho-so/" + query)
    return total(page.content.decode())


def number_of(worker):
    return IdentityDocument.objects.get(worker=worker).id_number_enc


@pytest.fixture
def workers():
    out = {}
    out["an"] = make_worker_full(full_name="Nguyễn Văn An")
    out["binh"] = make_worker_full(full_name="Trần Thị Bình")
    out["verified"] = make_worker_in_status(VS.VERIFIED)
    out["working"] = make_worker_full(full_name="Lê Đang Làm")
    employ(out["working"], "ACTIVE")
    out["archived"] = make_worker_in_status(VS.ARCHIVED)
    return out


# --- Quyền -----------------------------------------------------------------------------------
def test_chua_dang_nhap_chuyen_ve_dang_nhap():
    from django.test import Client

    response = Client().get("/ho-so/xuat-excel/")
    assert response.status_code == 302 and response.url.startswith("/dang-nhap/")


def test_viewer_khong_xuat_duoc_ca_get_lan_post(workers):
    client = login_client(make_user("VIEWER"))
    assert client.get("/ho-so/xuat-excel/").status_code == 403
    assert client.post("/ho-so/xuat-excel/", {"cccd_day_du": "1"}).status_code == 403
    assert not AuditLog.objects.filter(action="EXPORT").exists()


@pytest.mark.parametrize("role", ALL)
def test_nhan_vien_xuat_duoc(role, workers):
    response = get_export(role)
    assert response["Content-Type"].startswith("application/vnd.openxmlformats")
    assert "Danh-sach-ho-so-" in response["Content-Disposition"]


def test_nut_xuat_theo_vai_tro(workers):
    def page(role):
        return login_client(make_user(role)).get("/ho-so/").content.decode()

    for role in ("ADMIN", "HR_MANAGER"):
        content = page(role)
        assert "Xuất Excel" in content and "Xuất kèm số CCCD" in content
        assert 'name="cccd_day_du"' in content and "modal-export-full" in content
    hr = page("HR_STAFF")
    assert "Xuất Excel" in hr and "Xuất kèm số CCCD" not in hr and "cccd_day_du" not in hr
    viewer = page("VIEWER")
    assert "Xuất Excel" not in viewer and "xuat-excel" not in viewer


def test_lien_ket_xuat_mang_theo_bo_loc_dang_ap(workers):
    client = login_client(make_user("ADMIN"))
    content = client.get("/ho-so/?trang_thai_ho_so=chua-luu-tru&sap_xep=ten").content.decode()
    assert re.search(r'href="/ho-so/xuat-excel/\?[^"]*trang_thai_ho_so=chua-luu-tru', content)
    assert 'action="/ho-so/xuat-excel/?' in content  # hộp xác nhận cũng giữ bộ lọc


# --- Số dòng và nội dung khớp màn hình (kịch bản 13) --------------------------------------------
@pytest.mark.parametrize(
    "query",
    [
        "",
        "?trang_thai_ho_so=chua-luu-tru",
        "?trang_thai_ho_so=VERIFIED",
        "?trang_thai_ho_so=ARCHIVED",
        "?trang_thai_lam_viec=PROBATION%2CACTIVE",
        "?thieu_giay_to=1&trang_thai_ho_so=chua-luu-tru",
        "?q=nguyen+van+an",
        "?q=nguyen+van+an&trang_thai_ho_so=DRAFT",
        "?q=khong-co-ai-ten-nhu-vay",
    ],
)
def test_so_dong_file_bang_so_dong_man_hinh(query, workers):
    rows = export_rows(get_export("HR_STAFF", query))
    assert len(rows) - 1 == list_total(query)  # trừ dòng tiêu đề


def test_noi_dung_va_thu_tu_khop_man_hinh(workers):
    query = "?sap_xep=ten"
    rows = export_rows(get_export("ADMIN", query))
    page = login_client(make_user("ADMIN")).get("/ho-so/" + query).content.decode()
    names_in_file = [r[2] for r in rows[1:21]]  # trang đầu 20 dòng
    positions = [page.find(name) for name in names_in_file if name]
    assert positions == sorted(positions) and all(p >= 0 for p in positions)
    assert [r[0] for r in rows[1:]] == list(range(1, len(rows)))  # STT 1..n


def test_tim_khong_dau_ra_dung_ho_so_co_dau(workers):
    rows = export_rows(get_export("HR_STAFF", "?q=nguyen+van+an"))
    assert [r[2] for r in rows[1:]] == ["Nguyễn Văn An"]


def test_cot_dung_thu_tu_va_khong_co_cot_luong(workers):
    rows = export_rows(get_export())
    assert rows[0] == export.HEADERS
    assert rows[0][-2:] == ["Mã hồ sơ", "Số CCCD"]
    assert not any("ương" in h or "Đơn giá" in h for h in rows[0])


def test_cac_cot_lay_dung_du_lieu(workers):
    worker = workers["working"]
    worker.refresh_from_db()  # employ() đặt mã NV bằng update()
    Employment.objects.filter(worker=worker).update(start_date=days(-100))
    company = ClientCompany.objects.create(name="Công ty Mẫu A", location="Tỉnh Một")
    svc.add_assignment(
        make_user("HR_STAFF"),
        worker,
        client_company=company,
        position=Position.objects.get(name="Chức danh test"),
        start_date=days(-30),
    )
    row = next(r for r in export_rows(get_export("ADMIN")) if r[2] == "Lê Đang Làm")
    assert row[1] == worker.employee_code
    assert row[3] == worker.date_of_birth.strftime("%d/%m/%Y") and row[4] == "Nam"
    assert row[5] == worker.phone and row[6] == "Công ty Mẫu A – Tỉnh Một"
    assert row[7] == "Chức danh test" and row[8] == days(-100).strftime("%d/%m/%Y")
    assert row[9] == "Nháp" and row[10] == "Đang làm việc" and row[11] == worker.worker_code


# --- Số CCCD --------------------------------------------------------------------------------
@pytest.mark.parametrize("role", ALL)
def test_cccd_luon_che_khi_get(role, workers):
    response = get_export(role, "?cccd_day_du=1")  # tham số trên URL không có tác dụng
    rows = export_rows(response)[1:]
    numbers = [number_of(w) for w in Worker.objects.all()]
    text = response.content
    assert all(n.encode() not in text for n in numbers)
    sample = next(r for r in rows if r[2] == "Nguyễn Văn An")
    full = number_of(workers["an"])
    assert sample[12] == f"{full[:4]}••••{full[-4:]}"


@pytest.mark.parametrize("role", ["ADMIN", "HR_MANAGER"])
def test_quan_ly_va_admin_xuat_kem_cccd_day_du_bang_post(role, workers):
    client = login_client(make_user(role))
    response = client.post("/ho-so/xuat-excel/?q=nguyen+van+an", {"cccd_day_du": "1"})
    assert response.status_code == 200
    rows = export_rows(response)
    assert len(rows) == 2 and rows[1][12] == number_of(workers["an"])
    entry = AuditLog.objects.get(action="EXPORT")
    assert "có số CCCD đầy đủ" in entry.note


def test_post_khong_co_tham_so_cccd_van_che(workers):
    client = login_client(make_user("ADMIN"))
    rows = export_rows(client.post("/ho-so/xuat-excel/?q=nguyen+van+an", {}))
    assert "•" in rows[1][12] and rows[1][12] != number_of(workers["an"])


def test_hr_gui_post_xin_cccd_day_du_bi_403(workers):
    client = login_client(make_user("HR_STAFF"))
    assert client.post("/ho-so/xuat-excel/", {"cccd_day_du": "1"}).status_code == 403
    assert not AuditLog.objects.filter(action="EXPORT").exists()


def test_post_khong_csrf_bi_tu_choi(workers):
    from django.test import Client

    client = Client(enforce_csrf_checks=True)
    user = make_user("ADMIN")
    client.force_login(user)
    assert client.post("/ho-so/xuat-excel/", {"cccd_day_du": "1"}).status_code == 403


# --- An toàn dữ liệu ---------------------------------------------------------------------------
def test_o_bat_dau_bang_ky_tu_cong_thuc_duoc_them_dau_nhay(workers):
    Worker.objects.filter(pk=workers["binh"].pk).update(full_name='=HYPERLINK("http://x")')
    Worker.objects.filter(pk=workers["an"].pk).update(full_name="@SUM(1+1)")
    book = load_workbook(io.BytesIO(get_export("ADMIN").content), data_only=False)
    cells = [c for row in book.active.iter_rows() for c in row]
    assert all(c.data_type != "f" for c in cells)
    values = [c.value for c in cells if isinstance(c.value, str)]
    assert '\'=HYPERLINK("http://x")' in values and "'@SUM(1+1)" in values


# --- Nhật ký ---------------------------------------------------------------------------------
def test_nhat_ky_ghi_so_dong_va_bo_loc_khong_ghi_chu_tim_kiem(workers):
    user = make_user("HR_STAFF")
    login_client(user).get("/ho-so/xuat-excel/?q=nguyen+van+an&trang_thai_ho_so=DRAFT&sap_xep=ten")
    entry = AuditLog.objects.get(action="EXPORT")
    assert entry.user == user
    assert entry.object_type == "worker_list" and entry.object_repr == "Danh sách hồ sơ"
    assert entry.note.startswith("1 dòng;")
    assert "trang_thai_ho_so=DRAFT" in entry.note and "có tìm kiếm" in entry.note
    text = f"{entry.note}{entry.object_repr}{entry.changes}".lower()
    assert "nguyen" not in text and "van an" not in text and "sap_xep" not in text
    assert "có số cccd đầy đủ" not in text


def test_nhat_ky_khong_ghi_ho_ten_va_so_cccd(workers):
    login_client(make_user("ADMIN")).post("/ho-so/xuat-excel/", {"cccd_day_du": "1"})
    entry = AuditLog.objects.get(action="EXPORT")
    text = f"{entry.note}{entry.object_repr}{entry.changes}"
    assert not any(w.full_name in text for w in Worker.objects.all())
    assert not any(number_of(w) in text for w in Worker.objects.all())


def test_moi_lan_xuat_mot_dong_nhat_ky(workers):
    client = login_client(make_user("ADMIN"))
    client.get("/ho-so/xuat-excel/")
    client.get("/ho-so/xuat-excel/?trang_thai_ho_so=VERIFIED")
    assert AuditLog.objects.filter(action="EXPORT").count() == 2


def test_so_truy_van_khong_tang_theo_so_dong(workers, django_assert_max_num_queries):
    client = login_client(make_user("ADMIN"))
    client.get("/ho-so/xuat-excel/")
    with django_assert_max_num_queries(20):
        assert client.get("/ho-so/xuat-excel/").status_code == 200
    for _ in range(15):
        employ(make_worker_full(), "ACTIVE")
    with django_assert_max_num_queries(20):
        assert client.get("/ho-so/xuat-excel/").status_code == 200
