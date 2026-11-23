"""Cài đặt Phase 6 (trang.md mục 5.2): danh mục 10 loại, quy tắc sinh mã, ngưỡng và thời hạn.

Chỉ Admin; không có xóa; ngừng sử dụng thì không hiện khi tạo mới; trùng tên chặn khi so không
phân biệt hoa thường và khoảng trắng thừa; công ty khách chỉ trùng khi bỏ dấu thì cảnh báo, không
chặn (câu 48); đổi quy tắc sinh mã có tác dụng ngay, mã đã cấp giữ nguyên; mọi thay đổi ghi nhật ký.
"""

import pytest
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import Resolver404, resolve

from apps.audit.models import AuditLog
from apps.core.catalogs import CATALOGS, catalog_form_class
from apps.core.choices import CodeType
from apps.core.codes import next_code
from apps.core.models import (
    ClientCompany,
    Department,
    DocumentType,
    EducationLevel,
    Position,
    Section,
    SystemSetting,
)
from apps.core.settings_services import CatalogError, set_catalog_active
from tests.factories import login_client, make_user, make_worker

pytestmark = pytest.mark.django_db

SLUGS = [c.slug for c in CATALOGS]


def admin():
    return login_client(make_user("ADMIN"))


def logs(action):
    return AuditLog.objects.filter(action=action).count()


def warnings_of(response):
    return [str(m) for m in get_messages(response.wsgi_request) if m.level_tag == "warning"]


# ----- Khung tab, phân quyền ------------------------------------------------------------------
def test_du_10_loai_danh_muc_dung_slug_trang_md():
    assert SLUGS == [
        "phong-ban",
        "bo-phan",
        "to",
        "chuc-danh",
        "ca",
        "nguon-ung-tuyen",
        "trinh-do",
        "nhom-tai-lieu",
        "loai-tai-lieu",
        "cong-ty-khach",
    ]


def test_cai_dat_chuyen_toi_tab_danh_muc_va_co_du_4_tab():
    client = admin()
    assert client.get("/cai-dat/")["Location"] == "/cai-dat/danh-muc/"
    assert client.get("/cai-dat/danh-muc/")["Location"] == "/cai-dat/danh-muc/phong-ban/"
    html = client.get("/cai-dat/danh-muc/phong-ban/").content.decode()
    for label in ("Danh mục", "Sinh mã", "Ngưỡng và thời hạn", "OCR và QR"):
        assert label in html
    assert "style=" not in html


@pytest.mark.parametrize("slug", SLUGS)
def test_admin_mo_duoc_moi_danh_muc_va_form_them(slug):
    client = admin()
    assert client.get(f"/cai-dat/danh-muc/{slug}/").status_code == 200
    assert client.get(f"/cai-dat/danh-muc/{slug}/them/").status_code == 200


def test_loai_khong_ton_tai_404():
    assert admin().get("/cai-dat/danh-muc/khong-co/").status_code == 404


@pytest.mark.parametrize("role", ["HR_MANAGER", "HR_STAFF", "VIEWER"])
def test_vai_tro_khac_admin_bi_403_o_moi_url(role):
    dep = Department.objects.create(name="PB quyền")
    client = login_client(make_user(role))
    for url in (
        "/cai-dat/danh-muc/",
        "/cai-dat/danh-muc/phong-ban/",
        "/cai-dat/danh-muc/phong-ban/them/",
        f"/cai-dat/danh-muc/phong-ban/{dep.pk}/sua/",
        "/cai-dat/sinh-ma/",
        "/cai-dat/nguong/",
    ):
        assert client.get(url).status_code == 403, url
    for url in (
        "/cai-dat/danh-muc/phong-ban/them/",
        f"/cai-dat/danh-muc/phong-ban/{dep.pk}/ngung/",
        "/cai-dat/sinh-ma/",
        "/cai-dat/nguong/",
    ):
        assert client.post(url, {"name": "X"}).status_code == 403, url
    assert Department.objects.get(pk=dep.pk).is_active


