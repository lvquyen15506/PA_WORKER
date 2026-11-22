"""Màn hình đối chiếu và lưu hồ sơ từ phiên nhận diện (Phase 5 bước 5; kịch bản 3, 4, 5)."""

import datetime
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.audit.models import AuditLog, AuditPersonalValue
from apps.core.models import EducationLevel
from apps.intake import services
from apps.intake.models import IntakeSession
from apps.recruitment.models import Certificate, Education, WorkExperience
from apps.workers import services as worker_services
from apps.workers.models import IdentityFieldSource, Worker
from tests.factories import login_client, make_user, make_worker
from tests.intake_helpers import (
    CARDS,
    PHONE,
    card,
    card_bytes,
    card_upload,
    cv_upload,
    low_fields,
    make_session,
    review_data,
)
from tests.test_intake_views import intake_files

pytestmark = pytest.mark.django_db


def post_review(client, session, **kwargs):
    return client.post(f"/nhap-cccd/{session.pk}/", review_data(session, **kwargs))


def truth_data(card_id):
    """Giá trị đúng của thẻ ở dạng HR gõ vào form (ngày dd/mm/yyyy)."""
    c = card(card_id)
    data = {}
    for name in c["printed"]:
        value = c["values"][name]
        if name in ("date_of_birth", "issue_date", "expiry_date"):
            value = datetime.date.fromisoformat(value).strftime("%d/%m/%Y")
        data[name] = value
    return data


def sources(worker):
    return {s.field_name: s for s in IdentityFieldSource.objects.filter(worker=worker)}


# ----- kịch bản 3: thẻ có QR -----


def test_luu_ho_so_tu_the_co_qr(django_capture_on_commit_callbacks, settings):
    hr = make_user("HR_STAFF")
    client = login_client(hr)
    session = make_session(hr, "01")
    truth = card("01")["values"]
    with django_capture_on_commit_callbacks(execute=True):
        response = post_review(client, session)
    worker = Worker.objects.get()
    assert response.status_code == 302 and response["Location"] == f"/ho-so/{worker.pk}/"
    assert worker.verification_status == "DRAFT" and worker.created_by == hr
    assert worker.worker_code and worker.phone == PHONE
    assert worker.full_name == truth["full_name"] and worker.gender == truth["gender"]
    assert worker.date_of_birth.isoformat() == truth["date_of_birth"]
    identity = worker.identity
    assert identity.id_number_enc == truth["id_number"] and identity.id_doc_type == "CCCD_2021"
    assert identity.hometown == truth["hometown"]
    assert identity.issue_date.isoformat() == truth["issue_date"]

    found = sources(worker)
    for name in card("01")["qr_fields"]:
        key = name if name in ("full_name", "date_of_birth", "gender") else f"identity.{name}"
        assert found[key].source == "QR" and not found[key].edited_by_user, name
    assert found["nationality"].source == "OCR" and found["nationality"].confidence >= 80
    assert found["identity.hometown"].source == "OCR"
    for row in found.values():
        assert row.confirmed_by == hr and row.confirmed_at is not None

    docs = {d.document_type.system_code for d in worker.documents.all()}
    assert docs == {"CCCD_FRONT", "CCCD_BACK"}
    assert all(d.stored_file.storage.exists(d.stored_file.name) for d in worker.documents.all())
    assert not IntakeSession.objects.exists() and intake_files(settings) == []  # phiên đã đóng

    actions = list(AuditLog.objects.order_by("id").values_list("action", flat=True))
    for expected in ("INTAKE_CREATE", "INTAKE_SAVE", "CREATE"):
        assert expected in actions
    save = AuditLog.objects.get(action="INTAKE_SAVE")
    assert save.worker == worker and worker.worker_code in save.note
    assert truth["id_number"] not in save.note and truth["full_name"] not in save.note
    for entry in AuditLog.objects.all():
        assert truth["id_number"] not in str(entry.changes)


def test_the_qr_khong_can_tich_vi_khong_co_truong_vang():
    hr = make_user("HR_STAFF")
    session = make_session(hr, "02")
    assert low_fields(session) == []
    response = post_review(login_client(hr), session, tick=False)
    assert response.status_code == 302 and Worker.objects.count() == 1


@pytest.mark.parametrize("card_id", ["01", "03", "07", "09"])
def test_nhieu_the_qr_luu_dung_100_phan_tram_truong_qr(card_id):
    hr = make_user("HR_STAFF")
    session = make_session(hr, card_id)
    assert post_review(login_client(hr), session).status_code == 302
    worker = Worker.objects.get()
    truth = card(card_id)["values"]
    assert worker.identity.id_number_enc == truth["id_number"]
    assert worker.full_name == truth["full_name"]
    assert worker.date_of_birth.isoformat() == truth["date_of_birth"]
    assert worker.gender == truth["gender"]
    assert worker.identity.id_doc_type == card(card_id)["doc_type"]


