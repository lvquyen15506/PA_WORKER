"""View tài liệu: quyền theo vai trò và trạng thái, nhật ký, CSRF (kịch bản nghiệm thu 2)."""

import pytest
from django.test import Client

from apps.audit.models import AuditLog
from apps.core.choices import VerificationStatus as VS
from apps.core.models import DocumentType
from apps.documents.models import WorkerDocument
from apps.workers.models import Worker
from tests import samples
from tests.factories import login_client, make_document, make_user, make_worker_in_status

pytestmark = pytest.mark.django_db
STAFF = ["ADMIN", "HR_MANAGER", "HR_STAFF"]


def doc_of(worker, code="CCCD_FRONT", **kw):
    return make_document(worker, code, **kw)


def file_post(url, client, kind="PDF", **data):
    return client.post(url, {"file": samples.upload(kind), **data})


# ===== Xem / tải =============================================================================
@pytest.mark.parametrize("url_name", ["xem", "tai-xuong"])
@pytest.mark.parametrize("role", STAFF)
def test_nhan_vien_xem_va_tai_duoc(role, url_name):
    worker = make_worker_in_status(VS.DRAFT)
    doc = doc_of(worker)
    response = login_client(make_user(role)).get(f"/tai-lieu/{doc.pk}/{url_name}/")
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"%PDF-1.4 test"


@pytest.mark.parametrize("url_name", ["xem", "tai-xuong", "lich-su"])
@pytest.mark.parametrize("status", list(VS))
def test_viewer_goi_thang_duong_dan_bi_403_o_moi_trang_thai(status, url_name):
    # Kịch bản nghiệm thu 2: Viewer gọi trực tiếp URL tải/xem tệp thì bị từ chối.
    worker = make_worker_in_status(status)
    doc = doc_of(worker)
    before = AuditLog.objects.count()
    response = login_client(make_user("VIEWER")).get(f"/tai-lieu/{doc.pk}/{url_name}/")
    assert response.status_code == 403
    assert b"%PDF" not in response.content
    assert AuditLog.objects.count() == before  # bị từ chối thì không có lượt xem/tải nào được ghi


@pytest.mark.parametrize("path", ["xem", "tai-xuong", "thay-the", "lich-su"])
def test_chua_dang_nhap_chuyen_ve_trang_dang_nhap(path):
    doc = doc_of(make_worker_in_status(VS.DRAFT))
    response = Client().get(f"/tai-lieu/{doc.pk}/{path}/")
    assert response.status_code == 302 and response["Location"].startswith("/dang-nhap/")


def test_tai_lieu_khong_ton_tai_la_404():
    assert login_client(make_user("ADMIN")).get("/tai-lieu/99999/xem/").status_code == 404


def test_ho_so_da_an_danh_tep_da_xoa_thi_404():
    worker = make_worker_in_status(VS.DRAFT)
    doc = doc_of(worker)
    WorkerDocument.objects.filter(pk=doc.pk).update(stored_file=None, original_name="")
    client = login_client(make_user("ADMIN"))
    assert client.get(f"/tai-lieu/{doc.pk}/xem/").status_code == 404
    assert client.get(f"/tai-lieu/{doc.pk}/tai-xuong/").status_code == 404


def test_xem_va_tai_ghi_nhat_ky_dung_hanh_dong_khong_co_ten_tep():
    worker = make_worker_in_status(VS.DRAFT)
    doc = doc_of(worker, name="TênGốcRiêng.pdf")
    user = make_user("HR_STAFF")
    client = login_client(user)
    client.get(f"/tai-lieu/{doc.pk}/xem/")
    client.get(f"/tai-lieu/{doc.pk}/tai-xuong/")
    view = AuditLog.objects.get(action="VIEW_FILE")
    download = AuditLog.objects.get(action="DOWNLOAD_FILE")
    for entry in (view, download):
        assert entry.user == user and entry.worker_id == worker.pk
        assert entry.object_repr == str(doc)
        assert "TênGốcRiêng" not in f"{entry.object_repr} {entry.note} {entry.changes}"


