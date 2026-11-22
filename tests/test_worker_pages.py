"""Trang thêm/sửa hồ sơ, chi tiết, kiểm tra trùng, số CCCD đầy đủ, đồng ý, lịch sử chi tiết.

Gồm kịch bản nghiệm thu 5 (nhập CCCD đã có → báo trùng, mở hồ sơ cũ) và 14 (sửa họ tên hồ sơ đã
xác minh → về Chờ duyệt, nhật ký có giá trị cũ và mới)."""

import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.core.choices import VerificationStatus as VS
from apps.documents.models import WorkerDocument
from apps.workers.models import DataConsent, IdentityDocument, StatusChange, Worker
from tests import samples
from tests.factories import (
    login_client,
    make_document,
    make_user,
    make_worker_full,
    make_worker_in_status,
)

pytestmark = pytest.mark.django_db
STAFF = ["ADMIN", "HR_MANAGER", "HR_STAFF"]
ALL = [*STAFF, "VIEWER"]


def body(response):
    return response.content.decode()


def new_form(**override):
    data = {
        "full_name": "Phạm Văn Mới",
        "phone": "0911222333",
        "date_of_birth": "05/03/1995",
        "gender": "MALE",
        "nationality": "Việt Nam",
        "id_doc_type": "CCCD_2021",
        "id_number": "999000111222",
        "contacts-TOTAL_FORMS": "1",
        "contacts-INITIAL_FORMS": "0",
        "contacts-0-full_name": "Người Thân Giả",
        "contacts-0-relationship": "Anh",
        "contacts-0-phone": "0988777666",
    }
    data.update(override)
    return data


# ===== Phân quyền các trang ================================================================
@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("/ho-so/", ALL),
        ("/ho-so/them/", STAFF),
        ("/ho-so/them/nhap-tay/", STAFF),
        ("/ho-so/{id}/", ALL),
        ("/ho-so/{id}/sua/", STAFF),
        ("/ho-so/{id}/dong-y/", STAFF),
        ("/ho-so/{id}/dong-y/mau-in/", STAFF),
        ("/ho-so/{id}/lich-su/chi-tiet/", ["ADMIN", "HR_MANAGER"]),
        ("/ho-so/{id}/tai-lieu/them/", STAFF),
        ("/duyet-ho-so/", ["ADMIN", "HR_MANAGER"]),
    ],
)
@pytest.mark.parametrize("role", ALL)
def test_get_theo_vai_tro(path, allowed, role):
    worker = make_worker_in_status(VS.DRAFT)
    response = login_client(make_user(role)).get(path.format(id=worker.pk))
    assert response.status_code == (200 if role in allowed else 403)


@pytest.mark.parametrize(
    "path",
    ["/ho-so/", "/ho-so/them/", "/ho-so/{id}/", "/ho-so/{id}/sua/", "/duyet-ho-so/"],
)
def test_chua_dang_nhap_chuyen_ve_trang_dang_nhap(path):
    worker = make_worker_in_status(VS.DRAFT)
    response = Client().get(path.format(id=worker.pk))
    assert response.status_code == 302 and response["Location"].startswith("/dang-nhap/")


def test_get_khong_thay_doi_du_lieu():
    worker = make_worker_in_status(VS.PENDING)
    snapshot = (Worker.objects.count(), AuditLog.objects.count(), StatusChange.objects.count())
    client = login_client(make_user("ADMIN"))
    for path in ("/ho-so/", f"/ho-so/{worker.pk}/", "/duyet-ho-so/", "/ho-so/them/"):
        client.get(path)
    for tab in ("ca-nhan", "tuyen-dung", "lam-viec", "tai-lieu", "lich-su"):
        client.get(f"/ho-so/{worker.pk}/?tab={tab}")
    assert (
        Worker.objects.count(),
        AuditLog.objects.count(),
        StatusChange.objects.count(),
    ) == snapshot


def test_ho_so_khong_ton_tai_la_404():
    client = login_client(make_user("ADMIN"))
    for path in ("/ho-so/99999/", "/ho-so/99999/sua/", "/ho-so/99999/dong-y/mau-in/"):
        assert client.get(path).status_code == 404