def test_sua_truong_may_doc_thanh_nhap_tay():
    hr = make_user("HR_STAFF")
    session = make_session(hr, "01")
    post_review(login_client(hr), session, full_name="TÊN ĐÃ SỬA TAY")
    worker = Worker.objects.get()
    assert worker.full_name == "TÊN ĐÃ SỬA TAY"
    found = sources(worker)
    assert found["full_name"].source == "MANUAL" and found["full_name"].edited_by_user
    assert (
        found["identity.id_number"].source == "QR"
        and not found["identity.id_number"].edited_by_user
    )


def test_sua_ho_so_sau_do_doi_nguon_thanh_nhap_tay():
    hr = make_user("HR_STAFF")
    session = make_session(hr, "01")
    post_review(login_client(hr), session)
    worker = Worker.objects.get()
    worker_services.update_worker(hr, worker, {"full_name": "TÊN SỬA SAU"})
    source = IdentityFieldSource.objects.get(worker=worker, field_name="full_name")
    assert source.source == "MANUAL" and source.edited_by_user
    assert (
        IdentityFieldSource.objects.get(worker=worker, field_name="identity.id_number").source
        == "QR"
    )
    worker_services.update_worker(hr, worker, {"id_number": "999000000099"})
    changed = IdentityFieldSource.objects.get(worker=worker, field_name="identity.id_number")
    assert changed.source == "MANUAL" and changed.edited_by_user


# ----- kịch bản 4: thẻ không QR, trường tô vàng -----


def test_the_khong_qr_ocr_dien_duoc_va_luu():
    hr = make_user("HR_STAFF")
    session = make_session(hr, "12")
    assert session.get_result()["recognition"]["qr"]["raw"] is None
    assert post_review(login_client(hr), session).status_code == 302
    worker = Worker.objects.get()
    truth = card("12")["values"]
    assert worker.identity.id_number_enc == truth["id_number"]
    assert worker.identity.id_doc_type == "CCCD_2016"
    found = sources(worker)
    assert (
        found["identity.id_number"].source == "OCR" and found["identity.id_number"].confidence >= 80
    )


def test_chua_tich_da_kiem_tra_thi_khong_luu_duoc(settings):
    hr = make_user("HR_STAFF")
    client = login_client(hr)
    session = make_session(hr, "15")
    low = low_fields(session)
    assert len(low) >= 5
    data = truth_data("15")
    response = post_review(client, session, tick=False, **data)
    html = response.content.decode()
    assert response.status_code == 200 and "Cần tích Đã kiểm tra cho các trường tô vàng" in html
    assert Worker.objects.count() == 0 and IntakeSession.objects.filter(pk=session.pk).exists()
    assert len(intake_files(settings)) == 2  # ảnh phiên còn nguyên

    # chỉ tích một phần vẫn bị chặn (máy chủ kiểm tra lại, không tin giao diện)
    partial = {f"{low[0]}__checked": "on"}
    response = post_review(client, session, tick=False, **data, **partial)
    assert response.status_code == 200 and Worker.objects.count() == 0

    # tích đủ thì lưu được
    assert post_review(client, session, **data).status_code == 302
    worker = Worker.objects.get()
    assert worker.identity.id_number_enc == card("15")["values"]["id_number"]


def test_truong_doc_khong_duoc_hr_go_la_nhap_tay():
    hr = make_user("HR_STAFF")
    session = make_session(hr, "15")
    post_review(login_client(hr), session, **truth_data("15"))
    for row in IdentityFieldSource.objects.all():
        if row.source == "OCR":
            assert not row.edited_by_user
        else:
            assert row.source == "MANUAL"
    assert IdentityFieldSource.objects.filter(source="MANUAL").exists()


# ----- kịch bản 5: trùng CCCD -----


def existing_worker(user, card_id="01"):
    return worker_services.create_worker(
        user,
        {
            "full_name": "Hồ Sơ Cũ Giả",
            "phone": "0911111111",
            "id_number": card(card_id)["values"]["id_number"],
        },
    )


