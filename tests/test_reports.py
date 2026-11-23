"""Báo cáo /bao-cao/ (Phase 7, bước 4): 9 loại, quyền xem/xuất/in (câu 18), Excel, nhật ký."""

import io
import re

import pytest
from django.utils import timezone
from openpyxl import load_workbook

from apps.audit.models import AuditLog
from apps.core.choices import VerificationStatus as VS
from apps.core.models import ClientCompany, Department, Position
from apps.employment import assignments as svc
from apps.employment.models import Employment
from apps.reports import reports, stats
from tests.factories import (
    login_client,
    make_user,
    make_worker_full,
    make_worker_in_status,
)
from tests.test_dashboard import contract, days, employ, full_documents, total

pytestmark = pytest.mark.django_db
CODES = [d.code for d in reports.REPORTS]
TODAY = timezone.localdate()


def get(role, path, expect=200):
    response = login_client(make_user(role)).get(path)
    assert response.status_code == expect, (role, path, response.status_code)
    return response


def sheet_rows(response):
    book = load_workbook(io.BytesIO(response.content), data_only=False)
    return [[c.value for c in row] for row in book.active.iter_rows()]


@pytest.fixture
def data():
    """Công nhân đang làm ở hai phòng ban và một người chưa có bộ phận, có công ty khách."""
    other_dep = Department.objects.create(name="Phòng ban khác")
    from apps.core.models import Section

    other_section = Section.objects.create(department=other_dep, name="Bộ phận khác")
    a = make_worker_in_status(VS.VERIFIED)
    full_documents(a)
    employ(a, "ACTIVE")
    b = make_worker_full(full_name="Làm Khác Phòng")
    employ(b, "PROBATION")
    Employment.objects.filter(worker=b).update(section=other_section)
    c = make_worker_full(full_name="Chưa Có Bộ Phận")
    employ(c, "ACTIVE", section=False)
    resigned = make_worker_full(full_name="Đã Nghỉ")
    employ(resigned, "RESIGNED", resign=TODAY)
    company = ClientCompany.objects.create(name="Công ty Mẫu A", location="Tỉnh Một")
    position = Position.objects.get(name="Chức danh test")
    Employment.objects.filter(worker__in=[a, b]).update(start_date=days(-100))
    for worker in (a, b):
        svc.add_assignment(
            make_user("HR_STAFF"),
            worker,
            client_company=company,
            position=position,
            start_date=days(-30),
        )
    contract(a, days(200))
    return {"a": a, "b": b, "c": c, "other_dep": other_dep, "company": company}


# --- Quyền (câu 18) --------------------------------------------------------------------------
def test_chua_dang_nhap_chuyen_ve_dang_nhap():
    from django.test import Client

    for path in ("/bao-cao/", "/bao-cao/xuat-excel/", "/bao-cao/in/"):
        response = Client().get(path)
        assert response.status_code == 302 and response.url.startswith("/dang-nhap/")


@pytest.mark.parametrize(
    ("role", "page", "export", "printing"),
    [
        ("ADMIN", 200, 200, 200),
        ("HR_MANAGER", 200, 200, 200),
        ("HR_STAFF", 200, 200, 200),
        ("VIEWER", 200, 403, 403),
    ],
)
def test_phan_quyen_xem_xuat_in(role, page, export, printing):
    get(role, "/bao-cao/", page)
    get(role, "/bao-cao/xuat-excel/", export)
    get(role, "/bao-cao/in/", printing)


def test_viewer_khong_thay_nut_in_va_xuat_con_nhan_vien_thi_thay(data):
    viewer = get("VIEWER", "/bao-cao/").content.decode()
    assert "Xuất Excel" not in viewer and ">In<" not in viewer
    assert "/bao-cao/xuat-excel/" not in viewer and "/bao-cao/in/" not in viewer
    staff = get("HR_STAFF", "/bao-cao/").content.decode()
    assert "Xuất Excel" in staff and ">In<" in staff