def test_chua_dang_nhap_chuyen_toi_dang_nhap():
    response = Client().get("/cai-dat/danh-muc/phong-ban/")
    assert response.status_code == 302 and response["Location"].startswith("/dang-nhap/")


def test_khong_co_url_hay_nut_xoa():
    dep = Department.objects.create(name="PB xóa")
    with pytest.raises(Resolver404):
        resolve(f"/cai-dat/danh-muc/phong-ban/{dep.pk}/xoa/")
    html = admin().get("/cai-dat/danh-muc/phong-ban/").content.decode()
    assert "Xóa" not in html.replace("Xóa lọc", "")


def test_ngung_bang_get_khong_duoc():
    dep = Department.objects.create(name="PB get")
    assert admin().get(f"/cai-dat/danh-muc/phong-ban/{dep.pk}/ngung/").status_code == 405


# ----- Thêm, sửa, ngừng, dùng lại -------------------------------------------------------------
def test_them_sua_ngung_dung_lai_phong_ban_va_ghi_nhat_ky():
    client = admin()
    created, updated = logs("CREATE"), logs("UPDATE")
    response = client.post(
        "/cai-dat/danh-muc/phong-ban/them/", {"name": "  Xưởng   Hàn ", "sort_order": "3"}
    )
    assert response.status_code == 302
    dep = Department.objects.get(name="Xưởng Hàn")  # khoảng trắng thừa được gộp
    assert logs("CREATE") == created + 1
    client.post(
        f"/cai-dat/danh-muc/phong-ban/{dep.pk}/sua/", {"name": "Xưởng Hàn 2", "sort_order": "3"}
    )
    entry = AuditLog.objects.filter(action="UPDATE", object_type="core.Department").first()
    assert entry.changes == {"name": ["Xưởng Hàn", "Xưởng Hàn 2"]}
    client.post(f"/cai-dat/danh-muc/phong-ban/{dep.pk}/ngung/")
    assert not Department.objects.get(pk=dep.pk).is_active
    client.post(f"/cai-dat/danh-muc/phong-ban/{dep.pk}/dung-lai/")
    assert Department.objects.get(pk=dep.pk).is_active
    assert logs("UPDATE") == updated + 3


def test_sua_khong_doi_gi_thi_khong_ghi_nhat_ky():
    dep = Department.objects.create(name="PB y nguyên", sort_order=1)
    before = logs("UPDATE")
    admin().post(
        f"/cai-dat/danh-muc/phong-ban/{dep.pk}/sua/", {"name": "PB y nguyên", "sort_order": "1"}
    )
    assert logs("UPDATE") == before


def test_trung_ten_khac_hoa_thuong_bi_chan():
    Position.objects.create(name="Công nhân may")
    response = admin().post("/cai-dat/danh-muc/chuc-danh/them/", {"name": "công  NHÂN may"})
    assert response.status_code == 200
    assert "Đã có chức danh này trong danh mục." in response.content.decode()
    assert Position.objects.count() == 1


def test_bo_phan_cung_ten_khac_phong_ban_duoc_trung_phong_ban_bi_chan():
    a = Department.objects.create(name="PB A")
    b = Department.objects.create(name="PB B")
    Section.objects.create(department=a, name="Chuyền 1")
    client = admin()
    ok = client.post(
        "/cai-dat/danh-muc/bo-phan/them/", {"department": b.pk, "name": "Chuyền 1", "sort_order": 0}
    )
    assert ok.status_code == 302
    bad = client.post(
        "/cai-dat/danh-muc/bo-phan/them/", {"department": a.pk, "name": "chuyền 1", "sort_order": 0}
    )
    assert bad.status_code == 200 and "Đã có bộ phận này" in bad.content.decode()


def test_cap_bac_trinh_do_trung_bi_chan_bang_loi_tieng_viet():
    response = admin().post("/cai-dat/danh-muc/trinh-do/them/", {"name": "Thạc sĩ", "rank": "8"})
    assert response.status_code == 200
    assert not EducationLevel.objects.filter(name="Thạc sĩ").exists()