def test_trung_cccd_bao_ngay_khi_mo_man_hinh_doi_chieu():
    hr = make_user("HR_STAFF")
    old = existing_worker(hr)
    session = make_session(hr, "01")
    html = login_client(hr).get(f"/nhap-cccd/{session.pk}/").content.decode()
    assert "Số CCCD này đã có hồ sơ" in html
    assert f"/nhap-cccd/{session.pk}/mo-ho-so-cu/{old.pk}/" in html and "Mở hồ sơ cũ" in html


def test_trung_cccd_chan_luu_va_khong_tao_ho_so_moi(settings):
    hr = make_user("HR_STAFF")
    old = existing_worker(hr)
    session = make_session(hr, "01")
    response = post_review(login_client(hr), session)
    html = response.content.decode()
    assert response.status_code == 200 and "Số CCCD này đã có hồ sơ" in html
    assert f"/mo-ho-so-cu/{old.pk}/" in html
    assert Worker.objects.count() == 1 and IntakeSession.objects.filter(pk=session.pk).exists()
    assert len(intake_files(settings)) == 2


def test_kiem_tra_trung_bang_htmx_khi_roi_o_so_cccd():
    hr = make_user("HR_STAFF")
    old = existing_worker(hr)
    session = make_session(hr, "02")
    client = login_client(hr)
    url = f"/nhap-cccd/{session.pk}/kiem-tra-trung/"
    html = client.post(
        url, {"id_number": card("01")["values"]["id_number"], "phone": PHONE}
    ).content.decode()
    assert "Mở hồ sơ cũ" in html and f"/mo-ho-so-cu/{old.pk}/" in html
    ok = client.post(
        url, {"id_number": card("02")["values"]["id_number"], "phone": PHONE}
    ).content.decode()
    assert "Mở hồ sơ cũ" not in ok


def test_mo_ho_so_cu_dong_phien_khong_tao_ho_so_moi(django_capture_on_commit_callbacks, settings):
    hr = make_user("HR_STAFF")
    old = existing_worker(hr)
    session = make_session(hr, "01")
    pk = session.pk
    response = login_client(hr).post(f"/nhap-cccd/{pk}/mo-ho-so-cu/{old.pk}/")
    assert response.status_code == 302 and response["Location"] == f"/ho-so/{old.pk}/"
    assert Worker.objects.count() == 1 and not IntakeSession.objects.filter(pk=pk).exists()
    assert intake_files(settings) == []
    entry = AuditLog.objects.get(action="INTAKE_CANCEL")
    assert entry.worker == old and old.worker_code in entry.note
    assert not old.documents.exists()  # ảnh của phiên không được lưu vào hồ sơ cũ


def test_khong_mo_duoc_ho_so_cu_da_an_danh():
    hr = make_user("HR_STAFF")
    old = existing_worker(hr)
    Worker.objects.filter(pk=old.pk).update(anonymized_at=timezone.now())
    session = make_session(hr, "02")
    response = login_client(hr).post(f"/nhap-cccd/{session.pk}/mo-ho-so-cu/{old.pk}/")
    assert response.status_code == 404 and IntakeSession.objects.filter(pk=session.pk).exists()


def test_thieu_loai_tai_lieu_he_thong_bao_loi_tieng_viet_va_giu_phien():
    from apps.core.models import DocumentType

    hr = make_user("HR_STAFF")
    session = make_session(hr, "02")
    DocumentType.objects.filter(system_code="CCCD_FRONT").delete()
    response = post_review(login_client(hr), session)
    assert (
        response.status_code == 200 and "Thiếu loại tài liệu hệ thống" in response.content.decode()
    )
    assert Worker.objects.count() == 0 and IntakeSession.objects.filter(pk=session.pk).exists()


def test_trung_sdt_hoac_ten_ngay_sinh_chi_canh_bao_khong_chan():
    hr = make_user("HR_STAFF")
    make_worker(hr, phone=PHONE, full_name="Nguyễn Văn Giả")
    session = make_session(hr, cv=cv_upload())
    client = login_client(hr)
    check = client.post(
        f"/nhap-cccd/{session.pk}/kiem-tra-trung/", {"full_name": "Người Khác", "phone": PHONE}
    )
    assert "Có thể trùng hồ sơ" in check.content.decode()
    response = client.post(
        f"/nhap-cccd/{session.pk}/", review_data(session, full_name="Người Khác"), follow=True
    )
    assert Worker.objects.count() == 2
    assert "Có thể trùng hồ sơ" in response.content.decode()
    assert response.redirect_chain


# ----- chặn dữ liệu sai -----