def test_trang_them_hien_ba_the_lien_ket():
    page = body(login_client(make_user("HR_STAFF")).get("/ho-so/them/"))
    for label, url in (
        ("Nhập tay", "/ho-so/them/nhap-tay/"),
        ("Từ CCCD và CV", "/nhap-cccd/"),
        ("Từ file Excel", "/ho-so/nhap-excel/"),
    ):
        assert label in page and f'href="{url}"' in page


# ===== Thêm hồ sơ ====================================================================
def test_nhap_nhap_chi_can_ho_ten_va_sdt():
    client = login_client(make_user("HR_STAFF"))
    response = client.post(
        "/ho-so/them/nhap-tay/",
        {
            "full_name": "Chỉ Có Tên",
            "phone": "0911222333",
            "contacts-TOTAL_FORMS": "1",
            "contacts-INITIAL_FORMS": "0",
        },
    )
    worker = Worker.objects.get(full_name="Chỉ Có Tên")
    assert response.status_code == 302 and response["Location"] == f"/ho-so/{worker.pk}/"
    assert worker.verification_status == VS.DRAFT and worker.worker_code.startswith("HS-")
    assert [str(m) for m in response.wsgi_request._messages] == ["Đã lưu hồ sơ ở trạng thái Nháp."]


def test_nhap_day_du_luu_giay_to_va_lien_he():
    client = login_client(make_user("HR_STAFF"))
    response = client.post("/ho-so/them/nhap-tay/", new_form())
    worker = Worker.objects.get(full_name="Phạm Văn Mới")
    assert response.status_code == 302
    assert IdentityDocument.objects.get(worker=worker).id_number_enc == "999000111222"
    assert worker.emergency_contacts.get().phone == "0988777666"
    assert worker.date_of_birth == datetime.date(1995, 3, 5)


def test_form_co_thuoc_tinh_htmx_kiem_tra_trung_khi_roi_o():
    html = body(login_client(make_user("HR_STAFF")).get("/ho-so/them/nhap-tay/"))
    assert html.count('hx-post="/ho-so/kiem-tra-trung/"') == 4  # họ tên, SĐT, ngày sinh, CCCD
    assert 'hx-trigger="blur changed"' in html and 'id="duplicate-check"' in html


def test_loi_hien_duoi_tung_o_bang_tieng_viet_va_khong_luu():
    response = login_client(make_user("HR_STAFF")).post(
        "/ho-so/them/nhap-tay/",
        new_form(full_name="", phone="123", id_number="12", date_of_birth="31/02/2000"),
    )
    page = body(response)
    assert response.status_code == 200 and not Worker.objects.exists()
    for message in (
        "Nhập họ và tên.",
        "Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0.",
        "Số CCCD phải gồm 12 chữ số.",
        "Nhập ngày đúng định dạng dd/mm/yyyy.",
        "Có ô chưa đúng.",
    ):
        assert message in page


def test_duoi_15_tuoi_bi_chan_tu_15_den_duoi_18_chi_canh_bao():
    today = timezone.localdate()
    client = login_client(make_user("HR_STAFF"))
    child = new_form(date_of_birth=datetime.date(today.year - 10, 6, 1).strftime("%d/%m/%Y"))
    response = client.post("/ho-so/them/nhap-tay/", child)
    assert response.status_code == 200 and "Không nhập hồ sơ người dưới 15 tuổi." in body(response)
    assert not Worker.objects.exists()
    teen = new_form(date_of_birth=datetime.date(today.year - 16, 1, 1).strftime("%d/%m/%Y"))
    response = client.post("/ho-so/them/nhap-tay/", teen)
    assert response.status_code == 302 and Worker.objects.count() == 1
    assert any("dưới 18 tuổi" in str(m) for m in response.wsgi_request._messages)


