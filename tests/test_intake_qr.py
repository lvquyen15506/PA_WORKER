"""Tách trường QR theo cấu hình (câu 20) và bộ thẻ giả (Phase 5 bước 1)."""

import json
import random
from types import SimpleNamespace

import pytest

from apps.core.models import QrFormat
from apps.intake import fake_cards
from apps.intake.fields import DATE_FORMATS, FIELD_LABELS, normalize
from apps.intake.qr import choose_format, parse_qr

SAMPLE = "999000000001|999123456|NGUYỄN VĂN MẪU|05011995|Nam|Số 1 Đường Mẫu|20012021"


def fmt(**kwargs):
    base = {
        "separator": "|",
        "field_order": [
            "id_number",
            "old_id_number",
            "full_name",
            "date_of_birth",
            "gender",
            "permanent_address",
            "issue_date",
        ],
        "date_format": "ddmmyyyy",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


# ----- chuẩn hóa từng trường -----


def test_normalize_gia_tri_hop_le():
    assert normalize("id_number", " 9990000 00001 ") == "999000000001"
    assert normalize("old_id_number", "999123456") == "999123456"
    assert normalize("date_of_birth", "05011995", "ddmmyyyy") == "1995-01-05"
    assert normalize("gender", "Nữ") == "FEMALE"
    assert normalize("gender", "nam") == "MALE"
    assert normalize("full_name", "  NGUYỄN   VĂN  MẪU ") == "NGUYỄN VĂN MẪU"


@pytest.mark.parametrize(
    "name,raw",
    [
        ("id_number", "12345"),
        ("id_number", "99900000000A"),
        ("old_id_number", "1234567"),
        ("date_of_birth", "31022000"),  # 31/02 không tồn tại
        ("date_of_birth", "5/1/95"),
        ("gender", "Khác"),
        ("gender", ""),
        ("full_name", "   "),
    ],
)
def test_normalize_sai_dinh_dang_thi_bo_trong(name, raw):
    assert normalize(name, raw) is None


def test_normalize_ten_truong_la_bi_tu_choi():
    with pytest.raises(ValueError):
        normalize("khong_co", "x")


def test_cac_dinh_dang_ngay():
    expected = {
        "ddmmyyyy": "05011995",
        "dd/mm/yyyy": "05/01/1995",
        "dd-mm-yyyy": "05-01-1995",
        "yyyymmdd": "19950105",
        "yyyy-mm-dd": "1995-01-05",
    }
    assert set(expected) == set(DATE_FORMATS)
    for name, raw in expected.items():
        assert normalize("date_of_birth", raw, name) == "1995-01-05"


# ----- parse_qr -----


def test_parse_theo_cau_hinh_mac_dinh():
    result = parse_qr(SAMPLE, fmt())
    assert result.ok
    assert result.values == {
        "id_number": "999000000001",
        "old_id_number": "999123456",
        "full_name": "NGUYỄN VĂN MẪU",
        "date_of_birth": "1995-01-05",
        "gender": "MALE",
        "permanent_address": "Số 1 Đường Mẫu",
        "issue_date": "2021-01-20",
    }


def test_phan_tu_rong_thi_khong_dien():
    result = parse_qr("999000000001||NGUYỄN VĂN MẪU|05011995|Nam||20012021", fmt())
    assert result.ok
    assert "old_id_number" not in result.values and "permanent_address" not in result.values


def test_doi_dau_phan_cach_theo_cau_hinh():
    raw = SAMPLE.replace("|", ";")
    assert not parse_qr(raw, fmt()).ok
    assert parse_qr(raw, fmt(separator=";")).values["full_name"] == "NGUYỄN VĂN MẪU"


def test_doi_thu_tu_truong_theo_cau_hinh():
    order = ["full_name", "id_number", "date_of_birth", "gender"]
    result = parse_qr("NGUYỄN VĂN MẪU|999000000001|05011995|Nữ", fmt(field_order=order))
    assert result.ok
    assert result.values == {
        "full_name": "NGUYỄN VĂN MẪU",
        "id_number": "999000000001",
        "date_of_birth": "1995-01-05",
        "gender": "FEMALE",
    }


def test_doi_dinh_dang_ngay_theo_cau_hinh():
    raw = SAMPLE.replace("05011995", "1995-01-05").replace("20012021", "2021-01-20")
    assert "date_of_birth" not in parse_qr(raw, fmt()).values  # sai định dạng thì bỏ trống
    result = parse_qr(raw, fmt(date_format="yyyy-mm-dd"))
    assert result.values["date_of_birth"] == "1995-01-05"
    assert result.values["issue_date"] == "2021-01-20"


def test_skip_va_ten_la_bi_bo_qua():
    order = ["id_number", "skip", "full_name", "khong_co", "date_of_birth", "gender", "skip"]
    result = parse_qr("999000000001|bo|NGUYỄN VĂN MẪU|x|05011995|Nam|y", fmt(field_order=order))
    assert result.ok and set(result.values) == {
        "id_number",
        "full_name",
        "date_of_birth",
        "gender",
    }


def test_sai_so_phan_tu_thi_khong_dien_gi():
    for raw in (SAMPLE + "|them", "999000000001|a|b"):
        result = parse_qr(raw, fmt())
        assert not result.ok and result.values == {}


def test_so_dinh_danh_sai_thi_khong_khop():
    result = parse_qr(SAMPLE.replace("999000000001", "12345"), fmt())
    assert not result.ok and result.values == {}


def test_chuoi_rong():
    assert not parse_qr("", fmt()).ok
    assert not parse_qr(None, fmt()).ok


# ----- choose_format -----


@pytest.mark.django_db
def test_choose_format_hai_cau_hinh_giong_nhau_chon_theo_ngay_cap():
    # Đổi theo quy tắc mới: trước đây chọn mẫu đứng trước (Căn cước 2024), nên thẻ cấp 2021 bị
    # nhận sai. SAMPLE cấp 20/01/2021 thì không thể là Căn cước 2024.
    qr_format, result = choose_format(SAMPLE)
    assert qr_format.id_doc_type == "CCCD_2021" and result.ok


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("issue", "expected"),
    [
        ("30062024", "CCCD_2021"),  # ngày cuối trước mốc
        ("01072024", "CAN_CUOC_2024"),  # đúng ngày bắt đầu
        ("15032025", "CAN_CUOC_2024"),
        ("20012021", "CCCD_2021"),
    ],
)
def test_choose_format_ranh_gioi_ngay_cap_01_07_2024(issue, expected):
    raw = f"999000000001|999123456|NGUYỄN VĂN MẪU|05011995|Nam|Số 1 Đường Mẫu|{issue}"
    assert choose_format(raw)[0].id_doc_type == expected