def test_duoi_15_tuoi_bi_chan_phien_con_nguyen():
    hr = make_user("HR_STAFF")
    session = make_session(hr, "12")
    young = (timezone.localdate() - datetime.timedelta(days=365 * 10)).strftime("%d/%m/%Y")
    response = post_review(login_client(hr), session, date_of_birth=young)
    assert response.status_code == 200 and "dưới 15 tuổi" in response.content.decode()
    assert Worker.objects.count() == 0 and IntakeSession.objects.filter(pk=session.pk).exists()


def test_thieu_so_dien_thoai_hoac_ho_ten_bi_chan():
    hr = make_user("HR_STAFF")
    session = make_session(hr, "12")
    client = login_client(hr)
    assert post_review(client, session, phone="").status_code == 200
    assert post_review(client, session, full_name="").status_code == 200
    assert Worker.objects.count() == 0


def test_phien_cua_nguoi_khac_khong_luu_duoc():
    owner = make_user("HR_STAFF")
    session = make_session(owner, "12")
    other = login_client(make_user("HR_STAFF"))
    assert other.post(f"/nhap-cccd/{session.pk}/", review_data(session)).status_code == 404
    assert Worker.objects.count() == 0


def test_bam_luu_hai_lan_khong_tao_hai_ho_so(django_capture_on_commit_callbacks):
    hr = make_user("HR_STAFF")
    session = make_session(hr, "02")
    client = login_client(hr)
    data = review_data(session)
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post(f"/nhap-cccd/{session.pk}/", data).status_code == 302
    assert client.post(f"/nhap-cccd/{session.pk}/", data).status_code == 404
    assert Worker.objects.count() == 1


def test_loi_khi_luu_thi_hoan_tac_het_va_don_tep_tai_lieu(monkeypatch, settings):
    hr = make_user("HR_STAFF")
    session = make_session(hr, "02")
    from apps.documents import services as document_services

    calls = []
    original = document_services.upload_document

    def second_fails(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("lỗi giả lập")
        return original(*args, **kwargs)

    monkeypatch.setattr(document_services, "upload_document", second_fails)
    client = login_client(hr)
    client.raise_request_exception = False
    assert post_review(client, session).status_code == 500
    assert Worker.objects.count() == 0 and IntakeSession.objects.filter(pk=session.pk).exists()
    docs_root = settings.PRIVATE_MEDIA_ROOT
    leftover = [p for p in docs_root.rglob("*") if p.is_file() and "intake" not in p.parts]
    assert leftover == []  # tệp tài liệu đã lưu dở bị dọn
    assert services.get_session_for(hr, session.pk) is not None


# ----- CV: học vấn, kinh nghiệm, chứng chỉ, kỹ năng -----


def cv_rows():
    level = EducationLevel.objects.get(name="THPT")
    return {
        "full_name": "Nguyễn Văn Mẫu",
        "skills": "Vận hành máy may công nghiệp",
        "edu-0-education_level": str(level.pk),
        "edu-0-school_name": "THPT Thử Nghiệm",
        "edu-0-major": "Phổ thông",
        "edu-0-start_year": "2010",
        "edu-0-end_year": "2013",
        "exp-0-company_name": "Công ty Giả Lập",
        "exp-0-job_title": "Công nhân may",
        "exp-0-start_date": "01/03/2016",
        "exp-0-end_date": "30/06/2020",
        "cert-0-name": "Chứng chỉ an toàn lao động",
        "cert-0-issuer": "Trung tâm Mẫu",
        "cert-0-issue_date": "01/01/2019",
    }


def test_luu_ho_so_tu_cv_tao_dong_hoc_van_kinh_nghiem_chung_chi():
    hr = make_user("HR_STAFF")
    session = make_session(hr, cv=cv_upload())
    response = post_review(login_client(hr), session, **cv_rows())
    assert response.status_code == 302
    worker = Worker.objects.get()
    assert worker.skills == "Vận hành máy may công nghiệp"
    edu, exp, cert = (
        Education.objects.get(),
        WorkExperience.objects.get(),
        Certificate.objects.get(),
    )
    assert edu.worker == exp.worker == cert.worker == worker
    assert edu.school_name == "THPT Thử Nghiệm" and edu.education_level.name == "THPT"
    assert (edu.start_year, edu.end_year) == (2010, 2013)
    assert exp.company_name == "Công ty Giả Lập" and exp.start_date == datetime.date(2016, 3, 1)
    assert cert.name == "Chứng chỉ an toàn lao động" and cert.issue_date == datetime.date(
        2019, 1, 1
    )
    assert {d.document_type.system_code for d in worker.documents.all()} == {"CV"}
    assert not IdentityFieldSource.objects.exists()  # không có ảnh thẻ nên không có nguồn máy đọc
    # nhật ký: giá trị cá nhân nằm ở AuditPersonalValue, không nằm rõ trong changes
    log = AuditLog.objects.get(action="CREATE", object_type="recruitment.Education")
    assert log.changes[f"education[{edu.pk}].school_name"] == "(xem giá trị chi tiết)"
    assert "THPT Thử Nghiệm" not in str(log.changes) and log.worker == worker
    assert AuditPersonalValue.objects.filter(field_name=f"education[{edu.pk}].school_name").exists()
    assert AuditLog.objects.filter(object_type="recruitment.WorkExperience").count() == 1
    assert AuditLog.objects.filter(object_type="recruitment.Certificate").count() == 1


def test_dong_cv_chua_day_du_bi_bao_loi_va_khong_luu():
    hr = make_user("HR_STAFF")
    session = make_session(hr, cv=cv_upload())
    client = login_client(hr)
    response = post_review(
        client, session, full_name="Nguyễn Văn Mẫu", **{"edu-0-school_name": "Trường"}
    )
    html = response.content.decode()
    assert response.status_code == 200 and "Chọn trình độ học vấn." in html
    response = post_review(client, session, full_name="A", **{"exp-0-job_title": "Thợ"})
    assert "Nhập tên công ty." in response.content.decode()
    response = post_review(client, session, full_name="A", **{"cert-0-issuer": "X"})
    assert "Nhập tên chứng chỉ." in response.content.decode()
    assert Worker.objects.count() == 0 and not Education.objects.exists()


def test_dong_cv_trong_thi_bo_qua():
    hr = make_user("HR_STAFF")
    session = make_session(hr, cv=cv_upload())
    post_review(login_client(hr), session, full_name="Nguyễn Văn Mẫu")
    assert not Education.objects.exists() and not WorkExperience.objects.exists()
    assert not Certificate.objects.exists()


# ----- xóa EXIF khi lưu ảnh thành tài liệu (quyết định 7) -----


def jpeg_with_exif(card_id, orientation):
    image = Image.open(CARDS / card(card_id)["files"]["front"]).convert("RGB")
    exif = Image.Exif()
    exif[0x0112] = orientation
    exif[0x010F] = "MayAnhGia"
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2] = "N", (10.0, 0.0, 0.0)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif, quality=95)
    return buffer.getvalue(), image.size


