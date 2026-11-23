"""Danh sách hồ sơ: cột, tìm không dấu, bộ lọc, sắp xếp, phân trang, giữ bộ lọc (IV.7)."""

import datetime
import re

import pytest

from apps.core.choices import VerificationStatus as VS
from apps.core.models import ClientCompany, Department, EducationLevel, Position, Section
from apps.employment.models import Employment, WorkAssignment
from apps.recruitment.models import Education
from apps.workers.models import IdentityDocument, Worker
from tests.factories import (
    login_client,
    make_application,
    make_document,
    make_user,
    make_worker_full,
    make_worker_in_status,
)

pytestmark = pytest.mark.django_db
D = datetime.date
STAFF = ["ADMIN", "HR_MANAGER", "HR_STAFF"]


def page(role="HR_STAFF", query=""):
    client = login_client(make_user(role))
    response = client.get("/ho-so/" + query)
    assert response.status_code == 200
    return response.content.decode()


def shown(content, *workers):
    """Những hồ sơ (trong số `workers`) có tên hiện trong bảng."""
    return [w for w in workers if w.full_name in content]


def named(name, **kw):
    return make_worker_full(full_name=name, **kw)


def employ(
    worker, *, section, position, work_status="ACTIVE", received=None, start=None, code=None
):
    if code:
        Worker.objects.filter(pk=worker.pk).update(employee_code=code)
    return Employment.objects.create(
        worker=worker,
        received_date=received or D(2026, 1, 1),
        start_date=start or D(2026, 1, 2),
        section=section,
        position=position,
        work_status=work_status,
    )


@pytest.fixture
def catalog():
    dep_a = Department.objects.create(name="Phòng A")
    dep_b = Department.objects.create(name="Phòng B")
    return {
        "dep_a": dep_a,
        "dep_b": dep_b,
        "sec_a": Section.objects.create(department=dep_a, name="Bộ phận A1"),
        "sec_b": Section.objects.create(department=dep_b, name="Bộ phận B1"),
        "pos_1": Position.objects.create(name="Thợ hàn"),
        "pos_2": Position.objects.create(name="Kế toán"),
    }


# ===== Cột =====================================================================================
def test_cot_dung_thu_tu_theo_muc_iv_7():
    # Đổi theo phiếu v1.1 (câu 48): cột "Bộ phận" của mục IV.7 thay bằng "Công ty khách".
    named("Hàng Đầu")
    content = page()
    headers = re.findall(r"<th[^>]*>(.*?)</th>", content)
    assert headers == [
        "STT",
        "Mã NV",
        "Họ và tên",
        "Ngày sinh",
        "Giới tính",
        "SĐT",
        "Công ty khách",
        "Chức danh",
        "Ngày vào làm",
        "TT hồ sơ",  # viết tắt theo phác thảo đã duyệt để 12 cột vừa khung 1366 px
        "TT làm việc",
        "Thao tác",
    ]


def test_hang_hien_du_lieu_ngay_dd_mm_yyyy_o_trong_la_gach(catalog):
    w = named("Dòng Đủ Dữ Liệu", date_of_birth=D(1990, 3, 7), phone="0911000999")
    employ(
        w, section=catalog["sec_a"], position=catalog["pos_1"], start=D(2026, 2, 3), code="CN-00777"
    )
    WorkAssignment.objects.create(  # cột "Công ty khách" lấy từ đợt đang diễn ra (câu 48)
        worker=w,
        client_company=ClientCompany.objects.create(name="Công ty Khách Mẫu", location="Tỉnh Mẫu"),
        position=catalog["pos_1"],
        start_date=D(2026, 2, 3),
        created_by=w.created_by,
    )
    candidate = named("Ứng Viên Chưa Vào Làm")
    content = page()
    row = re.search(r"<tr>(?:(?!</tr>).)*Dòng Đủ Dữ Liệu.*?</tr>", content, re.S).group(0)
    for text in (
        "CN-00777",
        "07/03/1990",
        "Nam",
        "0911000999",
        "Công ty Khách Mẫu – Tỉnh Mẫu",
        "Thợ hàn",
        "03/02/2026",
    ):
        assert text in row
    assert "Nháp" in row and "Đang làm việc" in row
    row2 = re.search(r"<tr>(?:(?!</tr>).)*Ứng Viên Chưa Vào Làm.*?</tr>", content, re.S).group(0)
    assert row2.count("—") >= 4 and candidate.phone in row2


