"""Dashboard `/` (Phase 7, bước 3): 9 thẻ khớp danh sách đích, biểu đồ, việc cần làm, quyền.

Kịch bản nghiệm thu 10 (hợp đồng hết hạn sau 20 ngày hiện ở thẻ) và 11 (thẻ Thiếu giấy tờ mở đúng
danh sách, số dòng bằng số trên thẻ) chạy với thẻ thật ở đây.
"""

import datetime
import json
import re

import pytest
from django.utils import timezone

from apps.core.choices import VerificationStatus as VS
from apps.core.models import ClientCompany, EducationLevel, Position
from apps.employment import assignments as svc
from apps.employment.models import Contract, Employment
from apps.recruitment.models import Education
from apps.reports import stats
from apps.workers.models import IdentityDocument, Worker
from tests.factories import (
    login_client,
    make_application,
    make_document,
    make_employment,
    make_user,
    make_worker_full,
    make_worker_in_status,
)

pytestmark = pytest.mark.django_db
ALL_TYPES = ("CCCD_FRONT", "CCCD_BACK", "PORTRAIT", "CV")
TODAY = timezone.localdate()


def days(n):
    return TODAY + datetime.timedelta(days=n)


def get(role, path="/"):
    response = login_client(make_user(role)).get(path)
    assert response.status_code == 200, path
    return response.content.decode()


def total(content):
    match = re.search(r"Hiển thị[^/]*/\s*(\d+)", content)
    return int(match.group(1)) if match else 0


def card_map(role):
    user = make_user(role)
    return {c["code"]: c for c in stats.cards(user)}


def full_documents(worker):
    for code in ALL_TYPES:
        make_document(worker, code)


def employ(worker, status="ACTIVE", *, section=True, resign=None):
    emp = make_employment(worker, status)
    if not section:
        Employment.objects.filter(pk=emp.pk).update(section=None)
    if resign:
        Employment.objects.filter(pk=emp.pk).update(resign_date=resign)
    Worker.objects.filter(pk=worker.pk).update(employee_code=f"CN-T{worker.pk:05d}")
    return emp


def contract(worker, expiry):
    return Contract.objects.create(
        worker=worker,
        contract_no=f"HD-{worker.pk}-{expiry}",
        contract_type="FIXED_TERM",
        signed_date=days(-300),
        effective_date=days(-300),
        expiry_date=expiry,
        created_by=worker.created_by,
    )


@pytest.fixture
def dataset():
    """Bộ dữ liệu đủ để mỗi thẻ có số khác 0 và có hồ sơ nằm ngoài từng thẻ."""
    out = {}
    out["draft"] = make_worker_full(full_name="Nháp Một")
    out["pending"] = make_worker_in_status(VS.PENDING)
    out["needs"] = make_worker_in_status(VS.NEEDS_INFO)
    out["archived"] = make_worker_in_status(VS.ARCHIVED)
    verified = make_worker_in_status(VS.VERIFIED)
    full_documents(verified)  # Hoàn thiện
    out["complete"] = verified
    out["verified_missing"] = make_worker_in_status(VS.VERIFIED)  # Đã xác minh nhưng thiếu giấy tờ
    working = make_worker_in_status(VS.VERIFIED)
    employ(working, "ACTIVE")
    contract(working, days(20))  # kịch bản 10
    out["working"] = working
    probation = make_worker_full(full_name="Thử Việc")
    employ(probation, "PROBATION", section=False)  # chưa có bộ phận
    out["probation"] = probation
    resigned = make_worker_full(full_name="Nghỉ Tháng Này")
    employ(resigned, "RESIGNED", resign=TODAY)
    out["resigned"] = resigned
    make_application(out["draft"], "NEW")
    make_application(out["pending"], "INTERVIEW")
    make_application(out["needs"], "PASSED")
    return out


# --- Quyền -----------------------------------------------------------------------------------
def test_chua_dang_nhap_chuyen_ve_dang_nhap():
    from django.test import Client

    response = Client().get("/")
    assert response.status_code == 302 and response.url.startswith("/dang-nhap/")