def test_viewer_goi_thang_url_xuat_va_in_khong_ghi_nhat_ky(data):
    before = AuditLog.objects.filter(action__in=["EXPORT", "PRINT"]).count()
    get("VIEWER", "/bao-cao/xuat-excel/?loai=gioi-tinh", 403)
    get("VIEWER", "/bao-cao/in/?loai=gioi-tinh", 403)
    assert AuditLog.objects.filter(action__in=["EXPORT", "PRINT"]).count() == before


# --- Chín loại ---------------------------------------------------------------------------------
def test_co_dung_9_loai_bao_cao_gom_cong_ty_khach():
    assert len(CODES) == 9 and "cong-ty-khach" in CODES
    titles = [d.title for d in reports.REPORTS]
    assert "Công nhân đang làm theo công ty khách hàng" in titles


@pytest.mark.parametrize("code", CODES)
@pytest.mark.parametrize("role", ["ADMIN", "VIEWER"])
def test_moi_loai_xem_duoc_co_bieu_do_bang_va_dong_tong(code, role, data):
    content = get(role, f"/bao-cao/?loai={code}").content.decode()
    title = reports.BY_CODE[code].title
    assert title in content and 'data-pa-chart="chart-report"' in content
    assert "Tổng" in content


@pytest.mark.parametrize("code", CODES)
def test_so_lieu_bao_cao_khop_danh_sach_dich(code, data):
    """Mỗi số có liên kết thì số dòng danh sách đích bằng số đó (cùng vai trò xem)."""
    user = make_user("HR_STAFF")
    client = login_client(user)
    ctx = reports.ReportContext(code=code, start=days(-365), end=TODAY)
    report = reports.build_report(ctx)
    linked = 0
    for row in report.rows:
        for cell in row.values():
            if isinstance(cell, dict) and cell.get("url"):
                linked += 1
                page = client.get(cell["url"])
                assert page.status_code == 200
                assert total(page.content.decode()) == cell["text"], (code, row, cell["url"])
    if code in ("phong-ban", "chuc-danh", "cong-ty-khach", "trinh-do", "hoan-thien"):
        assert linked > 0


def test_dong_tong_bang_tong_cac_dong(data):
    for code in CODES:
        report = reports.build_report(reports.ReportContext(code, days(-365), TODAY))
        for column in report.columns:
            if column["kind"] == "link":
                key = column["key"]
                assert reports.plain(report.total[key]) == sum(
                    reports.plain(r[key]) for r in report.rows
                ), (code, key)


def test_co_cau_tinh_cong_nhan_dang_lam_khong_tinh_da_nghi(data):
    report = reports.build_report(reports.ReportContext("gioi-tinh", days(-365), TODAY))
    assert reports.plain(report.total["n"]) == 3  # a, b, c; người đã nghỉ không tính


def test_nhom_chua_co_bo_phan_o_bao_cao_phong_ban(data):
    report = reports.build_report(reports.ReportContext("phong-ban", days(-365), TODAY))
    none_row = next(r for r in report.rows if r["sec"] == "Chưa có bộ phận")
    assert reports.plain(none_row["n"]) == 1
    assert (
        none_row["n"]["url"].endswith("bo_phan=chua-co")
        or "bo_phan=chua-co" in none_row["n"]["url"]
    )


def test_loc_phong_ban_thu_hep_va_nhom_chua_co(data):
    other = data["other_dep"]
    narrowed = reports.build_report(
        reports.ReportContext("gioi-tinh", days(-365), TODAY, department=other)
    )
    assert reports.plain(narrowed.total["n"]) == 1
    none = reports.build_report(
        reports.ReportContext("gioi-tinh", days(-365), TODAY, department=stats.NO_SECTION)
    )
    assert reports.plain(none.total["n"]) == 1
    page = get("ADMIN", f"/bao-cao/?loai=gioi-tinh&phong_ban={other.pk}").content.decode()
    assert "Phòng ban: Phòng ban khác" in page
    none_page = get("ADMIN", "/bao-cao/?loai=gioi-tinh&phong_ban=chua-co").content.decode()
    assert "Phòng ban: Chưa có bộ phận" in none_page


