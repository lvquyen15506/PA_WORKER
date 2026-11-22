"""Ẩn danh hóa (câu 2, 30, 38; models.md mục 4.6–4.7): giữ gì, xóa gì, ai được làm."""

import datetime
from pathlib import Path

import pytest
from django.conf import settings

from apps.audit.models import AuditLog, AuditPersonalValue
from apps.audit.services import log
from apps.core.choices import AnonymizationKind as Kind
from apps.core.choices import VerificationStatus as VS
from apps.core.models import EducationLevel
from apps.documents.models import WorkerDocument
from apps.employment.models import Contract, Employment
from apps.recruitment.models import Application, Certificate, Education, WorkExperience
from apps.workers import retention, rules
from apps.workers.models import (
    AnonymizationItem,
    AnonymizationRecord,
    DataConsent,
    EmergencyContact,
    IdentityDocument,
    StatusChange,
    Worker,
)
from apps.workers.retention import (
    RetentionError,
    RetentionForbidden,
    anonymize,
    anonymize_on_request,
)
from apps.workers.workflow import TransitionError, transition
from tests.factories import (
    at,
    freeze_time,
    make_application,
    make_document,
    make_employment,
    make_user,
    make_worker_full,
    make_worker_in_status,
)

pytestmark = pytest.mark.django_db
D = datetime.date
MARK = "ZQXMARK"
FAR_FUTURE = D(2099, 1, 1)


def admin():
    return make_user("ADMIN")


def rich_worker(archive=True):
    """Hồ sơ có dữ liệu cá nhân ở MỌI bảng liên quan, tài liệu 3 phiên bản + biên bản đồng ý
    Ký giấy + tệp hợp đồng. Mọi giá trị cá nhân chứa MARK để quét sau khi ẩn danh."""
    worker = make_worker_full(
        full_name=f"{MARK} Họ Tên", email=f"{MARK}@example.com", skills=MARK, note=MARK
    )
    Worker.objects.filter(pk=worker.pk).update(employee_code=f"CN-T{worker.pk:05d}")
    worker.refresh_from_db()
    identity = IdentityDocument.objects.get(worker=worker)
    identity.old_id_number_enc = f"{MARK}OLD"
    identity.permanent_address_enc = f"{MARK} thường trú"
    identity.issue_place = MARK
    identity.hometown = MARK
    identity.birth_registration_place = MARK
    identity.issue_date = D(2021, 5, 1)
    identity.expiry_date = D(2036, 5, 1)
    identity.save()
    EmergencyContact.objects.filter(worker=worker).update(
        full_name=MARK, relationship=MARK, phone="0911222333"
    )
    app = make_application(worker, "FAILED", result_date=D(2026, 1, 5))
    Application.objects.filter(pk=app.pk).update(
        expected_salary=9_000_000, interview_notes=MARK, reject_reason=MARK
    )
    level = EducationLevel.objects.first()
    Education.objects.create(worker=worker, education_level=level, school_name=MARK, major=MARK)
    Certificate.objects.create(worker=worker, name=MARK, issuer=MARK, note=MARK)
    WorkExperience.objects.create(
        worker=worker, company_name=MARK, job_title=MARK, description=MARK
    )
    emp = make_employment(worker, "RESIGNED")
    emp.resign_date, emp.resign_reason, emp.resign_note = D(2026, 1, 1), "SELF", MARK
    emp.save()

    v1 = make_document(worker, "CCCD_FRONT", content=b"%PDF-v1", name=f"{MARK}1.pdf")
    v2 = make_document(worker, "CCCD_FRONT", content=b"%PDF-v2", name=f"{MARK}2.pdf", replaces=v1)
    WorkerDocument.objects.filter(pk=v1.pk).update(is_current=False)
    v3 = make_document(worker, "CCCD_FRONT", content=b"%PDF-v3", name=f"{MARK}3.pdf", replaces=v2)
    WorkerDocument.objects.filter(pk=v2.pk).update(is_current=False)
    consent_doc = make_document(worker, "CONSENT", content=b"%PDF-consent", name=f"{MARK}c.pdf")
    contract_doc = make_document(worker, "CONTRACT", content=b"%PDF-contract", name=f"{MARK}h.pdf")
    DataConsent.objects.create(
        worker=worker,
        consented=True,
        consent_date=D(2026, 1, 2),
        method="PAPER",
        document=consent_doc,
        recorded_by=worker.created_by,
    )
    Contract.objects.create(
        worker=worker,
        contract_no=f"HD-{worker.pk}",
        contract_type="FIXED_TERM",
        signed_date=D(2026, 1, 1),
        effective_date=D(2026, 1, 1),
        expiry_date=D(2027, 1, 1),
        document=contract_doc,
        note=MARK,
        created_by=worker.created_by,
    )
    log(
        "UPDATE",
        user=worker.created_by,
        obj=worker,
        changes={"full_name": ("Tên Cũ", f"{MARK} Họ Tên"), "phone": ("0900000001", "0900000002")},
    )
    if archive:
        with freeze_time(at(2026, 2, 1)):
            transition(worker, VS.ARCHIVED, worker.created_by)
        worker.refresh_from_db()
    return worker, [v1, v2, v3, consent_doc, contract_doc]