@pytest.mark.parametrize("role", ["ADMIN", "HR_MANAGER", "HR_STAFF", "VIEWER"])
def test_moi_vai_tro_xem_duoc_dashboard(role, dataset):
    content = get(role)
    assert "Tổng quan" in content
    for label in (
        "Tổng số hồ sơ",
        "Đang làm việc",
        "Hồ sơ mới trong tháng",
        "Chờ duyệt",
        "Thiếu giấy tờ",
        "Hoàn thiện",
        "Đang tuyển dụng",
        "Nghỉ việc trong tháng",
        "Hợp đồng sắp hết hạn",
    ):
        assert label in content


# --- Thẻ ---------------------------------------------------------------------------------------
def test_co_dung_9_the_theo_thu_tu_trang_md():
    codes = [c["code"] for c in card_map("ADMIN").values()]
    assert codes == [
        "total",
        "working",
        "new_month",
        "pending",
        "missing",
        "complete",
        "recruiting",
        "resigned",
        "contracts",
    ]


def test_gia_tri_the_theo_du_lieu(dataset):
    cards = card_map("ADMIN")
    assert cards["total"]["value"] == Worker.objects.exclude(verification_status="ARCHIVED").count()
    assert cards["working"]["value"] == 2  # ACTIVE + PROBATION
    assert cards["pending"]["value"] == 1
    assert cards["complete"]["value"] == 1
    assert cards["recruiting"]["value"] == 2  # NEW + INTERVIEW (PASSED không tính)
    assert cards["resigned"]["value"] == 1
    assert cards["contracts"]["value"] == 1


@pytest.mark.parametrize("role", ["ADMIN", "HR_MANAGER", "HR_STAFF", "VIEWER"])
def test_moi_the_mo_danh_sach_loc_dung_so_dong_bang_so_tren_the(role, dataset):
    """Kịch bản 11 tổng quát: bấm thẻ nào thì số dòng danh sách đích bằng số trên thẻ."""
    user = make_user(role)
    client = login_client(user)
    for card in stats.cards(user):
        page = client.get(card["url"])
        assert page.status_code == 200, card["url"]
        assert total(page.content.decode()) == card["value"], card["code"]


def test_kich_ban_10_hop_dong_het_han_sau_20_ngay_hien_o_the(dataset):
    before = card_map("ADMIN")["contracts"]["value"]
    worker = make_worker_full(full_name="Hợp Đồng Mới")
    employ(worker, "ACTIVE")
    contract(worker, days(20))
    contract(worker, days(200))  # hợp đồng khác còn xa không làm tăng thẻ
    after = card_map("ADMIN")["contracts"]
    assert after["value"] == before + 1
    listing = get("ADMIN", after["url"])
    assert "Hợp Đồng Mới" in listing and total(listing) == after["value"]


def test_kich_ban_11_the_thieu_giay_to_khong_tinh_luu_tru(dataset):
    card = card_map("ADMIN")["missing"]
    archived_missing = Worker.objects.get(verification_status="ARCHIVED")
    listing = get("ADMIN", card["url"])
    assert total(listing) == card["value"]
    assert archived_missing.full_name not in listing  # hồ sơ Lưu trữ thiếu giấy tờ không tính
    assert card["value"] == Worker.objects.exclude(verification_status="ARCHIVED").count() - 1
    assert "chua-luu-tru" in card["url"] and "thieu_giay_to=1" in card["url"]


def test_hoan_thien_lon_hon_0_khi_co_tai_lieu(dataset):
    assert card_map("ADMIN")["complete"]["value"] == 1


def test_lien_ket_the_dung_tham_so_trang_md():
    urls = {c["code"]: c["url"] for c in card_map("ADMIN").values()}
    assert urls["total"] == "/ho-so/?trang_thai_ho_so=chua-luu-tru"
    assert urls["working"] == "/ho-so/?trang_thai_lam_viec=PROBATION%2CACTIVE"
    assert urls["pending"] == "/ho-so/?trang_thai_ho_so=PENDING"
    assert urls["complete"] == "/ho-so/?hoan_thien=1"
    assert urls["recruiting"] == "/tuyen-dung/?trang_thai=NEW%2CSCREENING%2CINTERVIEW"
    assert urls["contracts"] == "/ho-so/?hop_dong_sap_het_han=1"
    first = TODAY.replace(day=1).strftime("%d/%m/%Y")
    assert f"tao_tu={first.replace('/', '%2F')}" in urls["new_month"]
    assert "nghi_tu=" in urls["resigned"] and "trang_thai_lam_viec=RESIGNED" in urls["resigned"]