@pytest.mark.django_db
def test_choose_format_khong_co_ngay_cap_giu_thu_tu_ma_mau_the():
    raw = "999000000001|999123456|NGUYỄN VĂN MẪU|05011995|Nam|Số 1 Đường Mẫu|"
    assert choose_format(raw)[0].id_doc_type == "CAN_CUOC_2024"


@pytest.mark.django_db
def test_choose_format_mau_hr_chon_van_duoc_giu_ke_ca_ngay_cap_som():
    qr_format, _ = choose_format(SAMPLE, doc_type="CAN_CUOC_2024")
    assert qr_format.id_doc_type == "CAN_CUOC_2024"


# ----- Kiểm tra hợp lệ chữ trong QR (CJK, ký tự lạ, họ tên ≥ 2 từ) -----
@pytest.mark.parametrize(
    "name",
    ["日本語 氏名", "ﾄ雪ｺｷng Vﾄハ ﾆｯ盻嫩", "Nguyễn Văn Ａ", "NGUYEN ☺ VAN", "Nguyễn"],
)
def test_ho_ten_cjk_la_hoac_mot_tu_bi_loai_khoi_ket_qua(name):
    raw = f"999000000001|999123456|{name}|05011995|Nam|Số 1 Đường Mẫu|20012021"
    result = parse_qr(raw, fmt())
    assert result.ok and "full_name" not in result.values
    assert result.rejected == ["full_name"]
    assert result.values["id_number"] == "999000000001"  # các trường hợp lệ khác vẫn giữ


def test_dia_chi_co_ky_tu_la_bi_loai_nhung_dia_chi_viet_hop_le_duoc_nhan():
    bad = parse_qr(SAMPLE.replace("Số 1 Đường Mẫu", "住所 1"), fmt())
    assert "permanent_address" not in bad.values and "permanent_address" in bad.rejected
    for good in (
        "Số 1 Đường Mẫu, Phường Thử Nghiệm",
        "12/3 Ngõ 4-5, Xã Ước Lệ",
        "Thôn Đặng (Tổ 2)",
    ):
        ok = parse_qr(SAMPLE.replace("Số 1 Đường Mẫu", good), fmt())
        assert ok.values["permanent_address"] == good and not ok.rejected