def test_muc_ngung_khong_hien_khi_tao_moi_nhung_van_hien_o_du_lieu_cu():
    active = Department.objects.create(name="PB đang dùng")
    stopped = Department.objects.create(name="PB đã ngừng", is_active=False)
    catalog = next(c for c in CATALOGS if c.slug == "bo-phan")
    form = catalog_form_class(catalog)()
    choices = list(form.fields["department"].queryset)
    assert active in choices and stopped not in choices
    old = Section.objects.create(department=stopped, name="BP cũ")
    edit = catalog_form_class(catalog)(instance=old)
    assert stopped in list(edit.fields["department"].queryset)


def test_loai_tai_lieu_he_thong_khong_ngung_duoc():
    contract = DocumentType.objects.get(system_code="CONTRACT")
    with pytest.raises(CatalogError):
        set_catalog_active(make_user("ADMIN"), contract, False)
    response = admin().post(f"/cai-dat/danh-muc/loai-tai-lieu/{contract.pk}/ngung/", follow=True)
    assert "không ngừng sử dụng được" in response.content.decode()
    assert DocumentType.objects.get(pk=contract.pk).is_active
    commitment = DocumentType.objects.get(name="Bản cam kết")
    set_catalog_active(make_user("ADMIN"), commitment, False)  # loại thường thì ngừng được


def test_service_danh_muc_chan_nguoi_khong_phai_admin():
    from django.core.exceptions import PermissionDenied

    dep = Department.objects.create(name="PB service")
    with pytest.raises(PermissionDenied):
        set_catalog_active(make_user("HR_MANAGER"), dep, False)


# ----- Công ty khách (câu 39, 48) -------------------------------------------------------------
URL_CLIENT = "/cai-dat/danh-muc/cong-ty-khach/them/"


def test_cong_ty_khach_cung_ten_dia_diem_khac_luu_duoc():
    ClientCompany.objects.create(name="Công ty An", location="Bình Dương")
    response = admin().post(URL_CLIENT, {"name": "Công ty An", "location": "Đồng Nai"})
    assert response.status_code == 302
    assert ClientCompany.objects.filter(name="Công ty An").count() == 2


def test_cong_ty_khach_trung_ten_va_dia_diem_khac_hoa_thuong_bi_chan():
    ClientCompany.objects.create(name="Công ty An", location="Bình Dương")
    response = admin().post(URL_CLIENT, {"name": "công ty  an", "location": " bình dương "})
    assert response.status_code == 200
    assert "Đã có công ty khách này ở địa điểm này" in response.content.decode()
    assert ClientCompany.objects.count() == 1


def test_cong_ty_khach_chi_trung_khi_bo_dau_thi_canh_bao_khong_chan():
    ClientCompany.objects.create(name="Công ty An", location="Bình Dương")
    response = admin().post(URL_CLIENT, {"name": "Cong ty An", "location": "Đồng Nai"})
    assert response.status_code == 302
    assert ClientCompany.objects.filter(name="Cong ty An").exists()
    assert warnings_of(response) == ["Có thể trùng với: Công ty An – Bình Dương"]


def test_cong_ty_khach_khong_canh_bao_khi_trung_giu_dau_hoac_sua_chinh_minh():
    own = ClientCompany.objects.create(name="Công ty An", location="Bình Dương")
    client = admin()
    other_site = client.post(URL_CLIENT, {"name": "Công ty An", "location": "Hà Nội"})
    assert warnings_of(other_site) == []  # cùng tên giữ dấu: cùng công ty, địa điểm khác
    edit = client.post(
        f"/cai-dat/danh-muc/cong-ty-khach/{own.pk}/sua/",
        {"name": "Công ty An", "location": "Bình Dương 2"},
    )
    assert edit.status_code == 302 and warnings_of(edit) == []


def test_trang_danh_sach_hien_canh_bao_sau_khi_luu():
    ClientCompany.objects.create(name="Công ty An", location="Bình Dương")
    response = admin().post(URL_CLIENT, {"name": "Cong ty An", "location": "Đồng Nai"}, follow=True)
    assert "Có thể trùng với: Công ty An – Bình Dương" in response.content.decode()