def stored_paths(documents):
    root = Path(settings.PRIVATE_MEDIA_ROOT)
    return [root / d.stored_file.name for d in documents]


def dump(obj):
    """Mọi giá trị cột của một dòng (trường mã hóa tự giải mã khi đọc), nối thành chuỗi."""
    return " | ".join(str(getattr(obj, f.attname)) for f in obj._meta.concrete_fields)


def run(worker_or_list, user=None, kind=Kind.EXPIRED, **kw):
    workers = worker_or_list if isinstance(worker_or_list, list) else [worker_or_list]
    kw.setdefault("today", FAR_FUTURE)
    return anonymize(workers, kind, user or admin(), **kw)


# ----- Bảng 4.7: giữ gì, xóa gì ----------------------------------------------------------------
def test_worker_va_giay_to_theo_bang_4_7(django_capture_on_commit_callbacks):
    worker, _ = rich_worker()
    with django_capture_on_commit_callbacks(execute=True):
        run(worker)
    w = Worker.objects.get(pk=worker.pk)
    assert w.full_name == "(Đã ẩn danh)" and w.name_search == ""
    assert (w.date_of_birth, w.gender, w.phone, w.email) == (None, "", "", "")
    assert (w.current_address, w.skills, w.note) == ("", "", "")
    assert w.anonymized_at is not None
    # Giữ: mã, trạng thái, người tạo, quốc tịch
    assert w.worker_code == worker.worker_code and w.employee_code == worker.employee_code
    assert w.verification_status == VS.ARCHIVED and w.created_by_id == worker.created_by_id
    assert w.nationality == "Việt Nam"

    ident = IdentityDocument.objects.get(worker=worker)  # dòng khung còn
    assert (ident.id_number_enc, ident.id_number_hash, ident.old_id_number_enc) == (None,) * 3
    assert (ident.permanent_address_enc, ident.issue_date, ident.expiry_date) == (None,) * 3
    assert (ident.issue_place, ident.hometown, ident.birth_registration_place) == ("",) * 3
    assert ident.id_doc_type  # loại giấy tờ không phải trường cá nhân: giữ cho thống kê


