"""Tiện ích Excel dùng chung (apps/core/excel.py): safe_cell, is_xlsx, check_zip_safe, xuất tệp."""

import datetime
import io
import zipfile
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from apps.core import excel
from apps.core.excel import ExcelFileError, check_zip_safe, is_xlsx, safe_cell
from tests.samples import DOCX, PDF, XLS, XLSX


# --- safe_cell -----------------------------------------------------------------------------
@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r", "\n"])
def test_safe_cell_them_dau_nhay_khi_chu_bat_dau_bang_ky_tu_cong_thuc(prefix):
    assert safe_cell(f"{prefix}SUM(A1)") == f"'{prefix}SUM(A1)"


@pytest.mark.parametrize(
    "text", ["Nguyễn Văn A", "0900000001", "a=b", " =x", "", "kỹ năng - máy may"]
)
def test_safe_cell_chu_binh_thuong_giu_nguyen(text):
    assert safe_cell(text) == text


def test_safe_cell_kieu_khac():
    assert safe_cell(None) is None
    assert safe_cell(True) is True
    assert safe_cell(12) == 12 and safe_cell(Decimal("1.5")) == Decimal("1.5")
    assert safe_cell(-5) == -5  # số âm là số, không phải chữ
    assert safe_cell(datetime.date(2026, 3, 5)) == "05/03/2026"
    assert safe_cell(datetime.datetime(2026, 3, 5, 14, 7)) == "05/03/2026 14:07"


def test_safe_cell_bo_ky_tu_dieu_khien_khong_hop_le_cua_xlsx():
    assert safe_cell("ab\x00c\x07d") == "abcd"


def test_write_rows_moi_o_deu_qua_safe_cell_va_doc_lai_la_chu_khong_phai_cong_thuc():
    book = excel.new_workbook("Danh sách / thử: *?")
    excel.write_rows(book.active, ["=Cot1", "Cột 2"], [["=1+1", "@x"], ["-y", "ok"]])
    assert not any(ch in book.active.title for ch in "\\/*?:[]")  # ký tự cấm trong tên sheet
    loaded = load_workbook(io.BytesIO(_save(book)), data_only=False)
    cells = [c for row in loaded.active.iter_rows() for c in row]
    assert all(c.data_type != "f" for c in cells)  # không có công thức thật
    assert [c.value for c in loaded.active[2]] == ["'=1+1", "'@x"]
    assert loaded.active["A1"].value == "'=Cot1"


def _save(book):
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def test_xlsx_response_header_an_toan():
    response = excel.xlsx_response(excel.new_workbook("A"), "Danh sách hồ sơ.xlsx")
    assert response["Content-Type"] == excel.XLSX_MIME
    assert response["Content-Disposition"].startswith("attachment;")
    assert "filename*=UTF-8''" in response["Content-Disposition"]
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Cache-Control"] == "no-store"
    assert is_xlsx(response.content)


# --- is_xlsx -------------------------------------------------------------------------------
def test_is_xlsx_nhan_dung_dinh_dang_that():
    assert is_xlsx(XLSX)
    assert is_xlsx(_save(excel.new_workbook("A")))
    for data in (DOCX, XLS, PDF, b"", b"PK\x03\x04khong-phai-zip"):
        assert not is_xlsx(data)


# --- check_zip_safe ------------------------------------------------------------------------
def _zip_bytes(entries, compression=zipfile.ZIP_DEFLATED):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_check_zip_safe_chap_nhan_xlsx_binh_thuong():
    check_zip_safe(_save(excel.new_workbook("A")))
    check_zip_safe(XLSX)


def test_check_zip_safe_tu_choi_zip_hong_hoac_khong_phai_zip():
    for data in (b"khong phai zip", b"PK\x03\x04" + b"\x00" * 30, b""):
        with pytest.raises(ExcelFileError) as exc:
            check_zip_safe(data)
        assert exc.value.message == "Tệp Excel không hợp lệ."


def test_check_zip_safe_zip_bomb_ti_le_nen_qua_100_lan():
    bomb = _zip_bytes({"xl/workbook.xml": b"\x00" * (20 * 1024 * 1024)})  # ~20 KB nén
    assert len(bomb) < 1024 * 1024
    with pytest.raises(ExcelFileError) as exc:
        check_zip_safe(bomb)
    assert exc.value.message == "Tệp Excel không hợp lệ."


def test_check_zip_safe_tong_giai_nen_qua_100_mb(monkeypatch):
    # Giữ test nhanh: hạ ngưỡng thay vì tạo 100 MB thật; tỉ lệ nén bằng 1 (lưu không nén).
    monkeypatch.setattr(excel, "MAX_UNZIPPED_BYTES", 50_000)
    data = _zip_bytes({"a": b"x" * 40_000, "b": b"y" * 40_000}, compression=zipfile.ZIP_STORED)
    with pytest.raises(ExcelFileError):
        check_zip_safe(data)


def test_check_zip_safe_header_khai_man_kich_thuoc_van_bi_chan_khi_dem_thuc(monkeypatch):
    monkeypatch.setattr(excel, "MAX_UNZIPPED_BYTES", 50_000)
    monkeypatch.setattr(excel, "RATIO_CHECK_MIN_BYTES", 10**12)  # tắt kiểm tra tỉ lệ
    data = _zip_bytes({"a": b"x" * 60_000}, compression=zipfile.ZIP_STORED)
    # Sửa file_size trong header (trung tâm thư mục và header cục bộ) xuống còn 100 byte.
    forged = bytearray(data)
    real = (60_000).to_bytes(4, "little")
    fake = (100).to_bytes(4, "little")
    start = 0
    while (index := forged.find(real, start)) != -1:
        forged[index : index + 4] = fake
        start = index + 4
    infos = zipfile.ZipFile(io.BytesIO(bytes(forged))).infolist()
    assert infos[0].file_size == 100  # tổng theo header qua ngưỡng, nhưng nội dung thật thì không
    with pytest.raises(ExcelFileError):
        check_zip_safe(bytes(forged))


def test_check_zip_safe_muc_nho_nen_tot_khong_bi_chan_oan():
    sheet = b"<c/>" * 100_000  # 400 KB, nén rất tốt nhưng dưới ngưỡng 1 MiB
    check_zip_safe(_zip_bytes({"xl/worksheets/sheet1.xml": sheet}))