# ----- Sinh mã --------------------------------------------------------------------------------
def code_post(**overrides):
    data = {
        "worker_code_prefix": "HS",
        "worker_code_use_year": "on",
        "worker_code_digits": "5",
        "employee_code_prefix": "CN",
        "employee_code_digits": "5",
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


def test_doi_quy_tac_ma_nv_co_tac_dung_ngay_ma_da_cap_giu_nguyen():
    worker = make_worker()
    old = next_code(CodeType.EMPLOYEE)
    type(worker).objects.filter(pk=worker.pk).update(employee_code=old)
    client = admin()
    before = logs("UPDATE")
    response = client.post(
        "/cai-dat/sinh-ma/", code_post(employee_code_prefix="NV", employee_code_digits="4")
    )
    assert response.status_code == 302 and logs("UPDATE") == before + 1
    # Tiền tố mới dùng ngay. Bộ đếm (theo loại mã + năm) chỉ tăng, không quay về 1 khi đổi
    # tiền tố (models.md 3.3: CodeSequence chỉ tăng), nên số tiếp theo là 2.
    assert next_code(CodeType.EMPLOYEE) == "NV-0002"
    worker.refresh_from_db()
    assert worker.employee_code == old  # mã đã cấp giữ nguyên


def test_trang_sinh_ma_xem_truoc_ma_ke_tiep_khong_tang_bo_dem():
    client = admin()
    html = client.get("/cai-dat/sinh-ma/").content.decode()
    assert "CN-00001" in html
    html = client.get("/cai-dat/sinh-ma/").content.decode()
    assert "CN-00001" in html  # xem lại vẫn là mã đó: xem trước không cấp mã
    assert next_code(CodeType.EMPLOYEE) == "CN-00001"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"employee_code_prefix": "C-N"}, "Tiền tố chỉ gồm chữ cái không dấu và chữ số"),
        ({"employee_code_prefix": ""}, "Tiền tố chỉ gồm chữ cái không dấu và chữ số"),
        ({"employee_code_digits": "9"}, "Nhập số nguyên từ 3 đến 8."),
        (
            {"worker_code_prefix": "ABCDEFGHIJ", "worker_code_digits": "8"},
            "vượt giới hạn 20",
        ),
    ],
)
def test_quy_tac_sinh_ma_sai_bi_tu_choi(overrides, message):
    before = SystemSetting.load().employee_code_prefix
    response = admin().post("/cai-dat/sinh-ma/", code_post(**overrides))
    assert response.status_code == 200 and message in response.content.decode()
    assert SystemSetting.load().employee_code_prefix == before


# ----- Ngưỡng và thời hạn ---------------------------------------------------------------------
def threshold_post(**overrides):
    data = {
        "expiry_warning_days": "30",
        "assignment_limit_months": "12",
        "failed_retention_months": "12",
        "resigned_retention_years": "10",
        "auto_archive_resigned_days": "30",
        "auto_archive_failed_days": "30",
        "stale_draft_months": "6",
        "intake_ttl_hours": "24",
    }
    data.update(overrides)
    return data


def test_luu_nguong_co_tac_dung_ngay_va_ghi_nhat_ky():
    before = logs("UPDATE")
    response = admin().post(
        "/cai-dat/nguong/", threshold_post(expiry_warning_days="45", assignment_limit_months="11")
    )
    assert response.status_code == 302
    system = SystemSetting.load()
    assert (system.expiry_warning_days, system.assignment_limit_months) == (45, 11)
    assert logs("UPDATE") == before + 1
    entry = AuditLog.objects.filter(action="UPDATE", object_type="core.SystemSetting").first()
    assert entry.changes["expiry_warning_days"] == ["30", "45"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"expiry_warning_days": "0"},
        {"assignment_limit_months": "61"},
        {"resigned_retention_years": "abc"},
        {"intake_ttl_hours": ""},
    ],
)
def test_nguong_ngoai_khoang_bi_tu_choi(overrides):
    response = admin().post("/cai-dat/nguong/", threshold_post(**overrides))
    assert response.status_code == 200 and "Nhập số nguyên từ" in response.content.decode()
    assert SystemSetting.load().expiry_warning_days == 30