@pytest.mark.parametrize("name", ["Nguyễn Thị Hương Quỳnh", "Đặng Văn Ước", "LÊ THỊ ÁNH NGUYỆT"])
def test_ho_ten_nhieu_dau_hop_le(name):
    raw = f"999000000001|999123456|{name}|05011995|Nam|Số 1 Đường Mẫu|20012021"
    assert parse_qr(raw, fmt()).values["full_name"] == name


@pytest.mark.django_db
def test_choose_format_theo_mau_the_duoc_chon():
    qr_format, result = choose_format(SAMPLE, doc_type="CCCD_2021")
    assert qr_format.id_doc_type == "CCCD_2021" and result.ok


@pytest.mark.django_db
def test_choose_format_khi_hai_cau_hinh_khac_nhau():
    QrFormat.objects.filter(id_doc_type="CAN_CUOC_2024").update(separator=";")
    qr_format, _ = choose_format(SAMPLE)
    assert qr_format.id_doc_type == "CCCD_2021"
    qr_format, result = choose_format(SAMPLE.replace("|", ";"))
    assert qr_format.id_doc_type == "CAN_CUOC_2024" and result.ok
    assert choose_format(SAMPLE, doc_type="CAN_CUOC_2024") == (None, None)


@pytest.mark.django_db
def test_choose_format_bo_qua_cau_hinh_da_tat_va_khong_khop():
    QrFormat.objects.update(is_active=False)
    assert choose_format(SAMPLE) == (None, None)
    QrFormat.objects.update(is_active=True)
    assert choose_format("khong phai qr") == (None, None)


def test_nhan_cho_moi_truong_nhan_dien():
    assert FIELD_LABELS["id_number"] == "Số CCCD" and len(FIELD_LABELS) == 12


# ----- bộ thẻ giả -----


@pytest.fixture
def cards(tmp_path):
    formats = {
        "CCCD_2021": fmt(),
        "CAN_CUOC_2024": fmt(),
        "CCCD_2016": fmt(),
    }
    return tmp_path, fake_cards.generate_cards(tmp_path, formats)


def test_bo_15_the_gia(cards):
    out, items = cards
    assert len(items) == 15
    assert len(list(out.glob("*.png"))) == 30
    by_type = {}
    for card in items:
        by_type.setdefault(card["doc_type"], []).append(card)
        assert card["values"]["id_number"].startswith("999")  # CCCD giả luôn bắt đầu 999
    assert {k: len(v) for k, v in by_type.items()} == {
        "CCCD_2021": 6,
        "CAN_CUOC_2024": 5,
        "CCCD_2016": 4,
    }
    assert all(not c["has_qr"] for c in by_type["CCCD_2016"])
    assert 3 <= sum(c["quality"] != "good" for c in items) <= 4
    truth = json.loads((out / "truth.json").read_text(encoding="utf-8"))
    assert truth["watermark"] == "MẪU – KHÔNG CÓ GIÁ TRỊ" and len(truth["cards"]) == 15


def test_qr_sinh_ra_tach_lai_dung_100_phan_tram(cards):
    _, items = cards
    for card in items:
        if not card["has_qr"]:
            continue
        payload, present = fake_cards.build_qr_payload(card["values"], fmt())
        result = parse_qr(payload, fmt())
        assert result.ok
        assert sorted(result.values) == sorted(card["qr_fields"]) == sorted(present)
        for name, value in result.values.items():
            assert value == card["values"][name]


def test_qr_the_gia_theo_cau_hinh_moi():
    """Đổi cấu hình thì chuỗi QR sinh ra đổi theo, và chỉ tách đúng bằng cấu hình mới."""
    values = fake_cards._make_values(random.Random(1), 7, "CCCD_2021")
    new = fmt(
        separator=";",
        field_order=["full_name", "id_number", "date_of_birth"],
        date_format="dd/mm/yyyy",
    )
    payload, _ = fake_cards.build_qr_payload(values, new)
    assert ";" in payload and "|" not in payload
    assert parse_qr(payload, new).values["id_number"] == values["id_number"]
    assert not parse_qr(payload, fmt()).ok
