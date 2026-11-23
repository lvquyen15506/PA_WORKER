"""Sửa lỗi nhận diện phát hiện khi thử thẻ thật (A–D): QR sai bảng mã, nhận sai loại thẻ, gợi ý
cho trường không đọc được. Chỉ dùng dữ liệu giả; không có ảnh hay chữ của thẻ thật."""

import datetime
import json
from pathlib import Path

import pytest

from apps.core.choices import FieldSource
from apps.intake import fake_cards, imaging, ocr, qr_reader
from apps.intake.fields import labels_for, plausible_qr_text
from apps.intake.hints import ISSUE_PLACE_HINT, compute_expiry
from apps.intake.ocr import Word, extract_fields, group_lines
from apps.intake.pipeline import _build_fields, recognize
from apps.intake.qr import WARN_BAD_QR

pytestmark = pytest.mark.django_db
D = datetime.date
CARDS = Path(__file__).parent / "fixtures" / "cccd"
TRUTH = json.loads((CARDS / "truth.json").read_text(encoding="utf-8"))["cards"]
SIDES = {"front": None, "back": None}


def lines_of(*texts, conf=95.0):
    words = []
    for i, line in enumerate(texts):
        words += [Word(token, conf, (1, 1, i)) for token in line.split(" ")]
    return group_lines(words)


def stub_engine(*texts, conf=95.0):
    lines = group_lines(
        [Word(t, conf, (1, 1, i)) for i, line in enumerate(texts) for t in line.split(" ")]
    )

    def engine(image, timeout):
        return [w for line in lines for w in line]

    return engine


def blank():
    return imaging.load_image(b"") if False else None


# ===== A. QR sai bảng mã =====
def mojibake(text):
    """Cách zbar hiểu nhầm: byte UTF-8 bị đọc là Shift-JIS rồi trả lại bằng UTF-8."""
    return text.encode("utf-8").decode("shift_jis").encode("utf-8")


@pytest.mark.parametrize(
    "text", ["Đặng Văn Ước", "Trần Văn Mẫu|05011995|Nam", "Đặng Văn Ước|999000000001|Nữ"]
)
def test_decode_text_sua_chu_nhat_do_zbar_doan_sai_shift_jis(text):
    garbled = mojibake(text)
    assert not plausible_qr_text(garbled.decode("utf-8"))  # đúng là chữ Nhật/katakana
    assert qr_reader.decode_text(garbled) == text


def test_decode_text_utf8_hop_le_giu_nguyen_va_chu_khong_hop_le_tra_cach_hieu_dau_tien():
    assert qr_reader.decode_text("Nguyễn Thị Hương Quỳnh".encode()) == "Nguyễn Thị Hương Quỳnh"
    lossy = "Nguyễn Thị Hương Quỳnh".encode().decode("latin-1").encode("utf-8")
    # không sửa được bằng Shift-JIS: trả bản đầu để bộ tách trường loại ra, không đoán
    assert qr_reader.decode_text(lossy) == lossy.decode("utf-8").strip()


@pytest.mark.parametrize("eci", [False, True])
@pytest.mark.parametrize("name", list(fake_cards.SPECIAL_NAMES.values()))
def test_doc_qr_ten_nhieu_dau_ma_hoa_utf8_co_va_khong_co_eci(name, eci):
    payload = f"999000000001|999123456|{name.upper()}|05011995|Nam|Số 1 Đường Mẫu, Xã Ước|20012021"
    qr = fake_cards._qr_image(payload, eci)
    reading = qr_reader.read_qr(imaging.to_gray(qr.convert("RGB")))
    assert reading is not None and reading.text == payload


def test_bo_the_gia_co_ten_nhieu_dau_va_qr_co_ca_hai_kieu_eci():
    qr_cards = [c for c in TRUTH if c["has_qr"]]
    assert {c["qr_eci"] for c in qr_cards} == {True, False}
    names = {c["values"]["full_name"] for c in qr_cards}
    assert "NGUYỄN THỊ HƯƠNG QUỲNH" in names and "ĐẶNG VĂN ƯỚC" in names