def test_kich_ban_5_nhap_cccd_da_co_bao_trung_mo_ho_so_cu_khong_tao_ho_so_moi():
    old = make_worker_full()
    identity = IdentityDocument.objects.get(worker=old)
    identity.id_number_enc = "999000111222"
    identity.save()
    client = login_client(make_user("HR_STAFF"))
    # 1. Rời ô số CCCD: mảnh HTMX báo trùng kèm nút Mở hồ sơ cũ.
    fragment = body(client.post("/ho-so/kiem-tra-trung/", {"id_number": "999000111222"}))
    assert "Số CCCD này đã có hồ sơ." in fragment
    assert f'href="/ho-so/{old.pk}/"' in fragment and "Mở hồ sơ cũ" in fragment
    # 2. Bấm Lưu: bị chặn, hiện lại nút Mở hồ sơ cũ, không tạo hồ sơ mới.
    before = Worker.objects.count()
    response = client.post("/ho-so/them/nhap-tay/", new_form())
    page = body(response)
    assert response.status_code == 200 and Worker.objects.count() == before
    assert old.worker_code in page and f'href="/ho-so/{old.pk}/"' in page and "Mở hồ sơ cũ" in page
    # 3. Mở hồ sơ cũ thấy đúng hồ sơ.
    assert old.full_name in body(client.get(f"/ho-so/{old.pk}/"))


@pytest.mark.parametrize("role", ["VIEWER"])
def test_viewer_khong_them_duoc(role):
    client = login_client(make_user(role))
    assert client.post("/ho-so/them/nhap-tay/", new_form()).status_code == 403
    assert not Worker.objects.exists()


def test_them_yeu_cau_csrf():
    logged = login_client(make_user("HR_STAFF"))
    client = Client(enforce_csrf_checks=True)
    client.cookies = logged.cookies
    assert client.post("/ho-so/them/nhap-tay/", new_form()).status_code == 403
    assert not Worker.objects.exists()


# ===== Mảnh HTMX kiểm tra trùng ================================================================
def test_kiem_tra_trung_canh_bao_sdt_va_ten_ngay_sinh_khong_chan():
    old = make_worker_full(
        full_name="Lê Thị Giả", phone="0911999888", date_of_birth=datetime.date(1991, 2, 3)
    )
    client = login_client(make_user("HR_STAFF"))
    fragment = body(client.post("/ho-so/kiem-tra-trung/", {"phone": "0911999888"}))
    assert old.worker_code in fragment and "số điện thoại" in fragment
    fragment = body(
        client.post(
            "/ho-so/kiem-tra-trung/",
            {"full_name": "le thi gia", "date_of_birth": "03/02/1991", "phone": "0900000001"},
        )
    )
    assert old.worker_code in fragment and "họ tên và ngày sinh" in fragment
    assert "Mở hồ sơ cũ" not in fragment  # chỉ cảnh báo, không phải lỗi trùng CCCD


def test_kiem_tra_trung_bo_qua_chinh_ho_so_dang_sua_va_khong_ghi_gi():
    worker = make_worker_full(phone="0911999777")
    client = login_client(make_user("HR_STAFF"))
    logs = AuditLog.objects.count()
    assert worker.worker_code in body(
        client.post("/ho-so/kiem-tra-trung/", {"phone": "0911999777"})
    )
    own = body(client.post(f"/ho-so/kiem-tra-trung/?sua={worker.pk}", {"phone": "0911999777"}))
    assert worker.worker_code not in own
    assert AuditLog.objects.count() == logs


def test_kiem_tra_trung_bao_loi_dinh_dang_khi_o_co_noi_dung():
    client = login_client(make_user("HR_STAFF"))
    assert "Số CCCD phải gồm 12 chữ số." in body(
        client.post("/ho-so/kiem-tra-trung/", {"id_number": "12"})
    )
    assert "Số CCCD" not in body(client.post("/ho-so/kiem-tra-trung/", {"id_number": ""}))


def test_kiem_tra_trung_chi_nhan_post():
    assert login_client(make_user("HR_STAFF")).get("/ho-so/kiem-tra-trung/").status_code == 405