def test_doc_docx_khong_xem_truoc_chuyen_sang_tai_xuong():
    worker = make_worker_in_status(VS.DRAFT)
    doc = make_document(worker, "CV", content=samples.DOCX, name="cv.docx")
    from apps.documents.models import WorkerDocument as W

    W.objects.filter(pk=doc.pk).update(
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    client = login_client(make_user("HR_STAFF"))
    response = client.get(f"/tai-lieu/{doc.pk}/xem/")
    assert response.status_code == 302 and response["Location"] == f"/tai-lieu/{doc.pk}/tai-xuong/"
    assert not AuditLog.objects.filter(action="VIEW_FILE").exists()  # chưa xem gì
    assert client.get(response["Location"]).status_code == 200
    assert AuditLog.objects.filter(action="DOWNLOAD_FILE").count() == 1


def test_ban_cu_van_xem_duoc_trong_lich_su():
    worker = make_worker_in_status(VS.DRAFT)
    v1 = doc_of(worker)
    from apps.documents import services

    services.replace_document(worker.created_by, v1, samples.upload("JPG"))
    client = login_client(make_user("HR_MANAGER"))
    assert client.get(f"/tai-lieu/{v1.pk}/xem/").status_code == 200


@pytest.mark.parametrize("url_name", ["xem", "tai-xuong"])
def test_xem_tai_chi_nhan_get(url_name):
    doc = doc_of(make_worker_in_status(VS.DRAFT))
    client = login_client(make_user("ADMIN"))
    assert client.post(f"/tai-lieu/{doc.pk}/{url_name}/").status_code == 405


# ===== Tải lên ===============================================================================
@pytest.mark.parametrize(
    ("status", "role", "allowed"),
    [
        (s, r, (s in (VS.DRAFT, VS.NEEDS_INFO, VS.VERIFIED)) and r != "VIEWER")
        for s in VS
        for r in [*STAFF, "VIEWER"]
    ],
)
def test_ma_tran_trang_tai_len(status, role, allowed):
    worker = make_worker_in_status(status)
    client = login_client(make_user(role))
    url = f"/ho-so/{worker.pk}/tai-lieu/them/"
    assert (client.get(url).status_code == 200) is allowed
    response = file_post(url, client, document_type=DocumentType.objects.get(system_code="CV").pk)
    if allowed:
        assert response.status_code == 302 and response["Location"].endswith("?tab=tai-lieu")
        assert WorkerDocument.objects.filter(worker=worker).count() == 1
    else:
        assert response.status_code == 403
        assert not WorkerDocument.objects.filter(worker=worker).exists()


def test_tai_len_thanh_cong_co_thong_bao_va_ghi_nhat_ky():
    worker = make_worker_in_status(VS.DRAFT)
    user = make_user("HR_STAFF")
    client = login_client(user)
    cv = DocumentType.objects.get(system_code="CV")
    response = file_post(f"/ho-so/{worker.pk}/tai-lieu/them/", client, document_type=cv.pk)
    assert response.status_code == 302
    messages = [str(m) for m in response.wsgi_request._messages]
    assert messages == ["Đã tải tài liệu lên."]
    assert AuditLog.objects.filter(action="UPLOAD_FILE", user=user).count() == 1


def test_tai_len_tep_sai_hien_loi_tieng_viet_duoi_o_va_khong_luu():
    worker = make_worker_in_status(VS.DRAFT)
    client = login_client(make_user("HR_STAFF"))
    cv = DocumentType.objects.get(system_code="CV")
    from django.core.files.uploadedfile import SimpleUploadedFile

    response = client.post(
        f"/ho-so/{worker.pk}/tai-lieu/them/",
        {"document_type": cv.pk, "file": SimpleUploadedFile("a.pdf", samples.EXE)},
    )
    assert response.status_code == 200
    assert "Chỉ nhận tệp JPG, PNG, PDF, DOC hoặc DOCX." in response.content.decode()
    assert not WorkerDocument.objects.exists()


def test_tai_len_thieu_loai_hoac_thieu_tep_hien_loi():
    worker = make_worker_in_status(VS.DRAFT)
    client = login_client(make_user("HR_STAFF"))
    url = f"/ho-so/{worker.pk}/tai-lieu/them/"
    html = client.post(url, {}).content.decode()
    assert "Chọn loại tài liệu." in html and "Chọn tệp cần tải lên." in html


def test_ho_so_khong_ton_tai_la_404():
    assert login_client(make_user("ADMIN")).get("/ho-so/99999/tai-lieu/them/").status_code == 404


# ===== Thay thế ==============================================================================
@pytest.mark.parametrize(
    ("status", "role", "allowed"),
    [
        (VS.DRAFT, "HR_STAFF", True),
        (VS.NEEDS_INFO, "HR_STAFF", True),
        (VS.VERIFIED, "HR_STAFF", False),
        (VS.VERIFIED, "HR_MANAGER", True),
        (VS.PENDING, "ADMIN", False),
        (VS.REJECTED, "ADMIN", False),
        (VS.ARCHIVED, "ADMIN", False),
        (VS.DRAFT, "VIEWER", False),
    ],
)
def test_ma_tran_trang_thay_the(status, role, allowed):
    worker = make_worker_in_status(status)
    doc = doc_of(worker)
    client = login_client(make_user(role))
    url = f"/tai-lieu/{doc.pk}/thay-the/"
    assert (client.get(url).status_code == 200) is allowed
    response = file_post(url, client, "JPG")
    assert (response.status_code == 302) is allowed
    if not allowed:
        assert response.status_code == 403
    assert WorkerDocument.objects.filter(worker=worker).count() == (2 if allowed else 1)


def test_thay_the_ban_cu_bao_loi_tren_trang():
    worker = make_worker_in_status(VS.DRAFT)
    v1 = doc_of(worker)
    client = login_client(make_user("HR_STAFF"))
    file_post(f"/tai-lieu/{v1.pk}/thay-the/", client)
    response = file_post(f"/tai-lieu/{v1.pk}/thay-the/", client)  # v1 không còn hiện hành
    assert response.status_code == 200
    assert "Chỉ thay thế được bản hiện hành" in response.content.decode()


# ===== Xác minh ==============================================================================
@pytest.mark.parametrize("role", ["ADMIN", "HR_MANAGER"])
def test_ql_admin_doi_trang_thai_xac_minh(role):
    worker = make_worker_in_status(VS.PENDING)
    doc = doc_of(worker)
    response = login_client(make_user(role)).post(
        f"/tai-lieu/{doc.pk}/xac-minh/", {"status": "MATCHED", "note": "Đã đối chiếu"}
    )
    assert response.status_code == 302
    doc.refresh_from_db()
    assert doc.verification_status == "MATCHED"


@pytest.mark.parametrize("role", ["HR_STAFF", "VIEWER"])
def test_hr_va_viewer_khong_doi_duoc_trang_thai_xac_minh(role):
    doc = doc_of(make_worker_in_status(VS.DRAFT))
    response = login_client(make_user(role)).post(
        f"/tai-lieu/{doc.pk}/xac-minh/", {"status": "MATCHED"}
    )
    assert response.status_code == 403
    doc.refresh_from_db()
    assert doc.verification_status == "UNVERIFIED"


@pytest.mark.parametrize("status", [VS.REJECTED, VS.ARCHIVED])
def test_khong_ai_doi_xac_minh_khi_bi_tu_choi_hoac_luu_tru(status):
    doc = doc_of(make_worker_in_status(status))
    response = login_client(make_user("ADMIN")).post(
        f"/tai-lieu/{doc.pk}/xac-minh/", {"status": "MATCHED"}
    )
    assert response.status_code == 403


def test_xac_minh_gia_tri_la_khong_doi_gi():
    doc = doc_of(make_worker_in_status(VS.DRAFT))
    client = login_client(make_user("ADMIN"))
    response = client.post(f"/tai-lieu/{doc.pk}/xac-minh/", {"status": "HACK"})
    assert response.status_code == 302
    assert [str(m) for m in response.wsgi_request._messages] == ["Chọn trạng thái xác minh hợp lệ."]
    doc.refresh_from_db()
    assert doc.verification_status == "UNVERIFIED"


def test_xac_minh_chi_nhan_post():
    doc = doc_of(make_worker_in_status(VS.DRAFT))
    assert login_client(make_user("ADMIN")).get(f"/tai-lieu/{doc.pk}/xac-minh/").status_code == 405


# ===== Lịch sử phiên bản (mảnh HTMX) ===========================================================
@pytest.mark.parametrize("role", STAFF)
def test_lich_su_liet_ke_cac_phien_ban(role):
    from apps.documents import services

    worker = make_worker_in_status(VS.DRAFT)
    v1 = doc_of(worker)
    v2 = services.replace_document(worker.created_by, v1, samples.upload("JPG"))
    html = login_client(make_user(role)).get(f"/tai-lieu/{v1.pk}/lich-su/").content.decode()
    assert "v1" in html and "v2 (hiện hành)" in html
    assert f"/tai-lieu/{v1.pk}/xem/" in html and f"/tai-lieu/{v2.pk}/tai-xuong/" in html


# ===== CSRF ==================================================================================
def test_cac_thao_tac_ghi_yeu_cau_csrf():
    worker = make_worker_in_status(VS.DRAFT)
    doc = doc_of(worker)
    logged_in = login_client(make_user("ADMIN"))  # đăng nhập bằng client thường (có CSRF tự động)
    client = Client(enforce_csrf_checks=True)
    client.cookies = logged_in.cookies  # cùng phiên, nhưng KHÔNG gửi mã CSRF
    cv = DocumentType.objects.get(system_code="CV")
    for url, data in [
        (f"/ho-so/{worker.pk}/tai-lieu/them/", {"document_type": cv.pk, "file": samples.upload()}),
        (f"/tai-lieu/{doc.pk}/thay-the/", {"file": samples.upload()}),
        (f"/tai-lieu/{doc.pk}/xac-minh/", {"status": "MATCHED"}),
    ]:
        assert client.post(url, data).status_code == 403
    assert WorkerDocument.objects.filter(worker=worker).count() == 1
    assert Worker.objects.get(pk=worker.pk).verification_status == VS.DRAFT