# ===== Tìm kiếm =================================================================================
def test_kich_ban_12_tim_khong_dau_ra_ho_so_co_dau():
    target = named("Nguyễn Văn An")
    other = named("Trần Thị Bình")
    content = page(query="?q=nguyen+van+an")
    assert shown(content, target, other) == [target]


@pytest.mark.parametrize(
    "query", ["Nguyễn Văn An", "NGUYEN VAN AN", "  nguyen   van an ", "van an", "Nguyen"]
)
def test_tim_ten_khong_phan_biet_dau_hoa_thuong_khoang_trang(query):
    target = named("Nguyễn Văn An")
    other = named("Lê Thị Cúc")
    assert shown(page(query=f"?q={query}"), target, other) == [target]


def test_tim_dong_chu_d_khong_dau():
    target = named("Đặng Đình Phúc")
    assert shown(page(query="?q=dang+dinh+phuc"), target) == [target]


def test_tim_theo_ma_ho_so_ma_nv_va_sdt(catalog):
    a = named("Người Một", phone="0911222333")
    b = named("Người Hai", phone="0944555666")
    employ(b, section=catalog["sec_a"], position=catalog["pos_1"], code="CN-00123")
    assert shown(page(query=f"?q={a.worker_code.lower()}"), a, b) == [a]
    assert shown(page(query="?q=cn-00123"), a, b) == [b]
    assert shown(page(query="?q=0911222333"), a, b) == [a]
    assert shown(page(query="?q=09112"), a, b) == [a]


def test_tim_khong_ra_gi_hien_trang_thai_rong():
    named("Có Người")
    content = page(query="?q=khongco")
    assert "Không có hồ sơ phù hợp." in content and "Xóa lọc" in content


@pytest.mark.parametrize("role", STAFF)
def test_nhan_vien_tim_theo_so_cccd_12_chu_so(role):
    a, b = named("Số Một"), named("Số Hai")
    IdentityDocument.objects.filter(worker=a).update(id_number_hash=None)
    identity = IdentityDocument.objects.get(worker=a)
    identity.id_number_enc = "999111222333"
    identity.save()
    content = page(role, "?q=999111222333")
    assert shown(content, a, b) == [a]
    assert shown(page(role, "?q=999+111+222+333"), a, b) == [a]  # gõ có khoảng trắng vẫn khớp


def test_viewer_nhap_so_cccd_khong_ra_ho_so_va_khong_tra_theo_bam():
    a = named("Số Một")
    identity = IdentityDocument.objects.get(worker=a)
    identity.id_number_enc = "999111222333"
    identity.save()
    assert shown(page("VIEWER", "?q=999111222333"), a) == []


# ===== Bộ lọc ===================================================================================
def test_loc_phong_ban_bo_phan_chuc_danh(catalog):
    a = named("Lọc A")
    b = named("Lọc B")
    c = named("Lọc C")
    employ(a, section=catalog["sec_a"], position=catalog["pos_1"])
    employ(b, section=catalog["sec_b"], position=catalog["pos_2"])
    ws = (a, b, c)
    assert shown(page(query=f"?phong_ban={catalog['dep_a'].pk}"), *ws) == [a]
    assert shown(page(query=f"?bo_phan={catalog['sec_b'].pk}"), *ws) == [b]
    assert shown(page(query=f"?chuc_danh={catalog['pos_2'].pk}"), *ws) == [b]
    both = f"?phong_ban={catalog['dep_a'].pk}&chuc_danh={catalog['pos_2'].pk}"
    assert shown(page(query=both), *ws) == []