@pytest.mark.parametrize("orientation, rotated", [(1, False), (6, True)])
def test_anh_luu_vao_ho_so_khong_con_exif_gps_va_da_xoay(orientation, rotated):
    hr = make_user("HR_STAFF")
    data, size = jpeg_with_exif("12", orientation)
    assert Image.open(io.BytesIO(data)).getexif().get_ifd(0x8825)  # dữ liệu thử có GPS
    session = services.create_session(
        hr, front=SimpleUploadedFile("anh.jpg", data, content_type="image/jpeg")
    )
    assert post_review(login_client(hr), session, full_name="Nguyễn Văn Giả").status_code == 302
    document = Worker.objects.get().documents.get()
    with document.stored_file.open("rb") as handle:
        stored = Image.open(io.BytesIO(handle.read()))
        stored.load()
    assert document.mime_type == "image/jpeg" and document.document_type.system_code == "CCCD_FRONT"
    assert len(stored.getexif()) == 0 and not stored.getexif().get_ifd(0x8825)
    assert "exif" not in stored.info and "icc_profile" not in stored.info
    assert stored.size == ((size[1], size[0]) if rotated else size)
    assert document.size_bytes == document.stored_file.size


def test_anh_png_luu_vao_ho_so_khong_con_metadata_van_ban():
    from PIL.PngImagePlugin import PngInfo

    hr = make_user("HR_STAFF")
    info = PngInfo()
    info.add_text("Author", "NguoiGia")
    buffer = io.BytesIO()
    Image.open(CARDS / card("12")["files"]["front"]).save(buffer, format="PNG", pnginfo=info)
    session = services.create_session(hr, front=SimpleUploadedFile("anh.png", buffer.getvalue()))
    post_review(login_client(hr), session, full_name="Nguyễn Văn Giả")
    document = Worker.objects.get().documents.get()
    with document.stored_file.open("rb") as handle:
        stored = Image.open(io.BytesIO(handle.read()))
    assert "Author" not in stored.info and not stored.text


def test_tep_goc_cua_phien_khong_doi_cho_toi_khi_luu():
    hr = make_user("HR_STAFF")
    session = make_session(hr, "12")
    with session.front_image.open("rb") as handle:
        assert handle.read() == card_bytes("12")
    assert card_upload("12").size  # tiện cho kiểm tra tệp nguồn có thật
