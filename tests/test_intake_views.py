"""Trang nhập từ CCCD và CV: tải ảnh, phân quyền, tệp phiên, xoay, hủy, ngân sách (Phase 5)."""

import datetime
import functools
import io
import re
import struct
import zlib

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.audit.models import AuditLog
from apps.core.models import SystemSetting
from apps.intake import ocr, services
from apps.intake.budget import Budget
from apps.intake.models import IntakeSession
from apps.intake.ocr import OcrTimeout
from apps.intake.pipeline import WARN_TIMEOUT
from apps.workers.models import Worker
from tests.factories import login_client, make_user
from tests.intake_helpers import card, card_bytes, card_upload, cv_upload, make_session

pytestmark = pytest.mark.django_db

STAFF = ["ADMIN", "HR_MANAGER", "HR_STAFF"]


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def png(width, height):
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def forged_png(width, height):
    data = png(8, 8)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    new = struct.pack(">I", len(ihdr)) + chunk + struct.pack(">I", zlib.crc32(chunk))
    return data[:8] + new + data[8 + 4 + 4 + 13 + 4 :]


def intake_files(settings):
    root = settings.PRIVATE_MEDIA_ROOT / "intake"
    return [p for p in root.rglob("*") if p.is_file()] if root.exists() else []


# ----- phân quyền -----