# ===== Sửa hồ sơ + kịch bản 14 ====================================================================
def edit_form(worker, **override):
    identity = IdentityDocument.objects.get(worker=worker)
    contact = worker.emergency_contacts.first()  # dòng liên hệ đầu tiên
    data = {
        "full_name": worker.full_name,
        "phone": worker.phone,
        "date_of_birth": worker.date_of_birth.strftime("%d/%m/%Y"),
        "gender": worker.gender,
        "nationality": worker.nationality,
        "current_address": worker.current_address,
        "id_doc_type": identity.id_doc_type,
        "id_number": identity.id_number_enc,
        "contacts-TOTAL_FORMS": "2",
        "contacts-INITIAL_FORMS": "1",
        "contacts-0-id": contact.pk,
        "contacts-0-full_name": contact.full_name,
        "contacts-0-relationship": contact.relationship,
        "contacts-0-phone": contact.phone,
        "contacts-1-full_name": "",
        "contacts-1-relationship": "",
        "contacts-1-phone": "",
    }
    data.update(override)
    return data


def test_form_sua_hien_gia_tri_cu():
    worker = make_worker_in_status(VS.DRAFT)
    html = body(login_client(make_user("HR_STAFF")).get(f"/ho-so/{worker.pk}/sua/"))
    assert (
        worker.full_name in html
        and IdentityDocument.objects.get(worker=worker).id_number_enc in html
    )
    assert f"?sua={worker.pk}" in html  # kiểm tra trùng bỏ qua chính hồ sơ này
    assert 'value="05/05/1995"' not in html and 'value="20/05/1995"' in html  # ngày dd/mm/yyyy


def test_kich_ban_14_sua_ho_ten_ho_so_da_xac_minh_ve_cho_duyet_nhat_ky_co_gia_tri_cu_moi():
    worker = make_worker_in_status(VS.VERIFIED)
    old_name = worker.full_name
    hr = make_user("HR_STAFF")
    client = login_client(hr)
    response = client.post(
        f"/ho-so/{worker.pk}/sua/", edit_form(worker, full_name="Nguyễn Tên Đã Sửa")
    )
    assert response.status_code == 302
    worker = Worker.objects.get(pk=worker.pk)
    assert worker.verification_status == VS.PENDING and worker.full_name == "Nguyễn Tên Đã Sửa"
    assert any("Chờ duyệt" in str(m) for m in response.wsgi_request._messages)
    # Tab Lịch sử: dòng thời gian có lý do tự điền.
    timeline = body(client.get(f"/ho-so/{worker.pk}/?tab=lich-su"))
    assert "Sửa trường định danh: họ tên" in timeline and "Chờ duyệt" in timeline
    assert "Chi tiết thay đổi" not in timeline  # HR không xem chi tiết trước/sau (câu 11)
    # Quản lý xem chi tiết: giá trị cũ và mới.
    manager = login_client(make_user("HR_MANAGER"))
    page = body(manager.get(f"/ho-so/{worker.pk}/?tab=lich-su"))
    assert f"/ho-so/{worker.pk}/lich-su/chi-tiet/" in page
    detail = body(manager.get(f"/ho-so/{worker.pk}/lich-su/chi-tiet/"))
    assert old_name in detail and "Nguyễn Tên Đã Sửa" in detail and "full_name" in detail
    # Nhật ký chung không chứa họ tên.
    for entry in AuditLog.objects.filter(worker=worker):
        assert old_name not in f"{entry.changes} {entry.note} {entry.object_repr}"
        assert "Tên Đã Sửa" not in f"{entry.changes} {entry.note} {entry.object_repr}"


