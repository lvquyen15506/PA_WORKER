"""Phase 3: khung giao diện, nhãn trạng thái, /ui-kit/ (chỉ Admin), quy tắc pa-ui trong template."""

import re
from pathlib import Path

import pytest
from django.template import Context, Template
from django.test import Client

from apps.core import badges
from apps.core.choices import (
    DocumentVerificationStatus,
    RecruitmentStatus,
    VerificationStatus,
    WorkStatus,
)
from apps.core.context_processors import build_menu
from tests.factories import PASSWORD, make_user

BASE = Path(__file__).resolve().parent.parent
FOUR_SETS = (VerificationStatus, WorkStatus, RecruitmentStatus, DocumentVerificationStatus)


def login(user):
    client = Client()
    assert (
        client.post("/dang-nhap/", {"username": user.username, "password": PASSWORD}).status_code
        == 302
    )
    return client


def render(source, **context):
    return Template("{% load pa_tags %}" + source).render(Context(context))


# --- /ui-kit/: chỉ Admin ---------------------------------------------------------------------
@pytest.mark.django_db
def test_ui_kit_chua_dang_nhap_chuyen_ve_dang_nhap():
    resp = Client().get("/ui-kit/")
    assert resp.status_code == 302 and resp["Location"].startswith("/dang-nhap/")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role,status", [("ADMIN", 200), ("HR_MANAGER", 403), ("HR_STAFF", 403), ("VIEWER", 403)]
)
def test_ui_kit_theo_vai_tro(role, status):
    assert login(make_user(role)).get("/ui-kit/").status_code == status


@pytest.mark.django_db
def test_ui_kit_hien_moi_component_va_moi_trang_thai():
    body = login(make_user("ADMIN")).get("/ui-kit/").content.decode()
    for choices in FOUR_SETS:
        for choice in choices:
            assert f">{choice.label}</span>" in body, choice
    for label, _color in badges.DERIVED_BADGES.values():
        assert f">{label}</span>" in body, label
    for marker in (
        "pa-page-header",
        "pa-stat",
        "pa-filter",
        "pa-table",
        "pa-pagination",
        "pa-form-section",
        "pa-badge",
        "modal-dialog",
        "pa-empty",
        "alert-success",
        "pa-tabs",
        "pa-source",
        "pa-field--low",
        "data-pa-chart",
        "data-pa-match",  # hộp xác nhận có trường form (block body)
        "dropdown-toggle",  # nút "Thêm"
    ):
        assert marker in body, marker
    assert "Không có hồ sơ phù hợp" in body  # bảng rỗng
    assert "is-invalid" in body  # form có lỗi mẫu
    assert "disabled" in body


# --- Khung chung và menu theo vai trò ----------------------------------------------------------
@pytest.mark.parametrize(
    "role,expected",
    [
        ("ADMIN", 9),
        ("HR_MANAGER", 7),
        ("HR_STAFF", 5),
        ("VIEWER", 4),
    ],
)
def test_menu_sidebar_theo_vai_tro(role, expected):
    assert len(build_menu(role, "/")) == expected


def test_menu_khong_lo_muc_cua_vai_tro_khac():
    labels = {i["label"] for i in build_menu("VIEWER", "/")}
    assert not labels & {"Thêm hồ sơ", "Duyệt hồ sơ", "Nhật ký thao tác", "Tài khoản", "Cài đặt"}
    hr = {i["label"] for i in build_menu("HR_STAFF", "/")}
    assert "Thêm hồ sơ" in hr and "Duyệt hồ sơ" not in hr


def test_menu_muc_dang_chon_la_khop_dai_nhat():
    active = [i["label"] for i in build_menu("ADMIN", "/ho-so/them/") if i["active"]]
    assert active == ["Thêm hồ sơ"]
    assert [i["label"] for i in build_menu("ADMIN", "/") if i["active"]] == ["Tổng quan"]
    assert [i["label"] for i in build_menu("ADMIN", "/ui-kit/") if i["active"]] == []