def test_bao_cao_cong_ty_khach_dem_cong_nhan_co_dot_dang_dien_ra(data):
    report = reports.build_report(reports.ReportContext("cong-ty-khach", days(-365), TODAY))
    assert [(r["company"], r["location"], reports.plain(r["n"])) for r in report.rows] == [
        ("Công ty Mẫu A", "Tỉnh Một", 2)
    ]
    assert report.rows[0]["n"]["url"] == f"/ho-so/?cong_ty_khach={data['company'].pk}"
    # Có lọc phòng ban: liên kết giữ tham số để số dòng đích vẫn bằng số trên báo cáo.
    narrowed = reports.build_report(
        reports.ReportContext("cong-ty-khach", days(-365), TODAY, department=data["other_dep"])
    )
    cell = narrowed.rows[0]["n"]
    assert cell["text"] == 1 and f"phong_ban={data['other_dep'].pk}" in cell["url"]


# --- Khoảng ngày chỉ áp cho báo cáo theo tháng -----------------------------------------------
def test_khoang_ngay_chi_ap_cho_bao_cao_theo_thang(data):
    wide = reports.build_report(reports.ReportContext("gioi-tinh", days(-900), TODAY))
    narrow = reports.build_report(reports.ReportContext("gioi-tinh", days(-5), days(-4)))
    assert wide.total == narrow.total  # cơ cấu không đổi theo khoảng ngày
    flow = reports.build_report(reports.ReportContext("vao-lam-nghi-viec", days(-5), days(-4)))
    assert sum(reports.plain(r["hires"]) for r in flow.rows) == 0


def test_bao_cao_theo_thang_dem_dung_trong_khoang(data):
    start = TODAY.replace(day=1)
    new = reports.build_report(reports.ReportContext("ho-so-moi", start, TODAY))
    assert len(new.rows) == 1
    from apps.workers.models import Worker

    created = Worker.objects.filter(created_at__date__gte=start).count()
    assert reports.plain(new.total["n"]) == created
    flow = reports.build_report(reports.ReportContext("vao-lam-nghi-viec", start, TODAY))
    assert sum(reports.plain(r["exits"]) for r in flow.rows) == 1  # "Đã Nghỉ" hôm nay


def test_khoang_ngay_sai_hien_loi_va_van_dung_mac_dinh():
    content = get("ADMIN", "/bao-cao/?loai=ho-so-moi&tu_ngay=01/12/2026&den_ngay=01/01/2026")
    text = content.content.decode()
    assert "Đến ngày phải sau hoặc bằng từ ngày." in text
    assert 'data-pa-chart="chart-report"' in text or "Không có số liệu" in text
    long_range = get("ADMIN", "/bao-cao/?loai=ho-so-moi&tu_ngay=01/01/2015&den_ngay=01/01/2026")
    assert "Khoảng thời gian tối đa 60 tháng." in long_range.content.decode()
    bad = get("ADMIN", "/bao-cao/?loai=khong-co").content.decode()
    assert "Thống kê báo cáo" in bad


def test_khong_co_du_lieu_hien_empty_state():
    content = get("ADMIN", "/bao-cao/?loai=gioi-tinh").content.decode()
    assert "Không có số liệu trong khoảng đã chọn." in content
    assert 'data-pa-chart="chart-report"' not in content