def test_chi_tiet_thay_doi_che_so_cccd_va_hien_da_an_danh_khi_het_gia_tri():
    worker = make_worker_in_status(VS.DRAFT)
    client = login_client(make_user("HR_STAFF"))
    client.post(f"/ho-so/{worker.pk}/sua/", edit_form(worker, id_number="999555666777"))
    manager = login_client(make_user("HR_MANAGER"))
    detail = body(manager.get(f"/ho-so/{worker.pk}/lich-su/chi-tiet/"))
    assert "999555666777" not in detail and "9995••••6777" in detail  # luôn dạng che
    # Sau ẩn danh hóa: giá trị đã bị xóa khỏi AuditPersonalValue, hiện "(đã ẩn danh)".
    from apps.audit.models import AuditPersonalValue

    AuditPersonalValue.objects.filter(worker=worker).delete()
    Worker.objects.filter(pk=worker.pk).update(anonymized_at=timezone.now())
    detail = body(manager.get(f"/ho-so/{worker.pk}/lich-su/chi-tiet/"))
    assert "(đã ẩn danh)" in detail


@pytest.mark.parametrize("status", [VS.PENDING, VS.REJECTED, VS.ARCHIVED])
@pytest.mark.parametrize("role", STAFF)
def test_ho_so_khoa_khong_sua_duoc_ca_get_lan_post(status, role):
    worker = make_worker_in_status(status)
    client = login_client(make_user(role))
    assert client.get(f"/ho-so/{worker.pk}/sua/").status_code == 403
    assert (
        client.post(f"/ho-so/{worker.pk}/sua/", edit_form(worker, phone="0900000009")).status_code
        == 403
    )
    assert Worker.objects.get(pk=worker.pk).phone == worker.phone


def test_sua_thanh_cong_thong_bao_va_khong_doi_thi_bao_khong_co_thay_doi():
    worker = make_worker_in_status(VS.DRAFT)
    client = login_client(make_user("HR_STAFF"))
    url = f"/ho-so/{worker.pk}/sua/"
    response = client.post(url, edit_form(worker, email="moi@example.com"), follow=True)
    assert "Đã lưu hồ sơ." in body(response)
    response = client.post(url, edit_form(worker, email="moi@example.com"), follow=True)
    assert "Không có thay đổi nào để lưu." in body(response)


def test_sua_trung_cccd_bao_loi_va_giu_nguyen():
    a, b = make_worker_in_status(VS.DRAFT), make_worker_in_status(VS.DRAFT)
    number_b = IdentityDocument.objects.get(worker=b).id_number_enc
    response = login_client(make_user("HR_STAFF")).post(
        f"/ho-so/{a.pk}/sua/", edit_form(a, id_number=number_b)
    )
    page = body(response)
    assert (
        response.status_code == 200 and b.worker_code in page and f'href="/ho-so/{b.pk}/"' in page
    )


def test_sua_them_va_xoa_nguoi_lien_he_qua_form():
    worker = make_worker_in_status(VS.DRAFT)
    client = login_client(make_user("HR_STAFF"))
    contact = worker.emergency_contacts.get()
    client.post(
        f"/ho-so/{worker.pk}/sua/",
        edit_form(
            worker,
            **{
                "contacts-1-full_name": "Thêm Mới",
                "contacts-1-relationship": "Chị",
                "contacts-1-phone": "0977666555",
            },
        ),
    )
    assert worker.emergency_contacts.count() == 2
    client.post(f"/ho-so/{worker.pk}/sua/", edit_form(worker, **{"contacts-0-delete": "on"}))
    assert not worker.emergency_contacts.filter(pk=contact.pk).exists()
    assert worker.emergency_contacts.count() == 1


def test_sua_ho_so_da_xac_minh_bat_buoc_du_truong_nen_hien_loi_neu_xoa_dia_chi():
    worker = make_worker_in_status(VS.VERIFIED)
    response = login_client(make_user("HR_STAFF")).post(
        f"/ho-so/{worker.pk}/sua/", edit_form(worker, current_address="")
    )
    assert response.status_code == 200 and "Nhập nơi ở hiện tại." in body(response)
    assert Worker.objects.get(pk=worker.pk).current_address


# ===== Chi tiết ===========================================================================
def test_tab_la_hoac_thieu_ve_tab_thong_tin_ca_nhan():
    worker = make_worker_in_status(VS.DRAFT)
    client = login_client(make_user("HR_STAFF"))
    for url in (f"/ho-so/{worker.pk}/", f"/ho-so/{worker.pk}/?tab=khong-co"):
        assert "Thông tin cơ bản" in body(client.get(url))