def test_loc_ba_bo_trang_thai(catalog):
    draft = named("Nháp Một")
    verified = make_worker_in_status(VS.VERIFIED)
    Worker.objects.filter(pk=verified.pk).update(full_name="Đã Xác Minh Một")
    verified.refresh_from_db()
    working = named("Đang Làm Một")
    employ(working, section=catalog["sec_a"], position=catalog["pos_1"], work_status="PROBATION")
    resigned = named("Đã Nghỉ Một")
    employ(resigned, section=catalog["sec_a"], position=catalog["pos_1"], work_status="RESIGNED")
    applying = named("Đang Tuyển Một")
    make_application(applying, "INTERVIEW")
    ws = (draft, verified, working, resigned, applying)
    assert shown(page(query="?trang_thai_ho_so=VERIFIED"), *ws) == [verified]
    assert set(shown(page(query="?trang_thai_ho_so=DRAFT"), *ws)) == {
        draft,
        working,
        resigned,
        applying,
    }
    assert shown(page(query="?trang_thai_lam_viec=PROBATION"), *ws) == [working]
    assert shown(page(query="?trang_thai_lam_viec=RESIGNED"), *ws) == [resigned]
    assert shown(page(query="?trang_thai_tuyen_dung=INTERVIEW"), *ws) == [applying]


def test_loc_trang_thai_tuyen_dung_xet_lan_ung_tuyen_gan_nhat():
    mover = named("Đổi Trạng Thái")
    make_application(mover, "FAILED", result_date=D(2025, 5, 1), applied_date=D(2025, 5, 1))
    make_application(mover, "SCREENING", applied_date=D(2026, 5, 1))
    assert shown(page(query="?trang_thai_tuyen_dung=SCREENING"), mover) == [mover]
    assert shown(page(query="?trang_thai_tuyen_dung=FAILED"), mover) == []


def test_loc_trinh_do_cao_nhat_cua_moi_nguoi():
    low, high, none = named("Học Thấp"), named("Học Cao"), named("Không Học")
    level = {r: EducationLevel.objects.get(rank=r) for r in (4, 6, 7)}
    Education.objects.create(worker=low, education_level=level[4], school_name="T")
    Education.objects.create(worker=high, education_level=level[4], school_name="T")
    Education.objects.create(worker=high, education_level=level[7], school_name="U")
    ws = (low, high, none)
    assert shown(page(query=f"?trinh_do={level[4].pk}"), *ws) == [low]  # cao nhất = THPT
    assert shown(page(query=f"?trinh_do={level[7].pk}"), *ws) == [high]
    assert shown(page(query=f"?trinh_do={level[6].pk}"), *ws) == []


def test_loc_thieu_giay_to_va_hoan_thien_so_dong_bang_so_hop_le():
    complete = make_worker_in_status(VS.VERIFIED)
    for code in ("CCCD_FRONT", "CCCD_BACK", "PORTRAIT", "CV"):
        make_document(complete, code)
    verified_missing = make_worker_in_status(VS.VERIFIED)
    make_document(verified_missing, "CV")
    draft_full = named("Nháp Đủ Giấy Tờ")
    for code in ("CCCD_FRONT", "CCCD_BACK", "PORTRAIT", "CV"):
        make_document(draft_full, code)
    ws = (complete, verified_missing, draft_full)
    content = page(query="?thieu_giay_to=1")
    assert shown(content, *ws) == [verified_missing]
    assert "/ 1" in content  # kịch bản 11: số dòng bằng số hồ sơ thiếu giấy tờ
    assert shown(page(query="?hoan_thien=1"), *ws) == [complete]
    # Dùng cùng lúc hai bộ lọc không gây lỗi và cho giao rỗng.
    assert shown(page(query="?hoan_thien=1&thieu_giay_to=1"), *ws) == []


