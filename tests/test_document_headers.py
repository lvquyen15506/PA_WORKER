"""Header khi trả tệp: sandbox + nosniff khi xem trước, attachment khi tải, Content-Type thật."""

import pytest

from apps.core.choices import VerificationStatus as VS
from apps.documents.models import WorkerDocument
from tests import samples
from tests.factories import login_client, make_document, make_user, make_worker_in_status

pytestmark = pytest.mark.django_db

MIME = {
    "JPG": "image/jpeg",
    "PNG": "image/png",
    "PDF": "application/pdf",
    "DOC": "application/msword",
    "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def doc(kind, name=None):
    worker = make_worker_in_status(VS.DRAFT)
    document = make_document(
        worker, "CV", content=samples.BY_KIND[kind], name=name or f"mau{samples.EXT[kind]}"
    )
    WorkerDocument.objects.filter(pk=document.pk).update(mime_type=MIME[kind])
    return document


@pytest.mark.parametrize("kind", ["JPG", "PNG", "PDF"])
def test_xem_truoc_co_sandbox_nosniff_inline_va_content_type_that(kind):
    document = doc(kind)
    response = login_client(make_user("HR_STAFF")).get(f"/tai-lieu/{document.pk}/xem/")
    assert response.status_code == 200
    assert response["Content-Security-Policy"] == "sandbox"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Disposition"].startswith("inline;")
    assert response["Content-Type"] == MIME[kind]


@pytest.mark.parametrize("kind", ["JPG", "PNG", "PDF", "DOC", "DOCX"])
def test_tai_xuong_la_attachment_co_nosniff_va_content_type_that(kind):
    document = doc(kind)
    response = login_client(make_user("HR_STAFF")).get(f"/tai-lieu/{document.pk}/tai-xuong/")
    assert response.status_code == 200
    assert response["Content-Disposition"].startswith("attachment;")
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Type"] == MIME[kind]
    assert b"".join(response.streaming_content) == samples.BY_KIND[kind]


def test_content_type_lay_tu_dinh_dang_da_luu_khong_theo_duoi_ten_goc():
    document = doc("PDF", name="trông-như-ảnh.jpg")  # tên gốc có đuôi .jpg nhưng nội dung là PDF
    response = login_client(make_user("HR_STAFF")).get(f"/tai-lieu/{document.pk}/xem/")
    assert response["Content-Type"] == "application/pdf"


def test_ten_tep_co_dau_va_ky_tu_la_trong_header_that():
    document = doc("PDF", name='Hồ sơ "Ánh"; x\r\n.pdf')
    for path in ("xem", "tai-xuong"):
        response = login_client(make_user("HR_STAFF")).get(f"/tai-lieu/{document.pk}/{path}/")
        header = response["Content-Disposition"]
        assert "\r" not in header and "\n" not in header
        assert header.count("filename=") == 1 and "filename*=UTF-8''" in header
        assert "H%E1%BB%93%20s%C6%A1" in header  # "Hồ sơ" mã hóa phần trăm
        assert "Ho so" in header  # bản ASCII


def test_tep_html_gia_pdf_khong_vao_duoc_he_thong_nen_xem_khong_chay_duoc_script():
    # Nếu tệp lọt vào bằng cách nào đó, header vẫn chặn script: sandbox, nosniff, đúng Content-Type.
    worker = make_worker_in_status(VS.DRAFT)
    document = make_document(
        worker, "CV", content=b"<html><script>alert(1)</script></html>", name="x.pdf"
    )
    response = login_client(make_user("ADMIN")).get(f"/tai-lieu/{document.pk}/xem/")
    assert response["Content-Security-Policy"] == "sandbox"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Type"] == "application/pdf"  # không phải text/html