def test_pipeline_qr_chu_cjk_de_trong_ho_ten_to_vang_va_canh_bao(monkeypatch):
    from apps.intake import pipeline

    garbled = "999000000001|999123456|日本語 氏名|05011995|Nam|住所 1|20012021"
    monkeypatch.setattr(
        pipeline.qr_reader, "read_qr", lambda *a, **k: qr_reader.QrReading(garbled, (0, 0, 10, 10))
    )
    image = imaging.load_image((CARDS / TRUTH[0]["files"]["front"]).read_bytes())
    result = recognize(image, None, engine=stub_engine("Dòng không có nhãn"))
    name = result["fields"]["full_name"]
    assert name["value"] is None and name["low"] is True and name["source"] is None
    assert WARN_BAD_QR in result["warnings"]
    assert result["fields"]["id_number"]["value"] == "999000000001"  # trường hợp lệ vẫn dùng
    assert result["fields"]["id_number"]["source"] == "QR"


def test_pipeline_qr_chu_cjk_nhung_ocr_doc_duoc_ho_ten_thi_dung_ocr(monkeypatch):
    from apps.intake import pipeline

    garbled = "999000000001|999123456|日本語 氏名|05011995|Nam|Số 1 Đường Mẫu|20012021"
    monkeypatch.setattr(
        pipeline.qr_reader, "read_qr", lambda *a, **k: qr_reader.QrReading(garbled, (0, 0, 10, 10))
    )
    image = imaging.load_image((CARDS / TRUTH[0]["files"]["front"]).read_bytes())
    result = recognize(image, None, engine=stub_engine("Họ và tên: NGUYỄN VĂN MẪU"))
    name = result["fields"]["full_name"]
    assert name["value"] == "NGUYỄN VĂN MẪU" and name["source"] == "OCR"
    assert WARN_BAD_QR in result["warnings"]


# ===== B. Nhận đúng loại thẻ =====
def test_the_gia_cccd_2021_khong_bi_nhan_la_can_cuoc_2024():
    for c in TRUTH:
        if c["doc_type"] == "CCCD_2021":
            issued = D.fromisoformat(c["values"]["issue_date"])
            assert issued < D(2024, 7, 1)
            ims = {s: imaging.load_image((CARDS / f).read_bytes()) for s, f in c["files"].items()}
            result = recognize(ims["front"], ims["back"])
            assert result["doc_type"] == "CCCD_2021", c["id"]


def test_tieu_de_doan_can_cuoc_nhung_ngay_cap_2021_thi_doi_ve_cccd_2021():
    qr = "999000000001|999123456|NGUYỄN VĂN MẪU|05011995|Nam|Số 1 Đường Mẫu|20012021"
    from apps.intake import pipeline

    image = imaging.load_image((CARDS / TRUTH[0]["files"]["front"]).read_bytes())
    original = pipeline.qr_reader.read_qr
    pipeline.qr_reader.read_qr = lambda *a, **k: qr_reader.QrReading(qr, (0, 0, 10, 10))
    try:
        result = recognize(image, None, engine=stub_engine("CĂN CƯỚC", "Họ và tên: NGUYỄN VĂN MẪU"))
    finally:
        pipeline.qr_reader.read_qr = original
    assert result["doc_type"] == "CCCD_2021" and result["doc_type_source"] == "issue_date"


def test_hr_chon_tay_can_cuoc_2024_thi_khong_bi_doi_theo_ngay_cap():
    qr = "999000000001|999123456|NGUYỄN VĂN MẪU|05011995|Nam|Số 1 Đường Mẫu|20012021"
    from apps.intake import pipeline

    image = imaging.load_image((CARDS / TRUTH[0]["files"]["front"]).read_bytes())
    original = pipeline.qr_reader.read_qr
    pipeline.qr_reader.read_qr = lambda *a, **k: qr_reader.QrReading(qr, (0, 0, 10, 10))
    try:
        result = recognize(image, None, doc_type="CAN_CUOC_2024", engine=stub_engine("x"))
    finally:
        pipeline.qr_reader.read_qr = original
    assert result["doc_type"] == "CAN_CUOC_2024" and result["doc_type_source"] == "chosen"