def test_loc_khoang_ngay_tiep_nhan(catalog):
    early, late, none = named("Tiếp Nhận Sớm"), named("Tiếp Nhận Muộn"), named("Chưa Tiếp Nhận")
    employ(early, section=catalog["sec_a"], position=catalog["pos_1"], received=D(2026, 1, 10))
    employ(late, section=catalog["sec_a"], position=catalog["pos_1"], received=D(2026, 6, 10))
    ws = (early, late, none)
    assert shown(page(query="?tiep_nhan_tu=01/06/2026"), *ws) == [late]
    assert shown(page(query="?tiep_nhan_den=31/01/2026"), *ws) == [early]
    assert shown(page(query="?tiep_nhan_tu=10/01/2026&tiep_nhan_den=10/06/2026"), *ws) == [
        early,
        late,
    ]


def test_ngay_sai_dinh_dang_bao_loi_khong_sap_trang():
    named("Vẫn Hiện")
    content = page(query="?tiep_nhan_tu=2026-01-01")
    assert "Nhập ngày đúng định dạng dd/mm/yyyy." in content and "Vẫn Hiện" in content


# ===== Sắp xếp =================================================================================
def order_of(content, *workers):
    positions = {w: content.index(w.full_name) for w in workers if w.full_name in content}
    return sorted(positions, key=positions.get)


def test_sap_xep_ten_ma_nv_ngay_vao_lam_ngay_sinh(catalog):
    a = named("Anh An", date_of_birth=D(2000, 1, 1))
    b = named("Bình Bê", date_of_birth=D(1990, 1, 1))
    c = named("Cúc Ca", date_of_birth=D(1995, 1, 1))
    employ(
        a, section=catalog["sec_a"], position=catalog["pos_1"], start=D(2026, 3, 1), code="CN-00003"
    )
    employ(
        b, section=catalog["sec_a"], position=catalog["pos_1"], start=D(2026, 1, 1), code="CN-00001"
    )
    ws = (a, b, c)
    assert order_of(page(query="?sap_xep=ten"), *ws) == [a, b, c]
    assert order_of(page(query="?sap_xep=-ten"), *ws) == [c, b, a]
    assert order_of(page(query="?sap_xep=ma-nv"), *ws) == [b, a, c]  # chưa có mã NV xuống cuối
    assert order_of(page(query="?sap_xep=-ma-nv"), *ws) == [a, b, c]
    assert order_of(page(query="?sap_xep=ngay-sinh"), *ws) == [b, c, a]
    assert order_of(page(query="?sap_xep=ngay-vao-lam"), *ws) == [b, a, c]
    assert order_of(page(query="?sap_xep=-ngay-vao-lam"), *ws) == [a, b, c]


def test_mac_dinh_ho_so_moi_tao_dung_truoc():
    old, new = named("Cũ Hơn"), named("Mới Hơn")
    assert order_of(page(), old, new) == [new, old]


def test_gia_tri_sap_xep_la_khong_gay_loi():
    named("Vẫn Chạy")
    assert "Vẫn Chạy" in page(query="?sap_xep=DROP+TABLE")


# ===== Phân trang và giữ bộ lọc ==========================================================
def test_phan_trang_20_dong():
    for i in range(45):
        named(f"Người Số {i:02d}")
    first = page(query="?sap_xep=ten")
    assert "Hiển thị 1–20 / 45" in first and first.count("Người Số") == 20
    last = page(query="?sap_xep=ten&trang=3")
    assert "Hiển thị 41–45 / 45" in last and last.count("Người Số") == 5
    assert "Người Số 44" in last and "Người Số 00" not in last
    assert "trang=3" in first  # liên kết phân trang giữ tham số sắp xếp
    assert "sap_xep=ten&amp;trang=2" in first
    assert "Người Số" in page(query="?trang=999")  # trang quá lớn -> trang cuối, không lỗi
    assert "Người Số" in page(query="?trang=abc")