def test_bang_con_theo_bang_4_7(django_capture_on_commit_callbacks):
    worker, _ = rich_worker()
    contacts = EmergencyContact.objects.filter(worker=worker).count()
    with django_capture_on_commit_callbacks(execute=True):
        run(worker)
    assert EmergencyContact.objects.filter(worker=worker).count() == contacts  # giữ dòng khung
    contact = EmergencyContact.objects.get(worker=worker)
    assert (contact.full_name, contact.relationship, contact.phone) == ("", "", "")

    app = Application.objects.get(worker=worker)  # giữ vị trí, nguồn, ngày, trạng thái
    assert (app.expected_salary, app.interview_notes, app.reject_reason) == (None, "", "")
    assert app.status == "FAILED" and app.position_id and app.source_id and app.applied_date

    edu = Education.objects.get(worker=worker)  # giữ trình độ (thống kê)
    assert (edu.school_name, edu.major, edu.note) == ("", "", "") and edu.education_level_id
    cert = Certificate.objects.get(worker=worker)
    assert (cert.name, cert.issuer, cert.note) == ("", "", "")
    exp = WorkExperience.objects.get(worker=worker)
    assert (exp.company_name, exp.job_title, exp.description) == ("", "", "")

    emp = Employment.objects.get(worker=worker)  # giữ bộ phận, chức danh, ngày, trạng thái
    assert emp.resign_note == "" and emp.section_id and emp.position_id
    assert emp.work_status == "RESIGNED" and emp.resign_date == D(2026, 1, 1)
    contract = Contract.objects.get(worker=worker)  # giữ số hợp đồng
    assert contract.note == "" and contract.contract_no == f"HD-{worker.pk}"

    consents = DataConsent.objects.filter(worker=worker)  # giữ có/không, ngày, hình thức
    assert consents.count() == 2  # bản điện tử của factory + bản Ký giấy do test thêm
    paper = consents.get(method="PAPER")
    assert (paper.consented, paper.consent_date) == (True, D(2026, 1, 2))
    assert paper.document_id  # chỉ tệp biên bản bị xóa, dòng tài liệu vẫn còn
    assert StatusChange.objects.filter(worker=worker).count() >= 2  # lịch sử trạng thái giữ nguyên


def test_tai_lieu_moi_phien_ban_bi_xoa_tep_va_ten_goc(django_capture_on_commit_callbacks):
    worker, docs = rich_worker()
    paths = stored_paths(docs)
    assert len(paths) == 5 and all(p.exists() for p in paths)
    current = [WorkerDocument.objects.get(pk=d.pk).is_current for d in docs[:3]]
    assert current == [False, False, True]  # có bản đã bị thay thế
    with django_capture_on_commit_callbacks(execute=True):
        run(worker)
    assert not any(p.exists() for p in paths)  # kể cả bản cũ, biên bản đồng ý, tệp hợp đồng
    after = WorkerDocument.objects.filter(worker=worker)
    assert after.count() == 5  # giữ dòng: loại, phiên bản, ngày, người tải
    for doc in after:
        assert not doc.stored_file and doc.original_name == ""
        assert doc.document_type_id and doc.version and doc.uploaded_by_id


def test_thu_muc_private_media_khong_con_tep_nao_cua_ho_so(django_capture_on_commit_callbacks):
    worker, docs = rich_worker()
    other = make_worker_full()
    other_doc = make_document(other, "CCCD_FRONT", content=b"%PDF-other")
    root = Path(settings.PRIVATE_MEDIA_ROOT)
    folder = root / "documents" / str(worker.pk)
    assert any(folder.iterdir())
    with django_capture_on_commit_callbacks(execute=True):
        run(worker)
    assert not [p for p in folder.rglob("*") if p.is_file()]
    # Tệp của hồ sơ khác vẫn nguyên.
    assert stored_paths([other_doc])[0].exists()
    assert WorkerDocument.objects.get(pk=other_doc.pk).original_name == "a.pdf"


def test_quet_khong_con_gia_tri_nao_cua_ho_so_o_bat_ky_bang_nao(
    django_capture_on_commit_callbacks,
):
    worker, _ = rich_worker()
    with django_capture_on_commit_callbacks(execute=True):
        run(worker)
    rows = [
        *Worker.objects.filter(pk=worker.pk),
        *IdentityDocument.objects.filter(worker=worker),
        *EmergencyContact.objects.filter(worker=worker),
        *Application.objects.filter(worker=worker),
        *Education.objects.filter(worker=worker),
        *Certificate.objects.filter(worker=worker),
        *WorkExperience.objects.filter(worker=worker),
        *Employment.objects.filter(worker=worker),
        *Contract.objects.filter(worker=worker),
        *WorkerDocument.objects.filter(worker=worker),
        *DataConsent.objects.filter(worker=worker),
        *StatusChange.objects.filter(worker=worker),
        *AuditPersonalValue.objects.filter(worker=worker),
    ]
    assert len(rows) > 12
    leaked = [dump(r) for r in rows if MARK in dump(r) or "0911222333" in dump(r)]
    assert leaked == []
    # Nhật ký chung cũng không chứa giá trị cá nhân.
    for entry in AuditLog.objects.filter(worker=worker):
        assert MARK not in f"{entry.changes} {entry.note} {entry.object_repr}"