def test_the_hoso_moi_trong_thang_tinh_theo_ngay_tao(dataset):
    first = TODAY.replace(day=1)
    in_month = Worker.objects.filter(created_at__date__gte=first).count()
    old = make_worker_full(full_name="Cũ Từ Lâu")
    Worker.objects.filter(pk=old.pk).update(created_at=timezone.now() - datetime.timedelta(days=80))
    card = card_map("ADMIN")["new_month"]
    assert card["value"] == in_month  # hồ sơ tạo 80 ngày trước không tính
    assert total(get("ADMIN", card["url"])) == in_month


# --- Biểu đồ -----------------------------------------------------------------------------------
def chart_json(content, chart_id):
    match = re.search(rf'<script id="{chart_id}" type="application/json">(.*?)</script>', content)
    assert match, chart_id
    return json.loads(match.group(1))


def test_bon_khung_bieu_do_co_tieu_de_va_don_vi(dataset):
    content = get("VIEWER")
    for chart_id in (
        "chart-in-out",
        "chart-department",
        "chart-gender",
        "chart-age",
        "chart-education",
        "chart-verification",
    ):
        cfg = chart_json(content, chart_id)
        assert cfg["unit"] and cfg["labels"]
        assert f'data-pa-chart="{chart_id}"' in content
    assert chart_json(content, "chart-in-out")["datasets"][0]["label"] == "Vào làm"
    assert len(chart_json(content, "chart-in-out")["labels"]) == 12
    assert chart_json(content, "chart-department")["horizontal"] is True


def test_co_cau_tinh_cong_nhan_dang_lam_va_tong_nhom_tuoi_khop(dataset):
    working = stats.working_workers().count()
    assert working == 2
    assert sum(n for _, n in stats.by_age_group()) == working  # kể cả "Chưa có ngày sinh"
    assert sum(n for _, n in stats.by_gender()) == working
    assert sum(r[1] for r in stats.by_department()) == working
    assert sum(r[1] for r in stats.by_education()) == working


def test_nhom_chua_co_bo_phan_o_bieu_do_phong_ban(dataset):
    labels = chart_json(get("ADMIN"), "chart-department")["labels"]
    assert "Chưa có bộ phận" in labels and "Phòng ban test" in labels
    rows = stats.by_section()
    assert ("—", "Chưa có bộ phận") in [(r[0], r[1]) for r in rows]


def test_nhom_tuoi_5_nhom_va_chua_co_ngay_sinh(dataset):
    Worker.objects.filter(pk=dataset["working"].pk).update(
        date_of_birth=TODAY.replace(year=TODAY.year - 17)
    )
    Worker.objects.filter(pk=dataset["probation"].pk).update(date_of_birth=None)
    groups = dict(stats.by_age_group())
    assert list(groups) == ["Dưới 18", "18–25", "26–35", "36–45", "Trên 45", "Chưa có ngày sinh"]
    assert groups["Dưới 18"] == 1 and groups["Chưa có ngày sinh"] == 1


def test_trinh_do_cao_nhat_cua_moi_nguoi(dataset):
    low = EducationLevel.objects.order_by("rank").first()
    high = EducationLevel.objects.order_by("rank").last()
    for level in (low, high):
        Education.objects.create(
            worker=dataset["working"], education_level=level, school_name="Trường Giả",
            start_year=2010, end_year=2013,
        )  # fmt: skip
    rows = {r[0]: r[1] for r in stats.by_education()}
    assert rows[high.name] == 1 and rows[low.name] == 0  # chỉ tính bậc cao nhất
    assert rows["Chưa có"] == 1  # người còn lại chưa có học vấn