def test_giu_bo_loc_khi_quay_lai_trang_va_xoa_loc():
    a = named("Giữ Lọc Nháp")
    verified = make_worker_in_status(VS.VERIFIED)
    Worker.objects.filter(pk=verified.pk).update(full_name="Giữ Lọc Đã Xác Minh")
    verified.refresh_from_db()
    client = login_client(make_user("HR_STAFF"))
    client.get("/ho-so/?trang_thai_ho_so=VERIFIED")
    back = client.get("/ho-so/").content.decode()  # quay lại bằng menu, không tham số
    assert shown(back, a, verified) == [verified]
    assert re.search(r'value="VERIFIED"\s+selected', back)  # ô lọc hiện lại giá trị đã chọn
    assert client.get("/ho-so/?reset=1").status_code == 302
    cleared = client.get("/ho-so/").content.decode()
    assert set(shown(cleared, a, verified)) == {a, verified}
    assert "worker_list_query" not in client.session


def test_chi_tim_nhanh_khong_xoa_bo_loc_da_luu():
    named("Giữ Bộ Lọc Nháp")
    client = login_client(make_user("HR_STAFF"))
    client.get("/ho-so/?trang_thai_ho_so=DRAFT")
    client.get("/ho-so/?q=Giu+Bo+Loc")  # chỉ có chữ tìm kiếm
    assert "trang_thai_ho_so=DRAFT" in client.session["worker_list_query"]
    back = client.get("/ho-so/").content.decode()
    assert re.search(r'value="DRAFT"\s+selected', back)  # bộ lọc trước đó vẫn còn


@pytest.mark.parametrize("query", ["-", "--", "...", " / ", "()"])
def test_tim_chi_co_dau_cau_khong_khop_moi_ho_so(query):
    named("Có Người Trong Bảng")
    content = page(query=f"?q={query}")
    assert "Không có hồ sơ phù hợp." in content and "Có Người Trong Bảng" not in content


def test_chu_tim_kiem_khong_luu_vao_phien():
    named("Ai Đó")
    client = login_client(make_user("HR_STAFF"))
    client.get("/ho-so/?q=999314159265&trang_thai_ho_so=DRAFT")
    saved = client.session["worker_list_query"]
    assert "999314159265" not in saved and "q=" not in saved and "DRAFT" in saved


def test_tim_nhanh_o_thanh_tren_ghi_de_bo_loc_da_luu():
    a = named("Tìm Nhanh Một")
    client = login_client(make_user("HR_STAFF"))
    client.get("/ho-so/?trang_thai_ho_so=VERIFIED")  # bộ lọc đã lưu sẽ loại hồ sơ Nháp
    content = client.get("/ho-so/?q=Tim+Nhanh+Mot").content.decode()
    assert shown(content, a) == [a]  # có tham số trên URL thì không áp bộ lọc đã lưu


# ===== Quyền thao tác trên dòng ==================================================================
def test_nut_them_hoso_va_sua_chi_co_voi_nhan_vien():
    worker = named("Có Nút Sửa")
    staff, viewer = page("HR_STAFF"), page("VIEWER")
    assert "Thêm hồ sơ" in staff and f"/ho-so/{worker.pk}/sua/" in staff
    assert "Thêm hồ sơ" not in viewer and "/sua/" not in viewer
    assert f"/ho-so/{worker.pk}/" in viewer  # vẫn có nút xem


def test_nut_sua_bi_an_khi_ho_so_cho_duyet_hoac_luu_tru():
    pending = make_worker_in_status(VS.PENDING)
    archived = make_worker_in_status(VS.ARCHIVED)
    draft = make_worker_in_status(VS.DRAFT)
    content = page("ADMIN")
    assert f"/ho-so/{draft.pk}/sua/" in content
    assert f"/ho-so/{pending.pk}/sua/" not in content
    assert f"/ho-so/{archived.pk}/sua/" not in content


def test_danh_sach_khong_phat_sinh_truy_van_theo_tung_dong(catalog, django_assert_max_num_queries):
    for i in range(25):
        w = named(f"Nhiều Dòng {i:02d}")
        employ(w, section=catalog["sec_a"], position=catalog["pos_1"])
    client = login_client(make_user("HR_STAFF"))
    with django_assert_max_num_queries(15):
        assert client.get("/ho-so/").status_code == 200
