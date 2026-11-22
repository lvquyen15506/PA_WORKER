"""Kiểm tra tệp tải lên: định dạng thật theo chữ ký nội dung, đuôi khớp, tối đa 10 MB."""

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.documents.validators import (
    MAX_SIZE,
    MSG_EMPTY,
    MSG_EXT,
    MSG_FORMAT,
    MSG_TOO_BIG,
    detect_kind,
    validate_upload,
)
from tests import samples


def up(name, content):
    return SimpleUploadedFile(name, content)


@pytest.mark.parametrize("kind", ["JPG", "PNG", "PDF", "DOC", "DOCX"])
def test_nhan_5_dinh_dang_hop_le(kind):
    detected = validate_upload(samples.upload(kind))
    assert detected.kind == kind and detected.ext == samples.EXT[kind]
    assert detected.mime and "/" in detected.mime


@pytest.mark.parametrize("name", ["a.JPG", "a.Jpeg", "a.jpeg", "A B.jpg", "tên có dấu.jpg"])
def test_duoi_jpeg_khong_phan_biet_hoa_thuong(name):
    assert validate_upload(up(name, samples.JPG)).kind == "JPG"


def test_nhan_dien_theo_noi_dung_khong_theo_content_type():
    uploaded = SimpleUploadedFile("a.pdf", samples.EXE, content_type="application/pdf")
    with pytest.raises(ValidationError) as exc:
        validate_upload(uploaded)
    assert exc.value.messages == [MSG_FORMAT]


@pytest.mark.parametrize(
    "content",
    [
        samples.EXE,
        b"<html><script>alert(1)</script></html>",
        b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
        b"MZ" + b"\x00" * 32,
        b"\x7fELF" + b"\x00" * 32,
        b"#!/bin/sh\nrm -rf /\n",
        b"plain text",
        b"GIF89a" + b"x" * 32,  # GIF không nằm trong danh sách
        b"PK\x03\x04" + b"x" * 32,  # zip hỏng
    ],
)
@pytest.mark.parametrize("name", ["a.pdf", "a.jpg", "a.png", "a.docx", "a.doc"])
def test_tep_doc_hai_doi_duoi_bi_tu_choi(content, name):
    with pytest.raises(ValidationError) as exc:
        validate_upload(up(name, content))
    assert exc.value.messages == [MSG_FORMAT]


def test_zip_cua_office_khong_phai_word_khong_phai_docx():
    assert detect_kind(samples.XLSX) is None
    with pytest.raises(ValidationError):
        validate_upload(up("bang-tinh.docx", samples.XLSX))


def test_zip_thuong_dat_ten_docx_bi_tu_choi():
    assert detect_kind(samples._zip(["a.txt"])) is None


def test_ole_khong_phai_word_khong_phai_doc():
    assert detect_kind(samples.XLS) is None
    with pytest.raises(ValidationError):
        validate_upload(up("bang-tinh.doc", samples.XLS))


@pytest.mark.parametrize(
    ("kind", "wrong_name"),
    [
        ("PDF", "a.jpg"),
        ("PDF", "a.docx"),
        ("JPG", "a.png"),
        ("PNG", "a.jpg"),
        ("DOCX", "a.doc"),
        ("DOC", "a.docx"),
        ("JPG", "a"),  # không có đuôi
        ("JPG", "a."),
        ("PDF", "a.pdf.exe"),
        ("PDF", "a.exe"),
        ("PNG", ".png"),  # chỉ có đuôi, không có tên: splitext coi là tên ẩn, không có đuôi
    ],
)
def test_duoi_ten_khong_khop_noi_dung_bi_tu_choi(kind, wrong_name):
    with pytest.raises(ValidationError) as exc:
        validate_upload(up(wrong_name, samples.BY_KIND[kind]))
    assert exc.value.messages == [MSG_EXT]


def test_pdf_co_khoang_trang_truoc_chu_ky_bi_tu_choi():
    with pytest.raises(ValidationError):
        validate_upload(up("a.pdf", b"  \n" + samples.PDF))


def test_tep_rong_bi_tu_choi():
    with pytest.raises(ValidationError) as exc:
        validate_upload(up("a.pdf", b""))
    assert exc.value.messages == [MSG_EMPTY]


def test_dung_10_mb_duoc_nhan_hon_10_mb_bi_tu_choi():
    ok = samples.PDF + b"x" * (MAX_SIZE - len(samples.PDF))
    assert len(ok) == MAX_SIZE
    assert validate_upload(up("a.pdf", ok)).kind == "PDF"
    with pytest.raises(ValidationError) as exc:
        validate_upload(up("a.pdf", ok + b"x"))
    assert exc.value.messages == [MSG_TOO_BIG]


def test_gioi_han_kiem_tra_ca_khi_khai_bao_size_nho(monkeypatch):
    # Không tin thuộc tính size: nội dung thực đọc ra vẫn bị giới hạn.
    big = up("a.pdf", samples.PDF + b"x" * MAX_SIZE)
    monkeypatch.setattr(big, "size", 10, raising=False)
    with pytest.raises(ValidationError) as exc:
        validate_upload(big)
    assert exc.value.messages == [MSG_TOO_BIG]


def test_con_tro_tep_ve_dau_sau_khi_kiem_tra():
    uploaded = samples.upload("PDF")
    validate_upload(uploaded)
    assert uploaded.read() == samples.PDF
