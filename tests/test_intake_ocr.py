"""OCR và tách trường theo nhãn (Phase 5 bước 2)."""

import json
from pathlib import Path

from apps.intake import imaging, ocr
from apps.intake.budget import Budget
from apps.intake.ocr import OcrTimeout, Word, extract_fields, group_lines

CARDS = Path(__file__).parent / "fixtures" / "cccd"
TRUTH = {
    c["id"]: c for c in json.loads((CARDS / "truth.json").read_text(encoding="utf-8"))["cards"]
}


def words(*lines, conf=95.0):
    """Dựng danh sách Word từ các dòng chữ (mỗi dòng một chuỗi)."""
    out = []
    for i, line in enumerate(lines):
        for token in line.split(" "):
            out.append(Word(token, conf, (1, 1, i)))
    return out


def lines_of(*texts, conf=95.0):
    return group_lines(words(*texts, conf=conf))


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


# ----- tách trường theo nhãn (không cần Tesseract) -----


def test_tach_truong_theo_nhan():
    lines = lines_of(
        "Số: 999000000001",
        "Họ và tên: NGUYỄN VĂN MẪU",
        "Ngày sinh: 05/01/1995",
        "Giới tính: Nam",
        "Quốc tịch: Việt Nam",
        "Quê quán: Phường Demo 1, Tỉnh Demo",
        "Nơi thường trú: Số 1 Đường Mẫu, Quận Kiểm Tra 1",
        "Có giá trị đến: 20/04/2036",
    )
    fields = extract_fields(lines)
    assert fields["id_number"].value == "999000000001"
    assert fields["full_name"].value == "NGUYỄN VĂN MẪU"
    assert fields["date_of_birth"].value == "1995-01-05"
    assert fields["gender"].value == "MALE"
    assert fields["nationality"].value == "Việt Nam"
    assert fields["hometown"].value == "Phường Demo 1, Tỉnh Demo"
    assert fields["permanent_address"].value == "Số 1 Đường Mẫu, Quận Kiểm Tra 1"
    assert fields["expiry_date"].value == "2036-04-20"


def test_dong_dia_chi_bat_dau_bang_so_khong_bi_nham_voi_so_cccd():
    fields = extract_fields(lines_of("Số 5 Đường Mẫu, Phường Thử"))
    assert "id_number" not in fields


def test_dau_hai_cham_dung_rieng_va_nhan_so_dinh_danh():
    fields = extract_fields(lines_of("Số định danh : 999000000007", "Ngày cấp : 20/01/2021"))
    assert fields["id_number"].value == "999000000007"
    assert fields["issue_date"].value == "2021-01-20"


def test_nhan_the_2024_va_noi_cu_tru():
    fields = extract_fields(
        lines_of(
            "Nơi cư trú: Số 7 Đường Mẫu",
            "Nơi đăng ký khai sinh: Thôn Mẫu 7, Tỉnh Demo",
            "Ngày hết hạn: 20/01/2036",
            "Nơi cấp: Cục Mẫu Thử Nghiệm",
        )
    )
    assert fields["permanent_address"].value == "Số 7 Đường Mẫu"
    assert fields["birth_registration_place"].value == "Thôn Mẫu 7, Tỉnh Demo"
    assert fields["expiry_date"].value == "2036-01-20"
    assert fields["issue_place"].value == "Cục Mẫu Thử Nghiệm"


def test_gia_tri_sai_dinh_dang_de_trong_khong_doan():
    fields = extract_fields(lines_of("Số: 99900000000", "Ngày sinh: 31/02/2000", "Giới tính: Khac"))
    assert fields["id_number"].value is None  # 11 chữ số
    assert fields["date_of_birth"].value is None
    assert fields["gender"].value is None


def test_do_tin_cay_la_gia_tri_thap_nhat_cua_cac_tu():
    line = [Word("Họ", 96, (1, 1, 1)), Word("và", 96, (1, 1, 1)), Word("tên:", 96, (1, 1, 1))]
    line += [Word("NGUYỄN", 90, (1, 1, 1)), Word("VĂN", 55, (1, 1, 1)), Word("MẪU", 93, (1, 1, 1))]
    field = extract_fields(group_lines(line))["full_name"]
    assert field.confidence == 55 and field.value == "NGUYỄN VĂN MẪU"


def test_duoi_san_tin_cay_thi_khong_hien_chu_rac():
    field = extract_fields(lines_of("Họ và tên: XYZ ABC", conf=12.0))["full_name"]
    assert field.value is None and field.confidence == 12.0


def test_nhan_dien_tieu_de_the():
    assert ocr.detect_title(lines_of("CĂN CƯỚC CÔNG DÂN")) == "legacy"
    assert ocr.detect_title(lines_of("CĂN CƯỚC (mặt sau)")) == "CAN_CUOC_2024"
    assert ocr.detect_title(lines_of("CĂN CƯỚC CÔNG DÂN (mặt sau)")) == "legacy"
    assert ocr.detect_title(lines_of("Thông tin khác")) is None


# ----- thời gian -----


def test_het_ngan_sach_thi_khong_goi_ocr():
    called = []
    budget = Budget(total=0)
    assert ocr.ocr_lines(object(), budget, engine=lambda img, t: called.append(t)) is None
    assert called == [] and budget.exhausted


def test_ocr_qua_gio_thi_tra_none_va_danh_dau_het_gio():
    def slow(image, timeout):
        raise OcrTimeout

    budget = Budget()
    assert ocr.ocr_lines(object(), budget, engine=slow) is None
    assert budget.exhausted


def test_timeout_moi_lan_goi_khong_vuot_phan_con_lai_cua_ngan_sach():
    clock = FakeClock()
    budget = Budget(total=40, clock=clock)
    seen = []

    def engine(image, timeout):
        seen.append(timeout)
        clock.t += timeout
        return []

    ocr.ocr_lines(object(), budget, engine=engine)
    ocr.ocr_lines(object(), budget, engine=engine)
    assert seen == [30.0, 10.0]  # lần 1: tối đa 30 giây; lần 2: chỉ còn 10 giây
    assert budget.expired


# ----- Tesseract thật trên thẻ giả -----


def read_card(card_id):
    card = TRUTH[card_id]
    found = {}
    for side in ("front", "back"):
        image = imaging.load_image((CARDS / card["files"][side]).read_bytes())
        found.update(extract_fields(ocr.ocr_lines(image, Budget())))
    return card, found


def test_tesseract_doc_dung_100_phan_tram_the_2016_khong_qr():
    for card_id in ("12", "13"):
        card, found = read_card(card_id)
        for name in card["printed"]:
            assert found[name].value == card["values"][name], (card_id, name)
            assert found[name].confidence >= 80


def test_tesseract_anh_mo_vua_thi_de_trong_hoac_do_tin_cay_thap():
    card, found = read_card("15")
    for name in card["printed"]:
        field = found.get(name)
        if field is None or field.value is None:
            continue
        # nếu vẫn đọc ra thì phải là đọc đúng; còn sai thì độ tin cậy phải dưới ngưỡng 80
        assert field.value == card["values"][name] or field.confidence < 80
    assert sum(1 for n in card["printed"] if found.get(n) and found[n].value) < len(card["printed"])