def test_nam_tab_hien_dung_noi_dung():
    worker = make_worker_in_status(VS.DRAFT)
    client = login_client(make_user("HR_STAFF"))
    expect = {
        "ca-nhan": "Liên hệ khẩn cấp",
        "tuyen-dung": "Lần ứng tuyển",
        "lam-viec": "Lịch sử điều chuyển",
        "tai-lieu": "Tài liệu hiện hành",
        "lich-su": "Dòng thời gian trạng thái",
    }
    for tab, text in expect.items():
        page = body(client.get(f"/ho-so/{worker.pk}/?tab={tab}"))
        assert text in page and 'aria-current="page">' in page


def test_tab_lam_viec_chua_co_thong_tin_hien_thong_bao():
    worker = make_worker_in_status(VS.DRAFT)
    page = body(login_client(make_user("HR_STAFF")).get(f"/ho-so/{worker.pk}/?tab=lam-viec"))
    assert "Chưa có thông tin làm việc." in page


def test_tab_lam_viec_hien_thong_tin_hop_dong_va_tep_hien_hanh():
    from apps.documents import services as document_services
    from apps.employment.models import Contract
    from tests.factories import make_employment

    worker = make_worker_in_status(VS.VERIFIED)
    make_employment(worker, "ACTIVE")
    v1 = make_document(worker, "CONTRACT")
    Contract.objects.create(
        worker=worker,
        contract_no="HD-2026-001",
        contract_type="FIXED_TERM",
        signed_date=datetime.date(2026, 1, 1),
        effective_date=datetime.date(2026, 1, 1),
        expiry_date=datetime.date(2027, 1, 1),
        document=v1,
        created_by=worker.created_by,
    )
    v2 = document_services.replace_document(
        make_user("HR_MANAGER"), v1, SimpleUploadedFile("hd.pdf", samples.PDF)
    )
    client = login_client(make_user("HR_STAFF"))
    page = body(client.get(f"/ho-so/{worker.pk}/?tab=lam-viec"))
    assert "HD-2026-001" in page and "Xác định thời hạn" in page and "Đang làm việc" in page
    assert f"/tai-lieu/{v2.pk}/tai-xuong/" in page  # bản hiện hành, không phải bản cũ
    assert f"/tai-lieu/{v1.pk}/tai-xuong/" not in page
    viewer = body(login_client(make_user("VIEWER")).get(f"/ho-so/{worker.pk}/?tab=lam-viec"))
    assert "HD-2026-001" in viewer and "/tai-lieu/" not in viewer


def test_tab_tai_lieu_danh_sach_con_thieu_va_phien_ban_cu():
    from apps.documents import services as document_services

    worker = make_worker_in_status(VS.DRAFT)
    v1 = make_document(worker, "CCCD_FRONT")
    document_services.replace_document(
        worker.created_by, v1, SimpleUploadedFile("a.pdf", samples.PDF)
    )
    page = body(login_client(make_user("HR_STAFF")).get(f"/ho-so/{worker.pk}/?tab=tai-lieu"))
    assert "Còn thiếu giấy tờ: CCCD mặt sau, Ảnh chân dung, CV hoặc Đơn xin việc." in page
    assert "Phiên bản cũ" in page and "Tải tài liệu lên" in page
    assert f"/tai-lieu/{v1.pk}/xem/" in page  # bản cũ vẫn xem được trong lịch sử


def test_tab_tai_lieu_hr_khi_da_xac_minh_co_them_nhung_khong_thay_the():
    worker = make_worker_in_status(VS.VERIFIED)
    doc = make_document(worker, "CCCD_FRONT")
    hr = body(login_client(make_user("HR_STAFF")).get(f"/ho-so/{worker.pk}/?tab=tai-lieu"))
    assert "Tải tài liệu lên" in hr and f"/tai-lieu/{doc.pk}/thay-the/" not in hr
    assert f"/tai-lieu/{doc.pk}/xac-minh/" not in hr  # chỉ Quản lý, Admin đổi xác minh (câu 34)
    manager = body(login_client(make_user("HR_MANAGER")).get(f"/ho-so/{worker.pk}/?tab=tai-lieu"))
    assert f"/tai-lieu/{doc.pk}/thay-the/" in manager and f"/tai-lieu/{doc.pk}/xac-minh/" in manager