# ===== C. OCR theo nhãn đúng mẫu thẻ, nhãn song ngữ =====
def test_nhan_can_cuoc_2024_ngay_thang_nam_het_han_khong_bi_nhan_la_ngay_cap():
    lines = lines_of("Ngày, tháng, năm hết hạn: 01/02/2035", "Ngày cấp: 15/03/2025")
    found = extract_fields(lines, "CAN_CUOC_2024")
    assert found["expiry_date"].value == "2035-02-01"
    assert found["issue_date"].value == "2025-03-15"
    assert ("ngay", "thang", "nam", "het", "han") in labels_for("CAN_CUOC_2024")["expiry_date"]
    assert ("ngay", "thang", "nam", "het", "han") not in labels_for("CCCD_2021")["expiry_date"]


def test_nhan_song_ngu_bo_phan_tieng_anh_lay_sau_dau_hai_cham():
    lines = lines_of(
        "Họ và tên / Full name: NGUYỄN VĂN MẪU",
        "Ngày sinh/Date of birth: 05/01/1995",
        "Quốc tịch / Nationality: Việt Nam",
        "Nơi thường trú / Place of residence: Số 1 Đường Mẫu, Phường Demo",
    )
    found = extract_fields(lines, "CCCD_2021")
    assert found["full_name"].value == "NGUYỄN VĂN MẪU"
    assert found["date_of_birth"].value == "1995-01-05"
    assert found["nationality"].value == "Việt Nam"
    assert found["permanent_address"].value == "Số 1 Đường Mẫu, Phường Demo"


def test_ocr_chi_dung_ngon_ngu_vie(monkeypatch):
    seen = {}

    def fake(image, **kwargs):
        seen.update(kwargs)
        return {"text": [], "conf": [], "block_num": [], "par_num": [], "line_num": []}

    monkeypatch.setattr(ocr.pytesseract, "image_to_data", fake)
    ocr.tesseract_engine(imaging.load_image((CARDS / TRUTH[0]["files"]["front"]).read_bytes()), 5)
    assert seen["lang"] == "vie"


# ===== C2. Gợi ý =====
def build(card_type, values, sides=("front", "back"), threshold=80, conf=95.0):
    """Trường nhận diện từ các dòng OCR giả; `values` là {nhãn dòng: giá trị}."""
    lines = lines_of(*[f"{k}: {v}" for k, v in values.items()], conf=conf)
    return _build_fields(card_type, lines, dict.fromkeys(sides), {}, threshold)


def test_goi_y_noi_cap_quoc_tich_va_han_khi_ocr_khong_doc_duoc():
    fields, notes = build("CCCD_2021", {"Ngày sinh": "05/01/1995", "Ngày cấp": "20/01/2021"})
    assert fields["issue_place"] == {
        "value": ISSUE_PLACE_HINT["CCCD_2021"],
        "source": "HINT",
        "confidence": None,
        "low": True,
    }
    assert (
        fields["nationality"]["value"] == "Việt Nam" and fields["nationality"]["source"] == "HINT"
    )
    expiry = fields["expiry_date"]
    assert expiry["value"] == "2035-01-05" and expiry["source"] == "HINT" and expiry["low"] is True
    assert all(fields[n]["low"] for n in ("issue_place", "nationality", "expiry_date"))
    assert notes == []


@pytest.mark.parametrize("card_type", ["CCCD_2021", "CCCD_2016", "CAN_CUOC_2024"])
def test_noi_cap_goi_y_theo_tung_mau_the(card_type):
    fields, _ = build(card_type, {"Ngày sinh": "05/01/1995", "Ngày cấp": "20/01/2025"})
    assert fields["issue_place"]["value"] == ISSUE_PLACE_HINT[card_type]


def test_ocr_doc_duoc_thi_khong_goi_y_de_len_va_nguon_van_la_ocr():
    fields, notes = build(
        "CCCD_2021",
        {
            "Ngày sinh": "05/01/1995",
            "Ngày cấp": "20/01/2021",
            "Nơi cấp": "Cục Mẫu Thử Nghiệm",
            "Quốc tịch": "Việt Nam",
            "Có giá trị đến": "05/01/2035",
        },
    )
    assert fields["issue_place"]["source"] == "OCR" and fields["nationality"]["source"] == "OCR"
    assert fields["expiry_date"]["source"] == "OCR" and fields["expiry_date"]["low"] is False
    assert notes == []