@pytest.mark.parametrize("role", STAFF)
def test_nhan_vien_vao_duoc_trang_tai_anh(role):
    response = login_client(make_user(role)).get("/nhap-cccd/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "Nhận diện" in html and "Tự nhận biết" in html and "style=" not in html


def test_viewer_bi_403_o_moi_url_nhap_cccd():
    owner = make_user("HR_STAFF")
    session = make_session(owner, "12")
    viewer = login_client(make_user("VIEWER"))
    base = f"/nhap-cccd/{session.pk}/"
    assert viewer.get("/nhap-cccd/").status_code == 403
    assert viewer.post("/nhap-cccd/", {}).status_code == 403
    for url in (base, base + "tep/mat-truoc/"):
        assert viewer.get(url).status_code == 403
    for url in (base, base + "kiem-tra-trung/", base + "huy/", base + "xoay/mat-truoc/"):
        assert viewer.post(url, {}).status_code == 403
    assert IntakeSession.objects.filter(pk=session.pk).exists()


def test_chua_dang_nhap_chuyen_toi_dang_nhap():
    from django.test import Client

    response = Client().get("/nhap-cccd/")
    assert response.status_code == 302 and response["Location"].startswith("/dang-nhap/")


def test_chi_nguoi_tao_va_admin_mo_duoc_phien():
    owner = make_user("HR_STAFF")
    session = make_session(owner, "12")
    base = f"/nhap-cccd/{session.pk}/"
    for role in ("HR_STAFF", "HR_MANAGER"):  # người khác, kể cả Quản lý
        other = login_client(make_user(role))
        assert other.get(base).status_code == 404
        assert other.get(base + "tep/mat-truoc/").status_code == 404
        assert other.get(base + "tep/cv/").status_code == 404
        for url in (base, base + "kiem-tra-trung/", base + "huy/", base + "xoay/mat-truoc/"):
            assert other.post(url, {}).status_code == 404
        assert other.post(base + "mo-ho-so-cu/1/").status_code == 404
    assert login_client(owner.__class__.objects.get(pk=owner.pk)).get(base).status_code == 200
    assert login_client(make_user("ADMIN")).get(base).status_code == 200
    assert login_client(make_user("ADMIN")).get(base + "tep/mat-truoc/").status_code == 200
    assert IntakeSession.objects.filter(pk=session.pk).exists()  # người khác không hủy được


def test_phien_het_han_thi_404():
    owner = make_user("HR_STAFF")
    session = make_session(owner, "12")
    IntakeSession.objects.filter(pk=session.pk).update(
        expires_at=timezone.now() - datetime.timedelta(minutes=1)
    )
    assert login_client(owner).get(f"/nhap-cccd/{session.pk}/").status_code == 404


# ----- tạo phiên -----


def test_tai_anh_tao_phien_khong_ghi_gi_vao_ho_so(settings):
    user = make_user("HR_STAFF")
    client = login_client(user)
    before = AuditLog.objects.count()
    response = client.post(
        "/nhap-cccd/",
        {
            "front_image": card_upload("01", "front"),
            "back_image": card_upload("01", "back"),
            "doc_type": "",
        },
    )
    assert response.status_code == 302
    session = IntakeSession.objects.get()
    assert response["Location"] == f"/nhap-cccd/{session.pk}/"
    assert session.created_by == user and Worker.objects.count() == 0
    from apps.documents.models import WorkerDocument
    from apps.workers.models import IdentityDocument, IdentityFieldSource

    assert not WorkerDocument.objects.exists()
    assert not IdentityDocument.objects.exists() and not IdentityFieldSource.objects.exists()
    entry = AuditLog.objects.get(action="INTAKE_CREATE")
    assert AuditLog.objects.count() == before + 1 and entry.user == user
    assert entry.object_type == "intake.IntakeSession" and "999" not in entry.note
    # hạn phiên theo cấu hình
    hours = SystemSetting.load().intake_ttl_hours
    assert abs((session.expires_at - session.created_at).total_seconds() - hours * 3600) < 5


def test_tep_phien_luu_ten_ngau_nhien_ngoai_thu_muc_public(settings):
    make_session(make_user("HR_STAFF"), "01")
    files = intake_files(settings)
    assert len(files) == 2
    for path in files:
        assert re.fullmatch(r"[0-9a-f]{32}\.png", path.name)  # không còn tên gốc
        assert "cccd" not in path.name and str(settings.STATIC_ROOT) not in str(path)
    assert not any(str(settings.STATIC_ROOT) in str(p) for p in files)


def test_ket_qua_nhan_dien_duoc_ma_hoa_trong_csdl():
    from django.db import connection

    session = make_session(make_user("HR_STAFF"), "01")
    truth = card("01")["values"]
    with connection.cursor() as cur:
        cur.execute("SELECT result_enc FROM intake_intakesession")
        raw = cur.fetchone()[0]
    assert truth["id_number"] not in raw and truth["full_name"] not in raw
    assert session.get_result()["recognition"]["fields"]["id_number"]["value"] == truth["id_number"]


def test_trang_doi_chieu_hien_nguon_va_khong_to_vang_voi_truong_qr():
    user = make_user("HR_STAFF")
    session = make_session(user, "01")
    html = login_client(user).get(f"/nhap-cccd/{session.pk}/").content.decode()
    assert "Đối chiếu thông tin" in html and "Kết quả nhận diện chưa được lưu" in html
    assert 'class="pa-source">QR<' in html and 'class="pa-source">OCR<' in html
    assert "pa-field--low" not in html and "style=" not in html
    assert card("01")["values"]["id_number"] in html
    assert "Xoay ảnh" in html and "Phóng to" in html and "Hủy phiên" in html


def test_nhan_nguon_va_o_tich_chi_o_truong_nhan_dien_khong_tran_sang_khoi_khac():
    """Họ tên người liên hệ và ngày cấp chứng chỉ trùng tên với trường nhận diện, nhưng không
    được nhận nhãn nguồn hay ô Đã kiểm tra."""
    from apps.intake.services import review_initial

    user = make_user("HR_STAFF")
    for card_id in ("01", "15"):
        session = make_session(user, card_id)
        _initial, meta, low = review_initial(session)
        html = login_client(user).get(f"/nhap-cccd/{session.pk}/").content.decode()
        assert html.count('class="pa-source"') == len(meta)
        assert html.count("data-pa-checked") == len(low)
        assert 'name="contacts-0-full_name__checked"' not in html
        assert 'name="cert-0-issue_date__checked"' not in html


def test_the_khong_qr_anh_mo_to_vang_va_khoa_nut_luu():
    user = make_user("HR_STAFF")
    session = make_session(user, "15")
    html = login_client(user).get(f"/nhap-cccd/{session.pk}/").content.decode()
    assert "pa-field--low" in html and "Đã kiểm tra" in html
    assert re.search(r"<button[^>]*data-pa-gate[^>]*disabled", html)
    assert "Ảnh bị mờ" in html


@pytest.mark.parametrize(
    "files, message",
    [
        ({}, "Chọn ít nhất một tệp"),
        ({"front_image": SimpleUploadedFile("a.jpg", b"khong phai anh")}, "Chỉ nhận tệp JPG"),
        ({"front_image": SimpleUploadedFile("a.pdf", b"%PDF-1.4 x")}, "chỉ nhận JPG, PNG"),
        ({"front_image": SimpleUploadedFile("a.png", b"")}, "rỗng"),
        (
            {"front_image": SimpleUploadedFile("a.png", png(10, 10) + b"0" * (10 * 1024 * 1024))},
            "10 MB",
        ),
        ({"cv_file": SimpleUploadedFile("cv.exe", b"MZ")}, "Chỉ nhận tệp"),
    ],
)
def test_tep_khong_hop_le_bi_tu_choi(files, message, settings):
    client = login_client(make_user("HR_STAFF"))
    response = client.post("/nhap-cccd/", files)
    assert response.status_code == 200 and message in response.content.decode()
    assert not IntakeSession.objects.exists() and intake_files(settings) == []


def test_loai_giay_to_sai_bi_tu_choi():
    client = login_client(make_user("HR_STAFF"))
    response = client.post("/nhap-cccd/", {"front_image": card_upload("12"), "doc_type": "KHAC"})
    assert response.status_code == 200 and not IntakeSession.objects.exists()


def test_anh_khai_bao_kich_thuoc_khong_lo_bi_tu_choi_khong_de_lai_tep(settings):
    client = login_client(make_user("HR_STAFF"))
    bad = SimpleUploadedFile("khung.png", forged_png(50_000, 50_000))
    response = client.post("/nhap-cccd/", {"front_image": bad})
    html = response.content.decode()
    assert response.status_code == 200 and "Ảnh quá lớn" in html and "40 triệu" in html
    assert not IntakeSession.objects.exists() and intake_files(settings) == []


def test_cv_chi_mot_tep_hong_bao_loi_va_khong_tao_phien(settings):
    client = login_client(make_user("HR_STAFF"))
    bad = SimpleUploadedFile("cv.pdf", b"%PDF-1.4 hong")
    response = client.post("/nhap-cccd/", {"cv_file": bad})
    assert "CV:" in response.content.decode() and not IntakeSession.objects.exists()
    assert intake_files(settings) == []


def test_cv_hong_nhung_co_anh_thi_van_tao_phien_kem_canh_bao():
    user = make_user("HR_STAFF")
    session = make_session(user, "12", cv=SimpleUploadedFile("cv.pdf", b"%PDF-1.4 hong"))
    cv = session.get_result()["cv"]
    assert cv["text"] == "" and cv["warnings"] and cv["warnings"][0].startswith("CV:")


def test_chi_tai_cv_van_hien_van_ban_va_goi_y():
    user = make_user("HR_STAFF")
    session = make_session(user, cv=cv_upload())
    assert session.get_result()["recognition"] is None
    html = login_client(user).get(f"/nhap-cccd/{session.pk}/").content.decode()
    assert "Văn bản trích từ CV" in html and "Đưa vào trường" in html
    assert "0999000111" in html and "mau.thu@example.com" in html
    assert "Học vấn (từ CV)" in html and "Chứng chỉ (từ CV)" in html


# ----- tệp của phiên -----


def test_tep_phien_xem_truc_tiep_voi_header_an_toan():
    user = make_user("HR_STAFF")
    session = make_session(user, "01", cv=cv_upload("cv-mau.pdf"))
    client = login_client(user)
    response = client.get(f"/nhap-cccd/{session.pk}/tep/mat-truoc/")
    assert response.status_code == 200 and response["Content-Type"] == "image/png"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Security-Policy"] == "sandbox"
    assert response["Content-Disposition"].startswith("inline")
    assert response["Cache-Control"] == "private, no-store"
    assert b"".join(response.streaming_content) == card_bytes("01")
    pdf = client.get(f"/nhap-cccd/{session.pk}/tep/cv/")
    assert pdf["Content-Type"] == "application/pdf"


def test_cv_docx_chi_cho_tai_xuong_va_khe_la_404():
    user = make_user("HR_STAFF")
    session = make_session(user, "01", cv=cv_upload())
    client = login_client(user)
    response = client.get(f"/nhap-cccd/{session.pk}/tep/cv/")
    assert response["Content-Disposition"].startswith("attachment")
    assert client.get(f"/nhap-cccd/{session.pk}/tep/khong-co/").status_code == 404
    only_front = make_session(user, "01", sides=("front",))
    assert client.get(f"/nhap-cccd/{only_front.pk}/tep/mat-sau/").status_code == 404


# ----- hủy phiên, xoay ảnh -----


def test_huy_phien_xoa_tep_va_ghi_nhat_ky(settings):
    user = make_user("HR_STAFF")
    session = make_session(user, "01")
    pk = session.pk
    response = login_client(user).post(f"/nhap-cccd/{pk}/huy/")
    assert response.status_code == 302
    assert not IntakeSession.objects.filter(pk=pk).exists() and intake_files(settings) == []
    entry = AuditLog.objects.get(action="INTAKE_CANCEL")
    assert entry.user == user and Worker.objects.count() == 0


def test_xoay_anh_doi_chieu_dai_va_nhan_dien_lai():
    user = make_user("HR_STAFF")
    session = make_session(user, "12")
    before = Image.open(session.front_image.open("rb"))
    width, height = before.size
    assert login_client(user).post(f"/nhap-cccd/{session.pk}/xoay/mat-truoc/").status_code == 302
    session = IntakeSession.objects.get(pk=session.pk)
    after = Image.open(session.front_image.open("rb"))
    assert after.size == (height, width)
    # ảnh nằm ngang bị xoay thì OCR không còn đọc được: trường để trống và tô vàng
    fields = session.get_result()["recognition"]["fields"]
    assert fields["id_number"]["value"] is None and fields["id_number"]["low"]


def test_xoay_bon_lan_tra_ve_anh_ban_dau_va_doc_lai_duoc():
    user = make_user("HR_STAFF")
    session = make_session(user, "12", sides=("front",))
    client = login_client(user)
    for _ in range(4):
        client.post(f"/nhap-cccd/{session.pk}/xoay/mat-truoc/")
    session = IntakeSession.objects.get(pk=session.pk)
    fields = session.get_result()["recognition"]["fields"]
    assert fields["id_number"]["value"] == card("12")["values"]["id_number"]


def test_xoay_anh_khong_co_trong_phien_hoac_khe_sai():
    user = make_user("HR_STAFF")
    session = make_session(user, "12", sides=("front",))
    client = login_client(user)
    response = client.post(f"/nhap-cccd/{session.pk}/xoay/mat-sau/", follow=True)
    assert "Phiên không có ảnh này" in response.content.decode()
    response = client.post(f"/nhap-cccd/{session.pk}/xoay/cv/", follow=True)
    assert "Phiên không có ảnh này" in response.content.decode()


def test_xoay_bang_phuong_thuc_get_bi_chan():
    user = make_user("HR_STAFF")
    session = make_session(user, "12")
    assert login_client(user).get(f"/nhap-cccd/{session.pk}/xoay/mat-truoc/").status_code == 405


# ----- ngân sách thời gian (quyết định 5) -----


@pytest.fixture
def cham(monkeypatch):
    """OCR giả chậm: mỗi lần gọi dùng hết thời gian được cấp (kể cả khi quá giờ), đồng hồ giả."""
    clock = FakeClock()
    monkeypatch.setattr(services, "Budget", functools.partial(Budget, clock=clock))

    def slow_engine(image, timeout):
        clock.t += timeout
        raise OcrTimeout

    monkeypatch.setattr(ocr, "tesseract_engine", slow_engine)
    return clock


def test_tai_anh_voi_ocr_cham_tra_ve_duoi_90_giay_khong_loi(cham):
    user = make_user("HR_STAFF")
    client = login_client(user)
    response = client.post(
        "/nhap-cccd/",
        {"front_image": card_upload("12", "front"), "back_image": card_upload("12", "back")},
    )
    assert response.status_code == 302  # không lỗi 500
    assert cham.t < 90
    session = IntakeSession.objects.get()
    recognition = session.get_result()["recognition"]
    assert recognition["budget_exhausted"] and WARN_TIMEOUT in recognition["warnings"]
    assert all(f["value"] is None and f["low"] for f in recognition["fields"].values())
    html = client.get(response["Location"]).content.decode()
    assert WARN_TIMEOUT in html and "pa-field--low" in html


def test_xoay_anh_voi_ocr_cham_dung_ngan_sach_rieng_duoi_90_giay(cham):
    user = make_user("HR_STAFF")
    session = make_session(user, "12")
    first = cham.t
    assert 0 < first < 90
    response = login_client(user).post(f"/nhap-cccd/{session.pk}/xoay/mat-truoc/")
    assert response.status_code == 302
    # ngân sách của lần xoay tính riêng: không cộng dồn vào ngân sách của lần tạo phiên
    assert cham.t - first < 90
    session = IntakeSession.objects.get(pk=session.pk)
    assert WARN_TIMEOUT in session.get_result()["recognition"]["warnings"]
    from PIL import Image as PILImage

    assert (
        PILImage.open(session.front_image.open("rb")).size[0]
        < PILImage.open(card_upload("12").file).size[0]
    )  # ảnh vẫn được xoay


def test_ngan_sach_moi_request_la_doi_tuong_rieng(monkeypatch):
    created = []
    original = services.Budget

    def spy(*args, **kwargs):
        budget = original(*args, **kwargs)
        created.append(budget)
        return budget

    monkeypatch.setattr(services, "Budget", spy)
    user = make_user("HR_STAFF")
    session = make_session(user, "12")
    login_client(user).post(f"/nhap-cccd/{session.pk}/xoay/mat-truoc/")
    assert len(created) == 2 and created[0] is not created[1]
    assert all(b.total == 90 for b in created)


def test_hang_so_ngan_sach_la_90_giay(settings):
    assert settings.INTAKE_TOTAL_BUDGET_SECONDS == 90
    assert Worker.objects.count() == 0
