"""Trang Cài đặt, tab OCR và QR (Phase 5 bước 4; câu 20, mục V.4)."""

import random

import pytest

from apps.audit.models import AuditLog
from apps.core.models import QrFormat, SystemSetting
from apps.intake import fake_cards
from apps.intake.external_ocr import log_external_send
from apps.intake.models import IntakeSession
from apps.intake.qr import choose_format, parse_qr
from tests.factories import login_client, make_user

pytestmark = pytest.mark.django_db

URL = "/cai-dat/ocr-qr/"
DEFAULT_ORDER = [
    "id_number",
    "old_id_number",
    "full_name",
    "date_of_birth",
    "gender",
    "permanent_address",
    "issue_date",
]


def post_data(order=None, **overrides):
    data = {"ocr_confidence_threshold": "80"}
    for doc_type in ("CAN_CUOC_2024", "CCCD_2021"):
        data[f"{doc_type}__is_active"] = "on"
        data[f"{doc_type}__separator"] = "|"
        data[f"{doc_type}__date_format"] = "ddmmyyyy"
        for i in range(1, 15):
            data[f"{doc_type}__pos{i}"] = ""
        for i, name in enumerate(order or DEFAULT_ORDER, start=1):
            data[f"{doc_type}__pos{i}"] = name
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


def admin():
    return login_client(make_user("ADMIN"))


def updates():
    return AuditLog.objects.filter(action="UPDATE").count()


# ----- phân quyền -----


@pytest.mark.parametrize("role", ["HR_MANAGER", "HR_STAFF", "VIEWER"])
def test_vai_tro_khac_admin_bi_403(role):
    client = login_client(make_user(role))
    for url in ("/cai-dat/", URL):
        assert client.get(url).status_code == 403
    assert client.post(URL, post_data()).status_code == 403


def test_chua_dang_nhap_chuyen_toi_dang_nhap():
    from django.test import Client

    response = Client().get(URL)
    assert response.status_code == 302 and response["Location"].startswith("/dang-nhap/")
    assert Client().post(URL, post_data()).status_code == 302


def test_admin_vao_duoc_tab_ocr_qr():
    # Phase 6 đổi tab đầu của /cai-dat/ về Danh mục (trang.md 5.2, phác thảo 2.12); test
    # chuyển hướng nằm ở tests/test_settings_phase6.py. Ở đây chỉ kiểm tab OCR và QR.
    client = admin()
    assert client.get("/cai-dat/").status_code == 302
    response = client.get(URL)
    assert response.status_code == 200
    html = response.content.decode()
    assert "Cấu hình QR – CCCD gắn chip (mẫu 2021)" in html
    assert "Cấu hình QR – Thẻ Căn cước (từ 01/7/2024)" in html
    assert "Lưu cài đặt" in html and "style=" not in html


def test_menu_cai_dat_tro_den_trang_hop_le():
    assert 'href="/cai-dat/"' in admin().get("/").content.decode()


# ----- lưu và nhật ký -----


def test_luu_nguong_tin_cay_ghi_nhat_ky():
    client, before = admin(), updates()
    response = client.post(URL, post_data(ocr_confidence_threshold="70"))
    assert response.status_code == 302
    assert SystemSetting.load().ocr_confidence_threshold == 70
    entry = AuditLog.objects.filter(action="UPDATE").latest("id")
    assert updates() == before + 1
    assert entry.object_type == "core.SystemSetting"
    assert entry.changes == {"ocr_confidence_threshold": ["80", "70"]}
    assert entry.actor_label and entry.note


def test_khong_doi_gi_thi_khong_ghi_nhat_ky():
    client, before = admin(), updates()
    assert client.post(URL, post_data()).status_code == 302
    assert updates() == before


def test_luu_cau_hinh_qr_ghi_nhat_ky_tung_mau_the():
    client = admin()
    data = post_data(CCCD_2021__separator=";", CCCD_2021__date_format="dd/mm/yyyy")
    client.post(URL, data)
    qr = QrFormat.objects.get(id_doc_type="CCCD_2021")
    assert qr.separator == ";" and qr.date_format == "dd/mm/yyyy"
    assert QrFormat.objects.get(id_doc_type="CAN_CUOC_2024").separator == "|"
    entry = AuditLog.objects.filter(action="UPDATE", object_type="core.QrFormat").get()
    assert entry.object_repr == "CCCD_2021"
    assert entry.changes == {"separator": ["|", ";"], "date_format": ["ddmmyyyy", "dd/mm/yyyy"]}


# ----- kiểm tra dữ liệu, sai thì không lưu và không ghi nhật ký -----


@pytest.mark.parametrize(
    "overrides",
    [
        {"ocr_confidence_threshold": "0"},
        {"ocr_confidence_threshold": "101"},
        {"ocr_confidence_threshold": "abc"},
        {"ocr_confidence_threshold": ""},
        {"CCCD_2021__separator": ""},
        {"CCCD_2021__separator": "||||||"},
        {"CCCD_2021__date_format": "mm-dd-yyyy"},
        {"CCCD_2021__pos3": "khong_co_truong_nay"},
    ],
)
def test_gia_tri_sai_khong_luu(overrides):
    client, before = admin(), updates()
    response = client.post(URL, post_data(**overrides))
    assert response.status_code == 200
    assert "Cài đặt chưa được lưu" in response.content.decode()
    assert updates() == before
    assert SystemSetting.load().ocr_confidence_threshold == 80
    assert QrFormat.objects.get(id_doc_type="CCCD_2021").separator == "|"