@pytest.mark.django_db
def test_khung_trang_co_sidebar_thanh_tren_chan_trang():
    body = login(make_user("HR_STAFF")).get("/").content.decode()
    assert "pa-sidebar" in body and "pa-topbar" in body
    # Phase 8: phiên bản lấy từ settings.APP_VERSION (bàn giao v1.1.0), không viết cứng "1.0".
    assert "PA Worker v1.1.0 · Phát triển bởi QQIT" in body
    assert "Đổi mật khẩu" in body and "Đăng xuất" in body
    assert "pa-page-header" in body
    assert "Nhật ký thao tác" not in body  # H không có mục này


@pytest.mark.django_db
def test_trang_dang_nhap_khung_toi_gian():
    body = Client().get("/dang-nhap/").content.decode()
    assert "pa-sidebar" not in body and "pa-topbar" not in body
    assert "PA Worker" in body and "Phát triển bởi QQIT" in body


@pytest.mark.django_db
def test_403_dung_khung_chung():
    resp = login(make_user("VIEWER")).get("/tai-khoan/")
    body = resp.content.decode()
    assert resp.status_code == 403
    assert "pa-sidebar" in body and "Bạn không có quyền thực hiện thao tác này." in body


@pytest.mark.django_db
def test_trang_tai_khoan_dung_component_chuan():
    body = login(make_user("ADMIN")).get("/tai-khoan/").content.decode()
    for marker in ("pa-tabs", "pa-table", "pa-badge", "pa-pagination", "data-pa-confirm"):
        assert marker in body, marker


# --- status_badge ------------------------------------------------------------------------------
@pytest.mark.parametrize("choices", FOUR_SETS)
def test_moi_gia_tri_bon_bo_trang_thai_co_nhan_va_mau(choices):
    for choice in choices:
        label, color = badges.lookup(choice.value)
        assert label == choice.label
        assert color in {"success", "blue", "warning", "danger", "muted"}
        assert badges.lookup(choice) == (label, color)  # nhận cả mã lẫn thành viên enum


def test_ma_trang_thai_cua_bon_bo_khong_trung_nhau():
    values = [c.value for s in FOUR_SETS for c in s]
    assert len(values) == len(set(values))


@pytest.mark.parametrize(
    "value,color",
    [
        (VerificationStatus.VERIFIED, "success"),
        (DocumentVerificationStatus.MATCHED, "success"),
        (RecruitmentStatus.PASSED, "success"),
        (WorkStatus.ACTIVE, "success"),
        (VerificationStatus.PENDING, "blue"),
        (RecruitmentStatus.NEW, "blue"),
        (RecruitmentStatus.SCREENING, "blue"),
        (RecruitmentStatus.INTERVIEW, "blue"),
        (WorkStatus.PROBATION, "blue"),
        (WorkStatus.AWAITING, "blue"),
        (VerificationStatus.NEEDS_INFO, "warning"),
        (WorkStatus.SUSPENDED, "warning"),
        (badges.MISSING_DOCS, "warning"),
        (badges.EXPIRING, "warning"),
        (VerificationStatus.REJECTED, "danger"),
        (RecruitmentStatus.FAILED, "danger"),
        (DocumentVerificationStatus.INVALID, "danger"),
        (VerificationStatus.DRAFT, "muted"),
        (VerificationStatus.ARCHIVED, "muted"),
        (WorkStatus.RESIGNED, "muted"),
        (RecruitmentStatus.DECLINED, "muted"),
        (DocumentVerificationStatus.UNVERIFIED, "muted"),
        (badges.COMPLETE, "success"),
        (badges.ACCOUNT_ACTIVE, "success"),
        (badges.ACCOUNT_LOCKED, "danger"),
        (badges.ACCOUNT_TEMP_LOCKED, "warning"),
        (badges.CATALOG_ACTIVE, "success"),
        (badges.CATALOG_STOPPED, "muted"),
        (badges.LOGIN_OK, "success"),
        (badges.LOGIN_FAILED, "danger"),
    ],
)
def test_bang_mau_theo_pa_ui_muc_5(value, color):
    assert badges.lookup(value)[1] == color
    assert f"pa-badge--{color}" in render("{{ v|status_badge }}", v=value)


