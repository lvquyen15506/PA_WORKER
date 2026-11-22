"""Trích văn bản CV và gợi ý (Phase 5 bước 3)."""

import io
import subprocess
from pathlib import Path

import pytest
from fpdf import FPDF
from PIL import Image

from apps.intake import cv
from apps.intake.budget import Budget
from apps.intake.cv import CvError, extract_text, find_hints
from apps.intake.imaging import MSG_TOO_LARGE, ImageRejected
from apps.intake.ocr import Word

CV_DIR = Path(__file__).parent / "fixtures" / "cv"


def read(name):
    return (CV_DIR / name).read_bytes()


def counting_engine(calls, size_log=None):
    def engine(image, timeout):
        calls.append(timeout)
        if size_log is not None:
            size_log.append(image.size)
        return [Word("Chữ", 90.0, (1, 1, 1)), Word("giả", 90.0, (1, 1, 2))]

    return engine


def scan_pdf(pages, size=(800, 1000)):
    images = [Image.new("RGB", size, "white") for _ in range(pages)]
    buffer = io.BytesIO()
    images[0].save(buffer, format="PDF", save_all=True, append_images=images[1:])
    return buffer.getvalue()


# ----- từng định dạng -----


def check_cv_text(text):
    assert "0999000111" in text and "mau.thu@example.com" in text
    assert "Học vấn" in text and "Kinh nghiệm làm việc" in text
    assert "Vận hành máy may công nghiệp" in text


def test_docx():
    result = extract_text(read("cv-mau.docx"), "DOCX")
    check_cv_text(result.text)
    assert not result.ocr_used and result.warnings == []


def test_pdf_co_lop_chu():
    result = extract_text(read("cv-mau.pdf"), "PDF")
    check_cv_text(result.text)
    assert not result.ocr_used


def test_doc_bang_antiword():
    result = extract_text(read("cv-mau.doc"), "DOC")
    check_cv_text(result.text)
    assert not result.ocr_used


def test_anh_cv_bang_ocr_tesseract():
    result = extract_text(read("cv-mau.png"), "PNG")
    assert result.ocr_used
    assert "0999000111" in result.text and "Học vấn" in result.text


def test_pdf_scan_khong_co_chu_thi_ocr():
    buffer = io.BytesIO()
    Image.open(CV_DIR / "cv-mau.png").convert("RGB").save(buffer, format="PDF")
    result = extract_text(buffer.getvalue(), "PDF")
    assert result.ocr_used
    assert "0999000111" in result.text and "Kinh nghiệm" in result.text


# ----- giới hạn trang, độ phân giải, điểm ảnh (quyết định 6) -----


def test_pdf_scan_5_trang_chi_ocr_3_trang():
    calls = []
    result = extract_text(scan_pdf(5), "PDF", engine=counting_engine(calls))
    assert len(calls) == 3
    assert cv.WARN_PARTIAL in result.warnings


def test_pdf_scan_3_trang_khong_canh_bao_cat_bot():
    calls = []
    result = extract_text(scan_pdf(3), "PDF", engine=counting_engine(calls))
    assert len(calls) == 3 and cv.WARN_PARTIAL not in result.warnings


def test_render_dpi_khong_vuot_300_va_ha_xuong_khi_trang_qua_lon(settings):
    assert cv._render_dpi(595, 842) == 300  # A4
    dpi = cv._render_dpi(5000, 5000)
    assert dpi < 300
    assert (5000 / 72 * dpi) ** 2 <= settings.MAX_IMAGE_PIXELS


def test_pdf_trang_kho_lon_duoc_ve_o_dpi_da_ha(settings):
    settings.MAX_IMAGE_PIXELS = 4_000_000
    pdf = FPDF(unit="pt", format=(3000, 3000))
    pdf.add_page()  # trang trống, không lớp chữ -> đi đường OCR
    sizes, calls = [], []
    extract_text(bytes(pdf.output()), "PDF", engine=counting_engine(calls, sizes))
    assert len(sizes) == 1
    width, height = sizes[0]
    assert width * height <= settings.MAX_IMAGE_PIXELS
    assert width < 3000 / 72 * 300  # thấp hơn 300 dpi