# ----- Nhật ký (câu 30) ---------------------------------------------------------------------
def test_xoa_gia_tri_ca_nhan_trong_nhat_ky_nhung_giu_dong_nhat_ky(
    django_capture_on_commit_callbacks,
):
    worker, _ = rich_worker()
    other, _ = rich_worker(archive=False)
    assert AuditPersonalValue.objects.filter(worker=worker).exists()
    other_values = AuditPersonalValue.objects.filter(worker=other).count()
    logs_before = AuditLog.objects.filter(worker=worker).count()
    with django_capture_on_commit_callbacks(execute=True):
        run(worker)
    assert not AuditPersonalValue.objects.filter(worker=worker).exists()
    assert AuditPersonalValue.objects.filter(worker=other).count() == other_values
    assert AuditLog.objects.filter(worker=worker).count() == logs_before + 1  # chỉ thêm một dòng
    entry = AuditLog.objects.filter(worker=worker, action="ANONYMIZE").get()
    assert entry.object_repr == worker.worker_code
    assert entry.user is not None and "Hết hạn lưu trữ" in entry.note
    assert AnonymizationRecord.objects.get().record_no in entry.note
    update = AuditLog.objects.filter(worker=worker, action="UPDATE").get()
    assert set(update.changes) == {"full_name", "phone"}  # tên trường vẫn còn để truy vết


# ----- Tệp chỉ bị xóa sau khi commit, lỗi thì hoàn tác ----------------------------------------
def test_tep_chi_bi_xoa_sau_khi_giao_dich_commit(django_capture_on_commit_callbacks):
    worker, docs = rich_worker()
    paths = stored_paths(docs)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        run(worker)
        assert all(p.exists() for p in paths)  # trong giao dịch: tệp còn
    assert len(callbacks) == 1
    callbacks[0]()
    assert not any(p.exists() for p in paths)


def test_giao_dich_loi_giua_chung_hoan_tac_ca_du_lieu_lan_tep(
    monkeypatch, django_capture_on_commit_callbacks
):
    first, docs1 = rich_worker()
    second, docs2 = rich_worker()
    calls = {"n": 0}
    original = retention.log

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("hỏng nhật ký")
        return original(*args, **kwargs)

    monkeypatch.setattr(retention, "log", flaky)
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        with pytest.raises(RuntimeError):
            run([first, second])
    assert callbacks == []
    assert all(p.exists() for p in stored_paths(docs1 + docs2))
    for w in (first, second):
        fresh = Worker.objects.get(pk=w.pk)
        assert fresh.anonymized_at is None and MARK in fresh.full_name
        assert AuditPersonalValue.objects.filter(worker=w).exists()
    assert not AnonymizationRecord.objects.exists() and not AnonymizationItem.objects.exists()


# ----- Biên bản ---------------------------------------------------------------------------
def test_so_bien_ban_tang_dan_trong_nam_va_dem_lai_tu_dau_o_nam_moi(
    django_capture_on_commit_callbacks,
):
    workers = [rich_worker()[0] for _ in range(3)]
    with django_capture_on_commit_callbacks(execute=True):
        with freeze_time(at(2026, 12, 30)):
            r1 = run(workers[0])
            r2 = run(workers[1])
        with freeze_time(at(2027, 1, 2)):
            r3 = run(workers[2])
    assert (r1.record_no, r2.record_no, r3.record_no) == (
        "BBH-2026-001",
        "BBH-2026-002",
        "BBH-2027-001",
    )


def test_mot_bien_ban_cho_nhieu_ho_so_ghi_dung_item(django_capture_on_commit_callbacks):
    a, _ = rich_worker()
    b, _ = rich_worker()
    user = admin()
    with django_capture_on_commit_callbacks(execute=True):
        record = run([a, b], user=user, note="Hủy theo danh sách chờ hủy")
    assert (record.worker_count, record.kind, record.performed_by) == (2, Kind.EXPIRED, user)
    assert record.note == "Hủy theo danh sách chờ hủy"
    items = {i.worker_code: i for i in record.items.all()}
    assert set(items) == {a.worker_code, b.worker_code}
    item = items[a.worker_code]
    assert item.employee_code == a.employee_code
    assert item.retention_basis == "RESIGNED" and item.retention_expired_on == D(2036, 1, 1)
    assert AuditLog.objects.filter(action="ANONYMIZE").count() == 2