def test_status_badge_chu_thay_the_va_ma_la():
    out = render('{{ v|status_badge:"Khóa tạm đến 14:05" }}', v=badges.ACCOUNT_TEMP_LOCKED)
    assert "Khóa tạm đến 14:05" in out and "pa-badge--warning" in out
    # mã lạ không làm vỡ trang, hiện xám, và được escape
    out = render("{{ v|status_badge }}", v="<script>x</script>")
    assert "<script>" not in out and "pa-badge--muted" in out
    assert "—" in render("{{ v|status_badge }}", v=None)


# --- Component ---------------------------------------------------------------------------------
def test_stat_card_so_lieu_tuy_chon():
    with_value = render(
        '{% include "components/_stat_card.html" with label="Chờ duyệt" value=7 sub="x" '
        'url="/a/" %}'
    )
    assert "pa-stat__value" in with_value and ">7<" in with_value
    without = render('{% include "components/_stat_card.html" with label="Nhập tay" url="/a/" %}')
    assert "pa-stat__value" not in without and "pa-stat--plain" in without
    zero = render('{% include "components/_stat_card.html" with label="Thiếu" value=0 url="/a/" %}')
    assert ">0<" in zero  # số 0 vẫn hiện


def test_confirm_modal_gui_form_post_co_csrf():
    out = render(
        '{% include "components/_confirm_modal.html" with id="m" title="T" message="M" '
        'action="/x/" confirm_label="Lưu trữ hồ sơ" danger=True %}'
    )
    assert 'method="post"' in out and 'action="/x/"' in out and "btn-danger" in out
    assert "Lưu trữ hồ sơ" in out


def test_table_o_trong_hien_gach_ngang_va_rong_hien_empty_state():
    cols = [{"key": "a", "label": "A", "kind": "text"}, {"key": "d", "label": "D", "kind": "date"}]
    out = render(
        '{% include "components/_table.html" with columns=cols rows=rows %}',
        cols=cols,
        rows=[{"a": None, "d": None}],
    )
    assert out.count("—") == 2
    empty = render(
        '{% include "components/_table.html" with columns=cols rows=rows empty_text="Trống." %}',
        cols=cols,
        rows=[],
    )
    assert "pa-empty" in empty and "Trống." in empty


def test_alert_tu_an_sau_5_giay_chi_khi_yeu_cau():
    on = render(
        '{% include "components/_alert.html" with kind="success" text="Xong" auto_hide=True %}'
    )
    off = render('{% include "components/_alert.html" with kind="danger" text="Lỗi" %}')
    assert "data-pa-autohide" in on and "data-pa-autohide" not in off
    assert "alert-danger" in off


# --- Quy tắc pa-ui trong template/CSS/JS --------------------------------------------------------
TEMPLATES = sorted((BASE / "templates").rglob("*.html"))


def test_template_khong_style_inline_khong_hex_khong_base_tam():
    assert TEMPLATES
    for path in TEMPLATES:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\sstyle\s*=", text), f"{path.name}: có style="
        assert "base_tam" not in text, path.name


def test_ma_mau_hex_chi_o_pa_css():
    hex_re = re.compile(r"(?<![\w&])#[0-9a-fA-F]{6}\b|(?<![\w&])#[0-9a-fA-F]{3}\b(?=\s*[;,)}])")
    files = [p for p in (BASE / "static" / "js").glob("*.js")] + TEMPLATES
    for path in files:
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"(href|data-bs-target|action|aria-controls)=\"#[^\"]*\"", "", text)
        assert not hex_re.search(text), f"{path.name} chứa mã màu hex"
    assert hex_re.search((BASE / "static" / "css" / "pa.css").read_text(encoding="utf-8"))


def test_khong_dung_cdn_va_font_ngoai():
    for path in TEMPLATES:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r'(src|href)="https?://', text), path.name
    css = (BASE / "static" / "css" / "pa.css").read_text(encoding="utf-8")
    assert "@import" not in css and "fonts.googleapis" not in css
    assert "system-ui" in css


def test_icon_chi_o_vi_tri_cho_phep():
    """pa-ui mục 6: icon chỉ ở menu sidebar, nút thao tác trong bảng, ô tìm kiếm."""
    allowed = {"base.html", "_table.html"}
    for path in TEMPLATES:
        if path.name in allowed:
            continue
        assert "bi bi-" not in path.read_text(encoding="utf-8"), path.name