def test_ocr_doc_han_khac_gia_tri_tinh_thi_giu_ocr_to_vang_va_canh_bao():
    fields, notes = build(
        "CCCD_2021",
        {"Ngày sinh": "05/01/1995", "Ngày cấp": "20/01/2021", "Có giá trị đến": "20/01/2036"},
    )
    expiry = fields["expiry_date"]
    assert expiry["value"] == "2036-01-20" and expiry["source"] == "OCR" and expiry["low"] is True
    assert notes == ["Có giá trị đến: Khác với hạn tính theo quy định (05/01/2035)."]


def test_cap_tu_60_tuoi_khong_thoi_han_de_trong_to_vang_co_ghi_chu():
    fields, notes = build("CCCD_2021", {"Ngày sinh": "05/01/1950", "Ngày cấp": "20/01/2021"})
    assert fields["expiry_date"] == {"value": None, "source": None, "confidence": None, "low": True}
    assert notes == ["Có giá trị đến: thẻ cấp từ 60 tuổi không thời hạn, để trống."]


def test_thieu_ngay_sinh_hoac_ngay_cap_thi_khong_tinh_han():
    fields, notes = build("CCCD_2021", {"Ngày cấp": "20/01/2021"})
    assert fields["expiry_date"]["value"] is None and fields["expiry_date"]["low"] is True
    assert notes == []


def test_chi_mot_mat_thi_chi_goi_y_truong_cua_mat_do():
    fields, _ = build("CCCD_2021", {"Ngày cấp": "20/01/2021"}, sides=("back",))
    assert "issue_place" in fields and "nationality" not in fields and "expiry_date" not in fields


def test_chua_biet_mau_the_thi_khong_goi_y():
    fields, _ = _build_fields(None, [], dict.fromkeys(("front", "back")), {}, 80)
    assert not any(f["source"] == "HINT" for f in fields.values())


@pytest.mark.parametrize(
    ("issue", "expected"),
    [
        # sinh 15/06/1990
        (D(2012, 6, 14), D(2015, 6, 15)),  # 22 tuổi 364 ngày: hết hạn lúc 25 tuổi
        (D(2013, 6, 14), D(2015, 6, 15)),  # 22 tuổi 364 ngày (trước mốc 23 tuổi)
        (D(2013, 6, 15), D(2030, 6, 15)),  # đúng 23 tuổi: trong 2 năm trước mốc 25 → mốc 40
        (D(2014, 6, 15), D(2030, 6, 15)),  # 24 tuổi
        (D(2015, 6, 15), D(2030, 6, 15)),  # đúng 25 tuổi
        (D(2028, 6, 14), D(2030, 6, 15)),  # 37 tuổi 364 ngày: chưa tới 2 năm trước mốc 40
        (D(2028, 6, 15), D(2050, 6, 15)),  # 38 tuổi: trong 2 năm trước mốc 40 → mốc 60
        (D(2030, 6, 15), D(2050, 6, 15)),  # đúng 40 tuổi
        (D(2048, 6, 14), D(2050, 6, 15)),  # 57 tuổi 364 ngày: chưa vào 2 năm trước mốc 60
        (D(2048, 6, 15), None),  # 58 tuổi: trong 2 năm trước mốc 60 → không thời hạn
        (D(2050, 6, 15), None),  # đúng 60 tuổi
        (D(2060, 1, 1), None),  # sau 60 tuổi
    ],
)
def test_tinh_han_ca_bien_moc_tuoi_25_40_60(issue, expected):
    dob = D(1990, 6, 15)
    assert compute_expiry(dob, issue) == expected