def test_item_ghi_can_cu_truoc_khi_xoa_du_lieu(django_capture_on_commit_callbacks):
    worker, _ = rich_worker()
    with django_capture_on_commit_callbacks(execute=True):
        run(worker)
    # Sau ẩn danh, retention_info vẫn tính được (lịch sử trạng thái và ngày còn), cùng kết quả.
    item = AnonymizationItem.objects.get(worker=worker)
    info = retention.retention_info(Worker.objects.get(pk=worker.pk))
    assert (item.retention_basis, item.retention_expired_on) == (info.basis, info.expires_on)


# ----- Quyền và điều kiện -----------------------------------------------------------------
@pytest.mark.parametrize("role", ["HR_MANAGER", "HR_STAFF", "VIEWER"])
def test_chi_admin_duoc_an_danh_hoa(role):
    worker, _ = rich_worker()
    with pytest.raises(RetentionForbidden):
        run(worker, user=make_user(role))
    assert Worker.objects.get(pk=worker.pk).anonymized_at is None


def test_chua_dang_nhap_hoac_he_thong_khong_duoc_an_danh():
    worker, _ = rich_worker()
    with pytest.raises(RetentionForbidden):
        anonymize([worker], Kind.EXPIRED, None, today=FAR_FUTURE)


@pytest.mark.parametrize("status", [VS.DRAFT, VS.PENDING, VS.NEEDS_INFO, VS.VERIFIED, VS.REJECTED])
def test_chi_an_danh_ho_so_luu_tru(status):
    worker = make_worker_in_status(status)
    for kind in (Kind.EXPIRED, Kind.SUBJECT_REQUEST):
        with pytest.raises(RetentionError, match="Lưu trữ"):
            run(worker, kind=kind, note="x", request_ref="Đơn 1")
    assert not AnonymizationRecord.objects.exists()


def test_khong_an_danh_hai_lan(django_capture_on_commit_callbacks):
    worker, _ = rich_worker()
    with django_capture_on_commit_callbacks(execute=True):
        run(worker)
    with pytest.raises(RetentionError, match="đã được ẩn danh"):
        run(worker)
    assert AnonymizationRecord.objects.count() == 1


def test_loai_het_han_chi_an_danh_ho_so_da_qua_han():
    worker, _ = rich_worker()  # lưu trữ 01/02/2026 theo căn cứ công nhân đã nghỉ: hết hạn 2036
    with pytest.raises(RetentionError, match="chưa hết hạn"):
        run(worker, today=D(2030, 1, 1))
    assert Worker.objects.get(pk=worker.pk).anonymized_at is None
    run(worker, today=D(2036, 1, 2))  # hết hạn 01/01/2036 -> quá hạn từ 02/01/2036
    assert Worker.objects.get(pk=worker.pk).anonymized_at is not None


def test_loai_het_han_dung_ngay_het_han_van_con_luu():
    worker, _ = rich_worker()
    with pytest.raises(RetentionError, match="chưa hết hạn"):
        run(worker, today=D(2036, 1, 1))


def test_danh_sach_rong_va_mot_ho_so_loi_thi_ca_lo_bi_tu_choi():
    with pytest.raises(RetentionError, match="Chưa chọn"):
        run([])
    good, _ = rich_worker()
    bad = make_worker_in_status(VS.VERIFIED)
    with pytest.raises(RetentionError):
        run([good, bad])
    assert Worker.objects.get(pk=good.pk).anonymized_at is None  # không ẩn danh một nửa
    assert not AnonymizationRecord.objects.exists()


def test_sau_an_danh_khong_mo_lai_khong_sua_va_roi_khoi_danh_sach_cho_huy(
    django_capture_on_commit_callbacks,
):
    worker, _ = rich_worker()
    with django_capture_on_commit_callbacks(execute=True):
        run(worker)
    worker.refresh_from_db()
    with pytest.raises(TransitionError, match="ẩn danh"):
        transition(worker, VS.DRAFT, make_user("HR_MANAGER"))
    assert not rules.can_edit_profile(make_user("ADMIN"), worker)
    assert not rules.can_add_document(make_user("ADMIN"), worker)
    assert worker.pk not in [w.pk for w, _ in retention.expired_entries(FAR_FUTURE)]