def test_thu_tu_phai_co_dung_mot_so_cccd():
    client, before = admin(), updates()
    order = [n for n in DEFAULT_ORDER if n != "id_number"]
    html = client.post(URL, post_data(order=order)).content.decode()
    assert "Phải có đúng một vị trí là Số CCCD." in html
    assert updates() == before


def test_truong_khong_duoc_lap_nhung_bo_qua_duoc_lap():
    client, before = admin(), updates()
    html = client.post(
        URL, post_data(order=["id_number", "full_name", "full_name"])
    ).content.decode()
    assert "đang xuất hiện nhiều lần" in html
    assert updates() == before
    ok = client.post(URL, post_data(order=["id_number", "skip", "skip", "full_name"]))
    assert ok.status_code == 302
    assert QrFormat.objects.get(id_doc_type="CCCD_2021").field_order == [
        "id_number",
        "skip",
        "skip",
        "full_name",
    ]


def test_vi_tri_phai_lien_nhau():
    client = admin()
    data = post_data(CCCD_2021__pos2="")  # để trống vị trí 2 nhưng vị trí 3 còn giá trị
    html = client.post(URL, data).content.decode()
    assert "Vị trí 2 để trống nhưng vị trí sau có giá trị" in html


# ----- câu 20: đổi cấu hình thì bộ tách dùng cấu hình mới, không sửa code -----


def test_doi_cau_hinh_qua_trang_thi_bo_tach_dung_cau_hinh_moi():
    client = admin()
    old_payload = "999000000001|999123456|NGUYỄN VĂN MẪU|05011995|Nam|Số 1 Đường Mẫu|20012021"
    assert choose_format(old_payload, "CCCD_2021")[1].ok

    new_order = ["full_name", "id_number", "date_of_birth", "gender"]
    data = post_data(CCCD_2021__separator=";", CCCD_2021__date_format="dd/mm/yyyy")
    for i in range(1, 15):  # chỉ đổi thứ tự của mẫu 2021, mẫu 2024 giữ nguyên
        data[f"CCCD_2021__pos{i}"] = new_order[i - 1] if i <= len(new_order) else ""
    assert client.post(URL, data).status_code == 302

    qr_format = QrFormat.objects.get(id_doc_type="CCCD_2021")
    values = fake_cards._make_values(random.Random(3), 21, "CCCD_2021")
    payload, present = fake_cards.build_qr_payload(values, qr_format)
    assert ";" in payload and "|" not in payload
    result = parse_qr(payload, qr_format)
    assert result.ok and set(result.values) == set(present)
    assert result.values["id_number"] == values["id_number"]
    # chuỗi theo cấu hình cũ không còn khớp mẫu 2021
    assert choose_format(old_payload, "CCCD_2021") == (None, None)
    # còn mẫu 2024 chưa đổi thì vẫn tách chuỗi cũ bằng cấu hình cũ của nó
    assert choose_format(old_payload, "CAN_CUOC_2024")[1].ok


# ----- API OCR ngoài -----


def test_mac_dinh_tat_va_khong_co_canh_bao():
    assert SystemSetting.load().external_ocr_enabled is False
    html = admin().get(URL).content.decode()
    assert "ảnh giấy tờ sẽ được gửi ra khỏi máy chủ" not in html


def test_bat_api_ngoai_hien_canh_bao_va_ghi_nhat_ky():
    client = admin()
    data = post_data(external_ocr_enabled="on", external_ocr_url="https://ocr.example.com/api")
    assert client.post(URL, data).status_code == 302
    system = SystemSetting.load()
    assert system.external_ocr_enabled and system.external_ocr_url == "https://ocr.example.com/api"
    entry = AuditLog.objects.filter(action="UPDATE", object_type="core.SystemSetting").latest("id")
    assert entry.changes["external_ocr_enabled"] == ["False", "True"]
    assert "ảnh giấy tờ sẽ được gửi ra khỏi máy chủ" in client.get(URL).content.decode()


def test_bat_api_ngoai_ma_thieu_dia_chi_thi_khong_luu():
    client, before = admin(), updates()
    response = client.post(URL, post_data(external_ocr_enabled="on", external_ocr_url=""))
    assert "Nhập địa chỉ API OCR" in response.content.decode()
    assert not SystemSetting.load().external_ocr_enabled and updates() == before


def test_bat_api_ngoai_dia_chi_khong_hop_le():
    client = admin()
    data = post_data(external_ocr_enabled="on", external_ocr_url="khong-phai-url")
    assert "bắt đầu bằng http" in client.post(URL, data).content.decode()
    assert not SystemSetting.load().external_ocr_enabled


def test_khoa_api_khong_bao_gio_hien_tren_giao_dien(settings):
    settings.EXTERNAL_OCR_API_KEY = "khoa-bi-mat-chi-dung-trong-test"
    client = admin()
    client.post(URL, post_data(external_ocr_enabled="on", external_ocr_url="https://o.example.com"))
    html = client.get(URL).content.decode()
    assert "khoa-bi-mat-chi-dung-trong-test" not in html
    assert "đã khai báo trong tệp .env" in html
    settings.EXTERNAL_OCR_API_KEY = ""
    assert "chưa khai báo trong tệp .env" in client.get(URL).content.decode()
    assert not hasattr(SystemSetting, "external_ocr_api_key")


def test_ghi_nhat_ky_gui_anh_ra_ngoai():
    user = make_user("HR_STAFF")
    session = IntakeSession.objects.create(created_by=user, expires_at="2099-01-01T00:00:00Z")
    entry = log_external_send(user, session)
    assert entry.action == "EXTERNAL_OCR_SEND" and entry.user == user
    assert entry.object_type == "intake.IntakeSession"
    assert "Họ" not in entry.note and entry.object_repr.startswith("Phiên nhận diện")