def test_bieu_do_vao_lam_nghi_viec_12_thang(dataset):
    start, end = stats.last_12_months()
    flow = stats.hires_and_exits(start, end)
    assert len(flow) == 12
    assert sum(r[2] for r in flow) == 1  # một người nghỉ hôm nay
    assert sum(r[1] for r in flow) == Employment.objects.filter(start_date__gte=start).count()


def test_bieu_do_trang_thai_xac_minh_dem_moi_ho_so(dataset):
    rows = dict(stats.by_verification_status())
    assert sum(rows.values()) == Worker.objects.count()
    assert rows["Lưu trữ"] == 1 and rows["Chờ duyệt"] == 1


# --- Việc cần làm ------------------------------------------------------------------------------
def blocks(role):
    return {b["code"]: b for b in stats.todo_blocks(make_user(role))}


def test_khoi_cho_duyet_chi_hien_voi_quan_ly_va_admin(dataset):
    assert "pending" in blocks("ADMIN") and "pending" in blocks("HR_MANAGER")
    assert "pending" not in blocks("HR_STAFF") and "pending" not in blocks("VIEWER")
    assert "Chờ duyệt (1)" in get("HR_MANAGER")
    assert "Chờ duyệt (" not in get("HR_STAFF").split("Việc cần làm")[1]


def test_khoi_viec_can_lam_so_luong_bang_danh_sach_dich(dataset):
    IdentityDocument.objects.filter(worker=dataset["working"]).update(expiry_date=days(5))
    by_code = blocks("ADMIN")
    assert [b["code"] for b in by_code.values()] == [
        "pending",
        "needs_info",
        "id_expiring",
        "assignment_due",
    ]
    for block in by_code.values():
        assert total(get("ADMIN", block["url"])) == block["count"], block["code"]
    assert by_code["id_expiring"]["count"] == 1 and by_code["needs_info"]["count"] == 1


def test_khoi_dot_lam_viec_sap_du_12_thang(dataset):
    worker = dataset["working"]
    client = ClientCompany.objects.get_or_create(name="Công ty Mẫu A", location="Tỉnh Một")[0]
    position = Position.objects.get(name="Chức danh test")
    Employment.objects.filter(worker=worker).update(start_date=days(-400))
    svc.add_assignment(
        make_user("HR_STAFF"),
        worker,
        client_company=client,
        position=position,
        start_date=days(-350),  # đủ 12 tháng sau khoảng 15 ngày
    )
    block = blocks("VIEWER")["assignment_due"]
    assert block["count"] == 1 and block["title"] == "Đợt làm việc sắp đủ 12 tháng"
    row = block["rows"][0]
    assert row["client"] == "Công ty Mẫu A – Tỉnh Một" and row["start"] == days(-350)
    assert block["url"] == "/ho-so/?dot_sap_du_han=1"
    assert total(get("VIEWER", block["url"])) == 1
    assert "Đợt làm việc sắp đủ 12 tháng (1)" in get("VIEWER")


def test_khoi_rong_hien_empty_state_va_chi_hien_10_dong():
    for _ in range(12):
        make_worker_in_status(VS.NEEDS_INFO)
    needs = blocks("ADMIN")["needs_info"]
    assert needs["count"] == 12 and len(needs["rows"]) == 10
    content = get("ADMIN")
    assert "Xem tất cả (12)" in content
    assert "Không có việc nào cần làm." in content  # các khối còn lại trống


def test_nguoi_dung_khong_thay_thong_tin_nhay_cam_tren_dashboard(dataset):
    content = get("VIEWER")
    numbers = [i.id_number_enc for i in IdentityDocument.objects.all()]
    assert numbers and all(number not in content for number in numbers)


def test_dashboard_so_truy_van_khong_tang_theo_so_ho_so(dataset, django_assert_max_num_queries):
    client = login_client(make_user("ADMIN"))
    client.get("/")  # làm nóng bộ nhớ đệm đăng nhập
    with django_assert_max_num_queries(90):
        assert client.get("/").status_code == 200
    for _ in range(15):
        make_worker_full()
    with django_assert_max_num_queries(90):
        assert client.get("/").status_code == 200