# ----- Ẩn danh hóa theo yêu cầu (câu 38) ----------------------------------------------------
def request_kwargs(worker, **override):
    data = {
        "reason": f"Chủ thể yêu cầu xóa dữ liệu, hồ sơ {worker.worker_code}",
        "request_ref": "Đơn số 15 ngày 20/11/2026",
        "confirm_code": worker.worker_code,
    }
    data.update(override)
    return data


@pytest.mark.parametrize("role", ["HR_MANAGER", "HR_STAFF", "VIEWER"])
def test_theo_yeu_cau_chi_admin(role):
    worker, _ = rich_worker()
    with pytest.raises(RetentionForbidden):
        anonymize_on_request(worker, make_user(role), **request_kwargs(worker))


@pytest.mark.parametrize("status", [VS.DRAFT, VS.PENDING, VS.VERIFIED, VS.REJECTED])
def test_theo_yeu_cau_ho_so_chua_luu_tru_bi_chan(status):
    worker = make_worker_in_status(status)
    with pytest.raises(RetentionError, match="Lưu trữ"):
        anonymize_on_request(worker, admin(), **request_kwargs(worker))


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"reason": ""}, "lý do"),
        ({"reason": "   "}, "lý do"),
        ({"request_ref": ""}, "đơn yêu cầu"),
        ({"request_ref": "  "}, "đơn yêu cầu"),
        ({"confirm_code": ""}, "không khớp"),
        ({"confirm_code": "HS-SAI-00000"}, "không khớp"),
        ({"confirm_code": "hs-2026-00001"}, "không khớp"),
    ],
)
def test_theo_yeu_cau_thieu_hoac_sai_thong_tin_bi_chan(override, message):
    worker, _ = rich_worker()
    with pytest.raises(RetentionError, match=message):
        anonymize_on_request(worker, admin(), **request_kwargs(worker, **override))
    assert Worker.objects.get(pk=worker.pk).anonymized_at is None
    assert not AnonymizationRecord.objects.exists()


def test_theo_yeu_cau_da_an_danh_roi_bi_chan(django_capture_on_commit_callbacks):
    worker, _ = rich_worker()
    with django_capture_on_commit_callbacks(execute=True):
        anonymize_on_request(worker, admin(), **request_kwargs(worker))
    with pytest.raises(RetentionError, match="đã được ẩn danh"):
        anonymize_on_request(worker, admin(), **request_kwargs(worker))


def test_theo_yeu_cau_thanh_cong_ghi_bien_ban_va_ngay_le_ra_het_han(
    django_capture_on_commit_callbacks,
):
    worker, docs = rich_worker()
    paths = stored_paths(docs)
    user = admin()
    with django_capture_on_commit_callbacks(execute=True):
        record = anonymize_on_request(worker, user, **request_kwargs(worker))
    assert record.kind == Kind.SUBJECT_REQUEST and record.worker_count == 1
    assert record.request_ref == "Đơn số 15 ngày 20/11/2026"
    assert worker.worker_code in record.note and record.performed_by == user
    item = record.items.get()
    assert item.retention_expired_on == D(2036, 1, 1)  # ngày lẽ ra hết hạn nằm ở tương lai
    assert Worker.objects.get(pk=worker.pk).anonymized_at is not None
    assert not any(p.exists() for p in paths)
    entry = AuditLog.objects.get(worker=worker, action="ANONYMIZE")
    assert "Theo yêu cầu của chủ thể" in entry.note and MARK not in entry.note
    assert not AuditPersonalValue.objects.filter(worker=worker).exists()


def test_ly_do_va_ghi_chu_tu_dong_khong_chua_ho_ten(django_capture_on_commit_callbacks):
    worker, _ = rich_worker()
    with django_capture_on_commit_callbacks(execute=True):
        record = anonymize_on_request(worker, admin(), **request_kwargs(worker))
    text = " ".join(
        [record.note, record.request_ref]
        + [f"{e.note} {e.object_repr}" for e in AuditLog.objects.filter(action="ANONYMIZE")]
    )
    assert MARK not in text and "Họ Tên" not in text
