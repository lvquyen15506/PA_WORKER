"""Content-Disposition khi xem/tải tài liệu: tên tệp an toàn, không chèn được header/tham số."""

import re
import unicodedata
from urllib.parse import unquote

import pytest

from apps.documents.http import (
    MAX_NAME_LENGTH,
    ascii_filename,
    safe_content_disposition,
    safe_filename,
)

DISPOSITION = re.compile(
    r'^(?P<kind>inline|attachment); filename="(?P<ascii>[A-Za-z0-9._ -]*)"; '
    r"filename\*=UTF-8''(?P<utf8>[A-Za-z0-9%._~-]*)$"
)


def parse(header):
    match = DISPOSITION.fullmatch(header)
    assert match, f"header sai cấu trúc: {header!r}"
    return match["kind"], match["ascii"], unquote(match["utf8"])


def assert_one_safe_line(header):
    assert "\r" not in header and "\n" not in header
    assert all(unicodedata.category(c) not in ("Cc", "Cf") for c in header)
    assert header.count('"') == 2  # đúng một cặp ngoặc kép của filename
    assert header.count(";") == 2  # không có tham số thừa


def test_ten_tieng_viet_giu_nguyen_o_filename_sao_chep_ascii_o_filename():
    header = safe_content_disposition("attachment", "Hồ sơ Nguyễn Thị Ánh.pdf", ".pdf")
    kind, plain, utf8 = parse(header)
    assert kind == "attachment"
    assert utf8 == "Hồ sơ Nguyễn Thị Ánh.pdf"
    assert plain == "Ho so Nguyen Thi Anh.pdf"
    assert "%E1%BB%93" in header  # ô có dấu được mã hóa phần trăm theo RFC 5987
    assert_one_safe_line(header)


@pytest.mark.parametrize("disposition", ["inline", "attachment"])
def test_hai_kieu_disposition(disposition):
    assert parse(safe_content_disposition(disposition, "a.pdf"))[0] == disposition


def test_kieu_khac_bi_tu_choi():
    with pytest.raises(ValueError):
        safe_content_disposition("form-data", "a.pdf")


HOSTILE = [
    'a"b.pdf',
    'a"; filename="evil.exe',
    'a"\r\nSet-Cookie: x=1\r\n.pdf',
    "a\r\nContent-Type: text/html\r\n\r\n<script>.pdf",
    "a\nb.pdf",
    "a\x00b.pdf",
    "a\tb.pdf",
    "a;b.pdf",
    "a; filename*=UTF-8''evil.exe",
    "../../etc/passwd",
    "..\\..\\windows\\system32\\cmd.exe",
    "C:\\Users\\a\\b.pdf",
    "/etc/passwd",
    "a\u202egpj.exe",  # ký tự đảo chiều (bidi) giả đuôi
    "a\u200b.pdf",  # ký tự rộng bằng 0
    "a\\b.pdf",
    "%0d%0aSet-Cookie: x=1.pdf",
    "<script>alert(1)</script>.pdf",
    "a\u2028b.pdf",
    "\x7f\x1b[31m.pdf",
]


@pytest.mark.parametrize("name", HOSTILE)
def test_ten_doc_hai_khong_chen_duoc_header_hay_tham_so(name):
    header = safe_content_disposition("attachment", name, ".pdf")
    assert_one_safe_line(header)
    kind, plain, utf8 = parse(header)
    assert kind == "attachment"
    assert "/" not in utf8 and "\\" not in utf8 and '"' not in utf8 and ";" not in utf8
    assert not utf8.startswith(".")
    assert "evil.exe" not in header.replace("%2E", ".") or "evil.exe" in utf8.replace(" ", "")
    assert plain  # luôn có tên ASCII không rỗng
    assert utf8.lower().endswith(".pdf") or utf8.endswith(".exe")  # đuôi nằm ở cuối, không xen giữa


def test_chen_tham_so_khong_tao_duoc_filename_thu_hai():
    header = safe_content_disposition("attachment", 'a"; filename="evil.exe', ".pdf")
    assert header.count("filename=") == 1 and header.count("filename*=") == 1


def test_bo_duong_dan_chi_giu_ten_tep():
    assert safe_filename("../../etc/passwd", ".pdf") == "passwd.pdf"
    assert safe_filename("..\\..\\win\\a b.pdf", ".pdf") == "a b.pdf"
    assert safe_filename("/etc/hosts", "") == "hosts"


def test_ten_rong_hoac_chi_toan_ky_tu_la_dung_ten_mac_dinh_kem_duoi_that():
    for name in ["", "   ", "\r\n", '"""', ";;;", "\x00\x01", "...", "\u200b\u202e", None]:
        assert safe_filename(name, ".pdf") == "tai-lieu.pdf"
    header = safe_content_disposition("inline", "\r\n", ".jpg")
    assert parse(header)[1:] == ("tai-lieu.jpg", "tai-lieu.jpg")


def test_ten_chi_co_duoi_van_co_ten_mac_dinh():
    assert safe_filename(".pdf", ".pdf") == "tai-lieu.pdf"


def test_chuoi_ky_tu_la_ascii_thanh_gach_duoi():
    assert ascii_filename("日本語.pdf") == "___.pdf"
    assert ascii_filename("đường Đỗ.pdf") == "duong Do.pdf"
    assert ascii_filename("a*b?c.pdf") == "a_b_c.pdf"


def test_ten_rat_dai_bi_cat_nhung_giu_duoi():
    name = safe_filename("a" * 500 + ".pdf", ".pdf")
    assert len(name) == MAX_NAME_LENGTH and name.endswith("a.pdf")
    vn = safe_filename("Đ" * 500 + ".docx", ".docx")
    assert len(vn) <= MAX_NAME_LENGTH and vn.endswith(".docx")
    assert_one_safe_line(safe_content_disposition("attachment", "x" * 5000 + ".pdf", ".pdf"))


def test_ten_khong_co_duoi_lay_duoi_theo_dinh_dang_that():
    assert safe_filename("ảnh chân dung", ".jpg") == "ảnh chân dung.jpg"


def test_unicode_duoc_chuan_hoa_nfc():
    decomposed = unicodedata.normalize("NFD", "Nguyễn.pdf")
    assert safe_filename(decomposed, ".pdf") == unicodedata.normalize("NFC", "Nguyễn.pdf")


def test_giu_nguyen_ten_binh_thuong():
    assert safe_filename("CCCD mặt trước (1).jpg", ".jpg") == "CCCD mặt trước (1).jpg"
    header = safe_content_disposition("inline", "CCCD mặt trước (1).jpg", ".jpg")
    assert parse(header)[2] == "CCCD mặt trước (1).jpg"