def test_anh_cv_khong_lo_bi_tu_choi(settings):
    settings.MAX_IMAGE_PIXELS = 100 * 100
    buffer = io.BytesIO()
    Image.new("RGB", (200, 200), "white").save(buffer, format="PNG")
    with pytest.raises(ImageRejected) as exc:
        extract_text(buffer.getvalue(), "PNG")
    assert str(exc.value) == MSG_TOO_LARGE


# ----- lỗi và thời gian -----


def test_kieu_tep_la_bi_tu_choi():
    with pytest.raises(CvError):
        extract_text(b"x", "XLSX")


def test_tep_hong_bao_loi_tieng_viet():
    with pytest.raises(CvError, match="PDF"):
        extract_text(b"%PDF-1.4 hong", "PDF")
    with pytest.raises(CvError, match="docx"):
        extract_text(b"PK\x03\x04 hong", "DOCX")
    with pytest.raises(CvError, match="doc"):
        extract_text(b"\xd0\xcf\x11\xe0 hong", "DOC")


def test_antiword_qua_gio(monkeypatch):
    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="antiword", timeout=1)

    monkeypatch.setattr(cv.subprocess, "run", boom)
    budget = Budget()
    result = extract_text(read("cv-mau.doc"), "DOC", budget=budget)
    assert result.text == "" and budget.exhausted
    assert cv.WARN_TIMEOUT in result.warnings


def test_het_ngan_sach_thi_khong_chay_antiword(monkeypatch):
    monkeypatch.setattr(cv.subprocess, "run", lambda *a, **k: pytest.fail("không được gọi"))
    result = extract_text(read("cv-mau.doc"), "DOC", budget=Budget(total=0))
    assert result.text == "" and cv.WARN_TIMEOUT in result.warnings


def test_pdf_scan_het_ngan_sach_thi_bo_trang_con_lai():
    calls = []
    result = extract_text(scan_pdf(3), "PDF", budget=Budget(total=0), engine=counting_engine(calls))
    assert calls == [] and cv.WARN_TIMEOUT in result.warnings


def test_cv_rong_co_canh_bao():
    pdf = FPDF()
    pdf.add_page()
    result = extract_text(bytes(pdf.output()), "PDF", engine=lambda image, timeout: [])
    assert result.text == "" and cv.MSG_NO_TEXT in result.warnings


# ----- gợi ý -----


def test_goi_y_tu_cv_mau():
    hints = find_hints(extract_text(read("cv-mau.docx"), "DOCX").text)
    assert hints["phones"] == ["0999000111"]
    assert hints["emails"] == ["mau.thu@example.com"]
    assert hints["month_years"] == ["03/2016", "06/2020"]
    assert [h["key"] for h in hints["headings"]] == [
        "education",
        "experience",
        "skills",
        "certificate",
    ]
    assert hints["sections"]["education"] == "Trung học phổ thông Thử Nghiệm, 2010 - 2013"
    assert hints["sections"]["skills"].startswith("Vận hành máy may")


@pytest.mark.parametrize(
    "raw",
    ["0999 000 111", "0999.000.111", "+84 999000111", "0999-000-111", "SĐT: 0999000111."],
)
def test_nhan_so_dien_thoai_nhieu_kieu_viet(raw):
    assert find_hints(raw)["phones"] == ["0999000111"]


def test_khong_nhan_so_khong_phai_dien_thoai():
    for raw in ("12345", "Mã số 1234567890123", "0999 00"):
        assert find_hints(raw)["phones"] == []


def test_ngay_thang_hop_le_moi_duoc_nhan():
    hints = find_hints("Sinh ngày 05/01/1995, nghỉ 31/13/2000, vào 7-3-2019")
    assert hints["dates"] == ["05/01/1995", "07/03/2019"]


def test_khong_tu_tao_thong_tin_khong_co_trong_cv():
    hints = find_hints("Tôi thích bóng đá và nấu ăn.")
    assert hints == {
        "phones": [],
        "emails": [],
        "dates": [],
        "month_years": [],
        "headings": [],
        "sections": {},
    }


def test_de_muc_khong_dau_va_viet_hoa():
    hints = find_hints("KINH NGHIỆM LÀM VIỆC:\nCông ty A\nKY NANG\nHàn")
    assert hints["sections"] == {"experience": "Công ty A", "skills": "Hàn"}


def test_dong_dai_khong_phai_de_muc():
    text = "Học vấn của tôi gồm nhiều giai đoạn khác nhau trong đời"
    assert find_hints(text)["headings"] == []