def test_tinh_han_du_lieu_khong_dung_duoc_va_sinh_29_02():
    assert compute_expiry(None, D(2021, 1, 1)) is None
    assert compute_expiry(D(2000, 1, 1), None) is None
    assert compute_expiry(D(2000, 1, 1), D(1999, 1, 1)) is None  # cấp trước ngày sinh
    # Sinh 29/02: mốc 25 tuổi rơi vào 2025 (không nhuận) → 28/02/2025; mốc 40 → 29/02/2040.
    assert compute_expiry(D(2000, 2, 29), D(2022, 1, 1)) == D(2025, 2, 28)
    assert compute_expiry(D(2000, 2, 29), D(2023, 3, 1)) == D(2040, 2, 29)  # trong 2 năm trước 25
    assert compute_expiry(D(1996, 2, 29), D(2010, 1, 1)) == D(
        2021, 2, 28
    )  # 25 tuổi, 2021 không nhuận


# ===== Nhãn nguồn Gợi ý =====
def test_field_source_co_goi_y_va_nhan_hien_thi():
    assert FieldSource.HINT.value == "HINT" and FieldSource.HINT.label == "Gợi ý"
    from django.template.loader import render_to_string

    html = render_to_string("components/_source_tag.html", {"source": "HINT"})
    assert "Gợi ý" in html and "pa-source" in html


def test_ui_kit_co_nhan_goi_y():
    from tests.factories import login_client, make_user

    page = login_client(make_user("ADMIN")).get("/ui-kit/").content.decode()
    assert page.count('class="pa-source"') >= 4 and "Gợi ý" in page


def test_man_hinh_doi_chieu_hien_nhan_goi_y_va_bat_tich_da_kiem_tra():
    from tests.factories import login_client, make_user
    from tests.intake_helpers import make_session

    hr = make_user("HR_STAFF")
    session = make_session(hr, "01")  # thẻ giả CCCD 2021: nơi cấp in trên thẻ nên OCR đọc được
    result = session.get_result()["recognition"]
    result["fields"]["issue_place"] = {
        "value": ISSUE_PLACE_HINT["CCCD_2021"],
        "source": "HINT",
        "confidence": None,
        "low": True,
    }
    session.set_result({**session.get_result(), "recognition": result})
    session.save()
    page = login_client(hr).get(f"/nhap-cccd/{session.pk}/").content.decode()
    assert ">Gợi ý<" in page
    assert 'name="issue_place__checked"' in page  # trường tô vàng buộc tích Đã kiểm tra


# ===== zxing-cpp là bộ đọc chính =====
@pytest.mark.parametrize("name", list(fake_cards.SPECIAL_NAMES.values()) + ["Phạm Thị Thuỷ Ái"])
def test_zxing_doc_dung_100_phan_tram_qr_khong_eci_ten_nhieu_dau(name):
    """Ca trước đó mất dữ liệu: QR UTF-8 không ECI; zxing-cpp đọc byte gốc nên phải đúng hết."""
    import zxingcpp

    payload = f"999000000001|999123456|{name.upper()}|05011995|Nam|Số 1 Đường Mẫu, Xã Ước|20012021"
    gray = imaging.to_gray(fake_cards._qr_image(payload, eci=False).convert("RGB"))
    results = zxingcpp.read_barcodes(gray, formats=zxingcpp.BarcodeFormat.QRCode)
    assert [bytes(r.bytes).decode("utf-8") for r in results] == [payload]
    reading = qr_reader._zxing_read(gray, 1.0)  # đường chính, không qua pyzbar
    assert reading is not None and reading.text == payload and len(reading.rect) == 4


def test_read_qr_dung_zxing_truoc_pyzbar_va_dung_pyzbar_khi_zxing_loi(monkeypatch):
    payload = "999000000001|999123456|ĐẶNG VĂN ƯỚC|05011995|Nam|Số 1 Đường Mẫu|20012021"
    gray = imaging.to_gray(fake_cards._qr_image(payload).convert("RGB"))

    def boom(*a, **k):
        raise AssertionError("pyzbar không được gọi khi zxing đọc được")

    monkeypatch.setattr(qr_reader.pyzbar, "decode", boom)
    assert qr_reader.read_qr(gray).text == payload
    monkeypatch.undo()
    monkeypatch.setattr(
        qr_reader.zxingcpp, "read_barcodes", lambda *a, **k: (_ for _ in ()).throw(RuntimeError)
    )
    assert qr_reader.read_qr(gray).text == payload  # dự phòng pyzbar vẫn đọc được