def test_ho_so_da_an_danh_hien_da_an_danh_va_an_nut():
    worker = make_worker_in_status(VS.ARCHIVED)
    Worker.objects.filter(pk=worker.pk).update(
        anonymized_at=timezone.now(), full_name="(Đã ẩn danh)", phone="", date_of_birth=None
    )
    client = login_client(make_user("ADMIN"))
    page = body(client.get(f"/ho-so/{worker.pk}/"))
    assert "(đã ẩn danh)" in page and "Mở lại hồ sơ" not in page
    assert client.get(f"/ho-so/{worker.pk}/dong-y/mau-in/").status_code == 404
    assert client.post(f"/ho-so/{worker.pk}/cccd-day-du/").status_code == 404


# ===== Số CCCD đầy đủ ==========================================================================
@pytest.mark.parametrize("role", STAFF)
def test_hien_so_day_du_ghi_nhat_ky_moi_lan_bam(role):
    worker = make_worker_in_status(VS.DRAFT)
    number = IdentityDocument.objects.get(worker=worker).id_number_enc
    user = make_user(role)
    client = login_client(user)
    for count in (1, 2):
        response = client.post(f"/ho-so/{worker.pk}/cccd-day-du/")
        assert response.status_code == 200 and number in body(response)
        assert response["Cache-Control"] == "no-store"
        logs = AuditLog.objects.filter(worker=worker, action="VIEW_FULL_ID", user=user)
        assert logs.count() == count
    entry = logs.first()
    assert number not in f"{entry.changes} {entry.note} {entry.object_repr}"


def test_hien_so_day_du_viewer_403_get_405_khong_co_giay_to_404():
    worker = make_worker_in_status(VS.DRAFT)
    assert (
        login_client(make_user("VIEWER")).post(f"/ho-so/{worker.pk}/cccd-day-du/").status_code
        == 403
    )
    staff = login_client(make_user("HR_STAFF"))
    assert staff.get(f"/ho-so/{worker.pk}/cccd-day-du/").status_code == 405
    no_identity = Worker.objects.create(
        worker_code="HS-X-1",
        full_name="Không Giấy Tờ",
        phone="0911000001",
        created_by=worker.created_by,
    )
    assert staff.post(f"/ho-so/{no_identity.pk}/cccd-day-du/").status_code == 404
    assert not AuditLog.objects.filter(action="VIEW_FULL_ID").exists()


def test_nut_hien_so_day_du_chi_co_voi_nhan_vien():
    worker = make_worker_in_status(VS.DRAFT)
    assert "Hiện số đầy đủ" in body(login_client(make_user("HR_STAFF")).get(f"/ho-so/{worker.pk}/"))
    assert "Hiện số đầy đủ" not in body(
        login_client(make_user("VIEWER")).get(f"/ho-so/{worker.pk}/")
    )


# ===== Đồng ý xử lý dữ liệu ============================================================
def consent_data(**override):
    data = {
        "consented": "1",
        "consent_date": timezone.localdate().strftime("%d/%m/%Y"),
        "method": "ELECTRONIC",
    }
    data.update(override)
    return data


def test_ghi_nhan_dong_y_dien_tu():
    worker = make_worker_in_status(VS.DRAFT)
    client = login_client(make_user("HR_STAFF"))
    response = client.post(f"/ho-so/{worker.pk}/dong-y/", consent_data(consented="0"))
    assert response.status_code == 302
    latest = DataConsent.objects.filter(worker=worker).first()
    assert latest.consented is False and latest.method == "ELECTRONIC"
    assert "Không đồng ý" in body(client.get(f"/ho-so/{worker.pk}/"))