# --- Excel -----------------------------------------------------------------------------------
def test_xuat_excel_noi_dung_khop_bao_cao(data):
    response = get("HR_STAFF", "/bao-cao/xuat-excel/?loai=gioi-tinh")
    assert response["Content-Type"].startswith("application/vnd.openxmlformats")
    assert (
        "attachment" in response["Content-Disposition"]
        and ".xlsx" in response["Content-Disposition"]
    )
    rows = sheet_rows(response)
    assert rows[0][0] == "Công nhân theo giới tính"
    assert rows[1][0].startswith("Công nhân đang làm")
    assert rows[2][0] == f"Ngày lập: {TODAY:%d/%m/%Y}" and rows[2][1].startswith("Người lập: ")
    header = rows.index(["Giới tính", "Số công nhân"])
    assert rows[header + 1][0] == "Nam" and rows[-1] == ["Tổng", 3]
    assert len(rows) - header - 1 == 3  # Nam, Nữ + Tổng


def test_xuat_excel_moi_o_qua_safe_cell_khong_co_cong_thuc(data):
    Position.objects.filter(name="Chức danh test").update(name='=HYPERLINK("http://x","a")')
    response = get("ADMIN", "/bao-cao/xuat-excel/?loai=chuc-danh")
    book = load_workbook(io.BytesIO(response.content), data_only=False)
    cells = [c for row in book.active.iter_rows() for c in row]
    assert all(c.data_type != "f" for c in cells)
    assert any(isinstance(c.value, str) and c.value.startswith("'=HYPERLINK") for c in cells)


def test_xuat_excel_bo_loc_sai_khong_xuat_khong_ghi_nhat_ky():
    client = login_client(make_user("ADMIN"))
    response = client.get(
        "/bao-cao/xuat-excel/?loai=ho-so-moi&tu_ngay=01/12/2026&den_ngay=01/01/2026"
    )
    assert response.status_code == 302 and response.url.startswith("/bao-cao/?")
    assert not AuditLog.objects.filter(action="EXPORT").exists()


# --- Nhật ký + in ---------------------------------------------------------------------------
def test_xuat_va_in_ghi_nhat_ky_khong_ho_ten(data):
    user = make_user("HR_MANAGER")
    client = login_client(user)
    client.get("/bao-cao/xuat-excel/?loai=phong-ban&phong_ban=chua-co")
    client.get("/bao-cao/in/?loai=ho-so-moi")
    export = AuditLog.objects.get(action="EXPORT")
    printing = AuditLog.objects.get(action="PRINT")
    assert export.user == user and printing.user == user
    assert export.object_type == "report" and export.object_id == "phong-ban"
    assert export.object_repr == "Công nhân theo phòng ban và bộ phận"
    assert "phòng ban: Chưa có bộ phận" in export.note
    assert "từ " in printing.note and "đến " in printing.note
    for entry in (export, printing):
        text = f"{entry.note}{entry.object_repr}{entry.changes}"
        assert not re.search(r"Làm Khác Phòng|Chưa Có Bộ Phận|Đã Nghỉ", text)


def test_ban_in_co_tieu_de_ngay_lap_nguoi_lap_va_nut_in(data):
    user = make_user("HR_STAFF")
    user.full_name = "Người Lập Mẫu"
    user.save()
    response = login_client(user).get("/bao-cao/in/?loai=nhom-tuoi")
    content = response.content.decode()
    assert response.status_code == 200
    assert "Công nhân theo nhóm tuổi" in content
    assert f"Ngày lập: {TODAY:%d/%m/%Y}" in content and "Người lập: Người Lập Mẫu" in content
    assert "In báo cáo" in content and "d-print-none" in content
    assert "Chưa có ngày sinh" in content


def test_so_truy_van_cua_bao_cao_khong_tang_theo_so_ho_so(data, django_assert_max_num_queries):
    client = login_client(make_user("ADMIN"))
    client.get("/bao-cao/")
    with django_assert_max_num_queries(40):
        assert client.get("/bao-cao/?loai=phong-ban").status_code == 200
    for _ in range(10):
        employ(make_worker_full(), "ACTIVE")
    with django_assert_max_num_queries(40):
        assert client.get("/bao-cao/?loai=phong-ban").status_code == 200
