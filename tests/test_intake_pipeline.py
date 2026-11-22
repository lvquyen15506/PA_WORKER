"""Quy trình nhận diện: ảnh -> QR -> OCR -> trường (Phase 5 bước 2, kịch bản 3 và 4)."""

import json
import random
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.core.models import QrFormat
from apps.intake import fake_cards, imaging
from apps.intake.budget import Budget
from apps.intake.ocr import OcrTimeout
from apps.intake.pipeline import WARN_TIMEOUT, recognize

pytestmark = pytest.mark.django_db

CARDS = Path(__file__).parent / "fixtures" / "cccd"
TRUTH = json.loads((CARDS / "truth.json").read_text(encoding="utf-8"))["cards"]
QR_CARDS = [c["id"] for c in TRUTH if c["has_qr"]]


def card(card_id):
    return next(c for c in TRUTH if c["id"] == card_id)


def images(card_id):
    c = card(card_id)
    return {s: imaging.load_image((CARDS / f).read_bytes()) for s, f in c["files"].items()}


def run(card_id, **kwargs):
    ims = images(card_id)
    return recognize(ims["front"], ims["back"], **kwargs)


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


# ----- kịch bản 3: thẻ có QR -----


@pytest.mark.parametrize("card_id", QR_CARDS)
def test_dien_dung_100_phan_tram_truong_co_trong_qr(card_id):
    c, result = card(card_id), run(card_id)
    assert result["qr"]["raw"] and result["qr"]["side"] == c["qr_side"]
    for name in c["qr_fields"]:
        field = result["fields"][name]
        assert field["value"] == c["values"][name], name
        assert field["source"] == "QR" and field["low"] is False and field["confidence"] is None
    # mẫu thẻ nhận đúng nhờ tiêu đề dù hai cấu hình QR đang giống nhau (câu 20)
    assert result["doc_type"] == c["doc_type"] and result["doc_type_source"] == "qr"


@pytest.mark.parametrize("card_id", QR_CARDS)
def test_truong_khong_co_trong_qr_duoc_ocr_bo_sung_dung(card_id):
    c, result = card(card_id), run(card_id)
    for name in c["printed"]:
        field = result["fields"][name]
        assert field["value"] == c["values"][name], name
        if name not in c["qr_fields"]:
            assert field["source"] == "OCR" and field["confidence"] >= 80


def test_so_cmnd_cu_chi_co_trong_qr_van_duoc_dien():
    c = next(c for c in TRUTH if c["has_qr"] and c["values"]["old_id_number"])
    result = run(c["id"])
    assert result["fields"]["old_id_number"]["value"] == c["values"]["old_id_number"]
    assert result["fields"]["old_id_number"]["source"] == "QR"


# ----- kịch bản 4: thẻ không QR -----


def test_the_khong_qr_ocr_dien_duoc():
    result = run("12")
    assert result["qr"]["raw"] is None and result["doc_type"] == "CCCD_2016"
    c = card("12")
    for name in c["printed"]:
        field = result["fields"][name]
        assert field["value"] == c["values"][name] and field["source"] == "OCR"
        assert field["low"] is False


def test_nguong_tin_cay_cau_hinh_duoc_to_vang():
    result = run("12", threshold=99)
    assert any(f["low"] and f["value"] for f in result["fields"].values())


def test_anh_mo_truong_khong_chac_chan_de_trong_va_to_vang():
    result = run("15")
    assert any("mờ" in w for w in result["warnings"])
    for field in result["fields"].values():
        if field["value"] is None:
            assert field["low"] is True and field["source"] is None
        elif field["source"] == "OCR" and field["confidence"] < 80:
            assert field["low"] is True
    assert sum(1 for f in result["fields"].values() if f["low"]) >= 5


def test_chi_mot_mat_thi_chi_doi_truong_cua_mat_do():
    result = recognize(images("12")["front"], None)
    assert "issue_date" not in result["fields"] and "id_number" in result["fields"]


def test_mat_sau_cua_the_2024_chua_qr_van_doc_duoc_khi_chi_tai_mat_sau():
    c = card("07")
    result = recognize(None, images("07")["back"])
    assert result["qr"]["side"] == "back"
    assert result["fields"]["id_number"]["value"] == c["values"]["id_number"]


def test_nguoi_dung_chon_mau_the_thi_dung_mau_do():
    result = run("12", doc_type="CCCD_2021")
    assert result["doc_type"] == "CCCD_2021" and result["doc_type_source"] == "chosen"


# ----- đổi cấu hình QR không cần sửa code (câu 20) -----


def test_doi_cau_hinh_qr_thi_bo_tach_dung_cau_hinh_moi():
    values = fake_cards._make_values(random.Random(5), 77, "CCCD_2021")
    QrFormat.objects.update(
        separator=";",
        field_order=["full_name", "id_number", "date_of_birth", "gender", "issue_date"],
        date_format="dd/mm/yyyy",
    )
    new_format = SimpleNamespace(**QrFormat.objects.filter(id_doc_type="CCCD_2021").values()[0])
    payload, present = fake_cards.build_qr_payload(values, new_format)
    front = fake_cards._draw_side("CCCD_2021", "front", values, payload)
    result = recognize(front, None)
    for name in present:
        assert result["fields"][name]["value"] == values[name]
        assert result["fields"][name]["source"] == "QR"
    assert result["qr"]["format"] in {"CCCD_2021", "CAN_CUOC_2024"}


def test_cau_hinh_cu_khong_con_khop_thi_khong_dien_tu_qr():
    QrFormat.objects.update(separator=";")  # ảnh trong bộ mẫu vẫn dùng "|"
    result = run("01")
    assert result["qr"]["format"] is None
    assert all(f["source"] != "QR" for f in result["fields"].values())
    assert result["fields"]["id_number"]["value"] == card("01")["values"]["id_number"]  # OCR


# ----- ngân sách thời gian (quyết định 5) -----


def test_het_ngan_sach_ngay_tu_dau_thi_truong_de_trong_to_vang_co_canh_bao():
    result = run("01", budget=Budget(total=0))
    assert WARN_TIMEOUT in result["warnings"] and result["budget_exhausted"]
    assert result["fields"] and all(
        f["value"] is None and f["low"] for f in result["fields"].values()
    )


def test_ocr_gia_cham_van_tra_ve_duoi_90_giay_khong_loi():
    clock = FakeClock()
    budget = Budget(clock=clock)  # mặc định 90 giây

    def slow_engine(image, timeout):
        clock.t += timeout  # dùng hết thời gian được cấp rồi quá giờ
        raise OcrTimeout

    result = run("12", budget=budget, engine=slow_engine)
    assert clock.t < 90 and budget.total == 90
    assert WARN_TIMEOUT in result["warnings"]
    assert all(f["value"] is None and f["low"] for f in result["fields"].values())


def test_ocr_cham_hon_phan_duoc_cap_thi_cac_buoc_sau_bi_bo():
    clock = FakeClock()
    budget = Budget(total=90, clock=clock)
    calls = []

    def stubborn(image, timeout):
        calls.append(timeout)
        clock.t += 80  # bỏ qua timeout, chạy 80 giây mỗi lần
        return []

    result = run("12", budget=budget, engine=stubborn)
    assert calls == [30.0, 10.0]  # lần 2 chỉ còn 10 giây (90 - 80)
    assert result["budget_exhausted"] and WARN_TIMEOUT in result["warnings"]


def test_ket_qua_la_json_duoc():
    json.dumps(run("07"))