def test_ky_giay_bat_buoc_tep_bien_ban_va_luu_thanh_tai_lieu_dong_y():
    worker = make_worker_in_status(VS.DRAFT)
    client = login_client(make_user("HR_STAFF"))
    url = f"/ho-so/{worker.pk}/dong-y/"
    response = client.post(url, consent_data(method="PAPER"))
    assert response.status_code == 200 and "Ký giấy: tải lên tệp biên bản đã ký." in body(response)
    before = DataConsent.objects.filter(worker=worker).count()
    response = client.post(
        url, {**consent_data(method="PAPER"), "file": SimpleUploadedFile("bb.pdf", samples.PDF)}
    )
    assert response.status_code == 302
    consent = DataConsent.objects.filter(worker=worker).first()
    assert DataConsent.objects.filter(worker=worker).count() == before + 1
    assert consent.method == "PAPER" and consent.document.document_type.system_code == "CONSENT"
    assert AuditLog.objects.filter(worker=worker, action="UPLOAD_FILE").exists()


def test_ky_giay_tep_sai_dinh_dang_bao_loi_khong_de_lai_dong_nao():
    worker = make_worker_in_status(VS.DRAFT)
    before = (DataConsent.objects.count(), WorkerDocument.objects.count())
    response = login_client(make_user("HR_STAFF")).post(
        f"/ho-so/{worker.pk}/dong-y/",
        {**consent_data(method="PAPER"), "file": SimpleUploadedFile("bb.pdf", samples.EXE)},
    )
    assert response.status_code == 200 and "Chỉ nhận tệp JPG, PNG, PDF, DOC hoặc DOCX." in body(
        response
    )
    assert (DataConsent.objects.count(), WorkerDocument.objects.count()) == before


def test_dong_y_ngay_sai_hoac_tuong_lai_bao_loi():
    worker = make_worker_in_status(VS.DRAFT)
    client = login_client(make_user("HR_STAFF"))
    page = body(client.post(f"/ho-so/{worker.pk}/dong-y/", consent_data(consent_date="2099-01-01")))
    assert "Nhập ngày đúng định dạng dd/mm/yyyy." in page
    future = (timezone.localdate() + datetime.timedelta(days=2)).strftime("%d/%m/%Y")
    page = body(client.post(f"/ho-so/{worker.pk}/dong-y/", consent_data(consent_date=future)))
    assert "Ngày đồng ý không được ở tương lai." in page


@pytest.mark.parametrize("status", [VS.PENDING, VS.REJECTED, VS.ARCHIVED])
def test_dong_y_bi_khoa_theo_trang_thai(status):
    worker = make_worker_in_status(status)
    client = login_client(make_user("ADMIN"))
    assert client.get(f"/ho-so/{worker.pk}/dong-y/").status_code == 403
    assert client.post(f"/ho-so/{worker.pk}/dong-y/", consent_data()).status_code == 403


def test_in_mau_dong_y_dien_san_khong_co_so_cccd_va_ghi_nhat_ky_print():
    worker = make_worker_in_status(VS.DRAFT)
    number = IdentityDocument.objects.get(worker=worker).id_number_enc
    user = make_user("HR_STAFF")
    response = login_client(user).get(f"/ho-so/{worker.pk}/dong-y/mau-in/")
    page = body(response)
    assert worker.worker_code in page and worker.full_name in page and worker.phone in page
    assert "20/05/1995" in page and "VĂN BẢN ĐỒNG Ý XỬ LÝ DỮ LIỆU CÁ NHÂN" in page
    assert number not in page  # không in số CCCD lên văn bản đồng ý
    entry = AuditLog.objects.get(action="PRINT", worker=worker)
    assert entry.user == user and entry.note == "In mẫu đồng ý"
    assert worker.full_name not in f"{entry.note} {entry.object_repr}"


def test_in_mau_khong_co_so_cccd_day_du():
    worker = make_worker_in_status(VS.DRAFT)
    number = IdentityDocument.objects.get(worker=worker).id_number_enc
    page = body(login_client(make_user("HR_STAFF")).get(f"/ho-so/{worker.pk}/dong-y/mau-in/"))
    assert number not in page
