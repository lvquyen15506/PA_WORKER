"""Service hồ sơ: tạo, sửa theo ma trận 4.4, đồng ý, mở lại.

Gồm kịch bản nghiệm thu 14 ở mức service."""

import datetime
import json
import re

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.audit.models import AuditLog, AuditPersonalValue
from apps.audit.services import PERSONAL_PLACEHOLDER
from apps.core.choices import VerificationStatus as VS
from apps.core.models import ApplicationSource, CodeSequence, Position
from apps.recruitment.models import Application
from apps.workers import services, workflow
from apps.workers.duplicates import find_by_id_number
from apps.workers.models import (
    DataConsent,
    EmergencyContact,
    IdentityDocument,
    StatusChange,
    Worker,
)
from apps.workers.services import WorkerDataError
from apps.workers.validation import ValidationResult
from apps.workers.workflow import TransitionError, can_review
from tests.factories import (
    fake_id,
    make_document,
    make_user,
    make_worker_full,
    make_worker_in_status,
)

pytestmark = pytest.mark.django_db
D = datetime.date
EDITORS = ["ADMIN", "HR_MANAGER", "HR_STAFF"]
CONTACT = {"full_name": "Người Thân Mới", "relationship": "Chị", "phone": "0988777666"}


def fresh(worker):
    return Worker.objects.get(pk=worker.pk)


def dump_logs(worker):
    return json.dumps(
        [[e.changes, e.note, e.object_repr] for e in AuditLog.objects.filter(worker=worker)],
        ensure_ascii=False,
    )


# ===== Tạo hồ sơ ===========================================================================
@pytest.mark.parametrize("role", EDITORS)
def test_tao_nhap_chi_can_ho_ten_va_sdt(role):
    user = make_user(role)
    worker = services.create_worker(user, {"full_name": "Trần Văn Giả", "phone": "0911222333"})
    assert re.fullmatch(r"HS-\d{4}-\d{5}", worker.worker_code)
    assert worker.verification_status == VS.DRAFT and worker.created_by == user
    assert worker.name_search == "tran van gia" and worker.employee_code is None
    assert not IdentityDocument.objects.filter(worker=worker).exists()
    assert worker.nationality == "Việt Nam"


def test_tao_ghi_dong_dau_cua_dong_thoi_gian_va_nhat_ky_khong_ho_ten():
    user = make_user("HR_STAFF")
    worker = services.create_worker(user, {"full_name": "Họ Tên Rất Riêng", "phone": "0911222333"})
    change = StatusChange.objects.get(worker=worker)
    assert (change.from_status, change.to_status, change.changed_by) == ("", VS.DRAFT, user)
    entry = AuditLog.objects.get(worker=worker)
    assert (entry.action, entry.user, entry.object_repr) == ("CREATE", user, worker.worker_code)
    assert "Riêng" not in dump_logs(worker)


def test_tao_day_du_giay_to_va_lien_he_ma_hoa_va_bam():
    user = make_user("HR_STAFF")
    number = fake_id()
    worker = services.create_worker(
        user,
        {
            "full_name": "Phạm Giả",
            "phone": "0911222333",
            "date_of_birth": D(1995, 5, 5),
            "gender": "FEMALE",
            "id_doc_type": "CCCD_2021",
            "id_number": f" {number[:6]} {number[6:]} ",  # có khoảng trắng
            "permanent_address": "Địa chỉ thường trú giả",
            "issue_date": D(2021, 1, 1),
        },
        contacts=[
            {"id": None, "delete": False, **CONTACT},
            {"id": None, "delete": False, "full_name": "", "relationship": "", "phone": ""},
        ],
    )
    identity = IdentityDocument.objects.get(worker=worker)
    assert identity.id_number_enc == number and identity.id_number_hash
    assert find_by_id_number(number) == worker
    assert identity.permanent_address_enc == "Địa chỉ thường trú giả"
    contacts = list(worker.emergency_contacts.all())
    assert [(c.full_name, c.sort_order) for c in contacts] == [
        ("Người Thân Mới", 0)
    ]  # dòng trống bỏ
    # Giá trị cá nhân của liên hệ nằm ở AuditPersonalValue, không ở changes
    assert "Người Thân Mới" not in dump_logs(worker)
    saved = {
        p.field_name: p.new_value_enc for p in AuditPersonalValue.objects.filter(worker=worker)
    }
    assert saved[f"emergency_contacts[{contacts[0].pk}].full_name"] == "Người Thân Mới"


def test_ma_ho_so_tang_dan_khong_trung():
    user = make_user("HR_STAFF")
    codes = [
        services.create_worker(user, {"full_name": f"A{i}", "phone": "0911222333"}).worker_code
        for i in range(3)
    ]
    assert len(set(codes)) == 3 and codes == sorted(codes)


@pytest.mark.parametrize("role", ["VIEWER"])
def test_viewer_va_nguoi_chua_dang_nhap_khong_tao_duoc(role):
    with pytest.raises(PermissionDenied):
        services.create_worker(make_user(role), {"full_name": "A", "phone": "0911222333"})
    with pytest.raises(PermissionDenied):
        services.create_worker(None, {"full_name": "A", "phone": "0911222333"})
    assert not Worker.objects.exists()


def test_tao_chan_du_lieu_sai_va_khong_de_lai_gi():
    user = make_user("HR_STAFF")
    today = timezone.localdate()
    under_15 = D(today.year - 10, 1, 1)
    with pytest.raises(WorkerDataError) as exc:
        services.create_worker(
            user, {"full_name": "", "phone": "12", "date_of_birth": under_15, "id_number": "1"}
        )
    assert set(exc.value.errors) == {"full_name", "phone", "date_of_birth", "id_number"}
    assert not Worker.objects.exists() and not AuditLog.objects.exists()
    assert not CodeSequence.objects.filter(code_type="WORKER").exists() or (
        CodeSequence.objects.get(code_type="WORKER").last_number == 0
    )


def test_tao_chan_lien_he_thieu_truong():
    with pytest.raises(WorkerDataError) as exc:
        services.create_worker(
            make_user("HR_STAFF"),
            {"full_name": "A", "phone": "0911222333"},
            contacts=[{"full_name": "Chỉ có tên", "relationship": "", "phone": ""}],
        )
    assert set(exc.value.contact_errors[0]) == {"relationship", "phone"}


def test_tao_chan_trung_cccd_va_tra_ve_ho_so_cu():
    old = make_worker_full()
    number = fake_id()
    IdentityDocument.objects.filter(worker=old).delete()
    IdentityDocument.objects.create(worker=old, id_number_enc=number)
    with pytest.raises(WorkerDataError) as exc:
        services.create_worker(
            make_user("HR_STAFF"), {"full_name": "B", "phone": "0911222333", "id_number": number}
        )
    assert exc.value.duplicate == old and old.worker_code in exc.value.errors["id_number"]
    assert Worker.objects.count() == 1


def test_hai_nguoi_nhap_cung_cccd_cung_luc_rang_buoc_unique_chan_va_khong_mat_ma(monkeypatch):
    user = make_user("HR_STAFF")
    number = fake_id()
    first = services.create_worker(
        user, {"full_name": "A", "phone": "0911222333", "id_number": number}
    )
    # Mô phỏng người thứ hai qua được bước kiểm tra trùng (chạy song song): CSDL phải chặn.
    monkeypatch.setattr(services, "validate_worker_data", lambda *a, **k: ValidationResult())
    with pytest.raises(WorkerDataError) as exc:
        services.create_worker(user, {"full_name": "B", "phone": "0911222334", "id_number": number})
    assert "id_number" in exc.value.errors
    assert Worker.objects.count() == 1
    monkeypatch.undo()
    third = services.create_worker(user, {"full_name": "C", "phone": "0911222335"})
    # Lần tạo hỏng không làm mất số mã: mã kế tiếp liền sau mã đầu.
    assert int(third.worker_code[-5:]) == int(first.worker_code[-5:]) + 1


def test_truong_khong_hop_le_trong_data_bi_tu_choi():
    with pytest.raises(ValueError):
        services.create_worker(
            make_user("HR_STAFF"),
            {"full_name": "A", "phone": "0911222333", "verification_status": "VERIFIED"},
        )
    assert not Worker.objects.exists()


# ===== Sửa hồ sơ theo ma trận 4.4 ===========================================================
@pytest.mark.parametrize("status", [VS.DRAFT, VS.NEEDS_INFO, VS.VERIFIED])
@pytest.mark.parametrize("role", EDITORS)
def test_trang_thai_cho_phep_sua(status, role):
    worker = make_worker_in_status(status)
    result = services.update_worker(make_user(role), worker, {"email": "moi@example.com"})
    assert result.changed and fresh(worker).email == "moi@example.com"


@pytest.mark.parametrize("status", [VS.PENDING, VS.REJECTED, VS.ARCHIVED])
@pytest.mark.parametrize("role", [*EDITORS, "VIEWER"])
def test_trang_thai_khoa_khong_ai_sua_duoc(status, role):
    worker = make_worker_in_status(status)
    with pytest.raises(PermissionDenied):
        services.update_worker(make_user(role), worker, {"email": "moi@example.com"})
    assert fresh(worker).email == ""


@pytest.mark.parametrize("status", [VS.DRAFT, VS.NEEDS_INFO, VS.VERIFIED])
def test_viewer_khong_sua_duoc_o_bat_ky_trang_thai(status):
    worker = make_worker_in_status(status)
    with pytest.raises(PermissionDenied):
        services.update_worker(make_user("VIEWER"), worker, {"email": "moi@example.com"})


def test_ho_so_da_an_danh_khong_sua_duoc():
    worker = make_worker_full()
    Worker.objects.filter(pk=worker.pk).update(anonymized_at=timezone.now())
    with pytest.raises(PermissionDenied):
        services.update_worker(make_user("ADMIN"), worker, {"email": "moi@example.com"})


def test_doi_tuong_cu_trong_bo_nho_khong_qua_mat_khoa_trang_thai_hien_tai():
    worker = make_worker_in_status(VS.DRAFT)
    stale = fresh(worker)
    workflow.transition(worker, VS.PENDING, worker.created_by)  # người khác vừa gửi duyệt
    assert stale.verification_status == VS.DRAFT
    with pytest.raises(PermissionDenied):
        services.update_worker(make_user("HR_STAFF"), stale, {"email": "moi@example.com"})


def test_sua_khong_doi_gi_thi_khong_ghi_nhat_ky_khong_doi_updated_at():
    worker = make_worker_in_status(VS.DRAFT)
    before = fresh(worker).updated_at
    logs = AuditLog.objects.count()
    result = services.update_worker(
        make_user("HR_STAFF"),
        worker,
        {"full_name": worker.full_name, "phone": worker.phone, "email": "", "gender": "MALE"},
    )
    assert result == (False, False)
    assert AuditLog.objects.count() == logs and fresh(worker).updated_at == before


# ===== Kịch bản 14: sửa họ tên hồ sơ Đã xác minh =============================================
def test_kich_ban_14_sua_ho_ten_ve_cho_duyet_va_nhat_ky_co_gia_tri_cu_moi():
    worker = make_worker_in_status(VS.VERIFIED)
    old_name = worker.full_name
    editor = make_user("HR_STAFF")
    result = services.update_worker(editor, worker, {"full_name": "Nguyễn Tên Mới Giả"})
    assert result == (True, True)
    worker = fresh(worker)
    assert worker.verification_status == VS.PENDING and worker.full_name == "Nguyễn Tên Mới Giả"
    assert worker.name_search == "nguyen ten moi gia"
    # Dòng thời gian: người sửa được ghi là người gửi duyệt, lý do tự điền không có họ tên.
    change = StatusChange.objects.filter(worker=worker).last()
    assert (change.from_status, change.to_status, change.changed_by) == (
        VS.VERIFIED,
        VS.PENDING,
        editor,
    )
    assert change.reason == "Sửa trường định danh: họ tên"
    # Nhật ký: giá trị cũ và mới nằm ở AuditPersonalValue; AuditLog chỉ có chỗ giữ chỗ.
    update = AuditLog.objects.get(worker=worker, action="UPDATE")
    assert update.changes == {"full_name": PERSONAL_PLACEHOLDER}
    values = AuditPersonalValue.objects.get(audit_log=update, field_name="full_name")
    assert (values.old_value_enc, values.new_value_enc) == (old_name, "Nguyễn Tên Mới Giả")
    status_log = AuditLog.objects.filter(worker=worker, action="STATUS_CHANGE").first()  # mới nhất
    assert status_log.changes == {"verification_status": ["VERIFIED", "PENDING"]}
    everything = dump_logs(worker)
    assert old_name not in everything and "Tên Mới" not in everything
    # Người sửa không tự duyệt lại được.
    assert not can_review(worker, editor)


@pytest.mark.parametrize(
    ("data", "label"),
    [
        ({"date_of_birth": D(1990, 1, 1)}, "ngày sinh"),
        ({"id_number": "999000000777"}, "số CCCD"),
    ],
)
def test_sua_ngay_sinh_hoac_so_cccd_cung_ve_cho_duyet(data, label):
    worker = make_worker_in_status(VS.VERIFIED)
    result = services.update_worker(make_user("HR_MANAGER"), worker, data)
    assert result.back_to_pending and fresh(worker).verification_status == VS.PENDING
    assert (
        StatusChange.objects.filter(worker=worker).last().reason == f"Sửa trường định danh: {label}"
    )


def test_sua_nhieu_truong_dinh_danh_cung_luc_chi_mot_lan_ve_cho_duyet():
    worker = make_worker_in_status(VS.VERIFIED)
    services.update_worker(
        make_user("HR_STAFF"),
        worker,
        {"full_name": "Tên Khác", "date_of_birth": D(1991, 2, 2), "id_number": "999000000888"},
    )
    pendings = StatusChange.objects.filter(worker=worker, to_status=VS.PENDING)
    assert pendings.count() == 2  # lần gửi duyệt đầu của factory + lần tự về Chờ duyệt này
    assert pendings.last().reason == "Sửa trường định danh: họ tên, ngày sinh, số CCCD"


@pytest.mark.parametrize(
    "data",
    [
        {"phone": "0900111222"},
        {"email": "x@example.com"},
        {"current_address": "Địa chỉ mới"},
        {"skills": "Hàn"},
        {"note": "Ghi chú"},
        {"gender": "FEMALE"},
        {"issue_place": "Nơi cấp mới"},
        {"permanent_address": "Thường trú mới"},
    ],
)
def test_sua_truong_khac_khi_da_xac_minh_van_giu_da_xac_minh(data):
    worker = make_worker_in_status(VS.VERIFIED)
    result = services.update_worker(make_user("HR_STAFF"), worker, data)
    assert result == (True, False)
    assert fresh(worker).verification_status == VS.VERIFIED


def test_sua_hoc_dinh_danh_khi_nhap_khong_doi_trang_thai():
    worker = make_worker_in_status(VS.DRAFT)
    result = services.update_worker(make_user("HR_STAFF"), worker, {"full_name": "Tên Khác"})
    assert result == (True, False) and fresh(worker).verification_status == VS.DRAFT
    assert StatusChange.objects.filter(worker=worker).count() == 1  # chỉ dòng tạo hồ sơ


def test_sua_giay_to_ghi_nhat_ky_theo_ten_logic_va_cap_nhat_bam():
    worker = make_worker_in_status(VS.DRAFT)
    old_number = IdentityDocument.objects.get(worker=worker).id_number_enc
    services.update_worker(
        make_user("HR_STAFF"),
        worker,
        {"id_number": "999000000321", "id_doc_type": "CAN_CUOC_2024", "hometown": "Quê giả"},
    )
    entry = AuditLog.objects.get(worker=worker, action="UPDATE")
    assert entry.object_type == "workers.IdentityDocument"
    assert entry.changes["identity.id_number"] == PERSONAL_PLACEHOLDER
    assert entry.changes["identity.id_doc_type"] == ["CCCD_2021", "CAN_CUOC_2024"]  # không cá nhân
    pv = AuditPersonalValue.objects.get(audit_log=entry, field_name="identity.id_number")
    assert (pv.old_value_enc, pv.new_value_enc) == (old_number, "999000000321")
    assert find_by_id_number("999000000321") == worker and find_by_id_number(old_number) is None


def test_sua_tao_giay_to_neu_chua_co():
    worker = services.create_worker(
        make_user("HR_STAFF"), {"full_name": "A", "phone": "0911222333"}
    )
    services.update_worker(
        make_user("HR_STAFF"), worker, {"id_doc_type": "CCCD_2021", "id_number": fake_id()}
    )
    assert IdentityDocument.objects.get(worker=worker).id_number_hash


def test_sua_bi_chan_khi_trung_cccd_nhung_duoc_giu_so_cua_chinh_minh():
    a, b = make_worker_in_status(VS.DRAFT), make_worker_in_status(VS.DRAFT)
    number_b = IdentityDocument.objects.get(worker=b).id_number_enc
    with pytest.raises(WorkerDataError) as exc:
        services.update_worker(make_user("HR_STAFF"), a, {"id_number": number_b})
    assert exc.value.duplicate == b
    own = IdentityDocument.objects.get(worker=a).id_number_enc
    assert services.update_worker(make_user("HR_STAFF"), a, {"id_number": own}).changed is False


def test_sua_ho_so_da_xac_minh_phai_giu_du_truong_gui_duyet():
    worker = make_worker_in_status(VS.VERIFIED)
    with pytest.raises(WorkerDataError) as exc:
        services.update_worker(make_user("HR_STAFF"), worker, {"current_address": ""})
    assert "current_address" in exc.value.errors
    assert fresh(worker).current_address and fresh(worker).verification_status == VS.VERIFIED
    # Ở Nháp thì được để trống.
    draft = make_worker_in_status(VS.DRAFT)
    services.update_worker(make_user("HR_STAFF"), draft, {"current_address": ""})
    assert fresh(draft).current_address == ""


def test_loi_giua_chung_khi_chuyen_cho_duyet_hoan_tac_ca_chinh_sua(monkeypatch):
    worker = make_worker_in_status(VS.VERIFIED)
    old_name = worker.full_name

    def boom(*args, **kwargs):
        raise RuntimeError("hỏng")

    monkeypatch.setattr(workflow, "transition", boom)
    with pytest.raises(RuntimeError):
        services.update_worker(make_user("HR_STAFF"), worker, {"full_name": "Tên Khác"})
    assert fresh(worker).full_name == old_name and fresh(worker).verification_status == VS.VERIFIED


def test_sua_cap_nhat_updated_at():
    worker = make_worker_in_status(VS.DRAFT)
    before = fresh(worker).updated_at
    services.update_worker(make_user("HR_STAFF"), worker, {"note": "mới"})
    assert fresh(worker).updated_at > before


# ===== Người liên hệ khẩn cấp ================================================================
def test_them_sua_xoa_lien_he_va_ghi_gia_tri_cu():
    worker = make_worker_in_status(VS.DRAFT)
    user = make_user("HR_STAFF")
    existing = worker.emergency_contacts.get()
    # thêm
    result = services.update_worker(user, worker, {}, contacts=[{"id": None, **CONTACT}])
    assert result.changed and worker.emergency_contacts.count() == 2
    added = worker.emergency_contacts.get(full_name="Người Thân Mới")
    assert added.sort_order == existing.sort_order + 1
    # sửa
    services.update_worker(
        user, worker, {}, contacts=[{"id": added.pk, **{**CONTACT, "phone": "0999888777"}}]
    )
    entry = AuditLog.objects.filter(worker=worker, action="UPDATE").first()
    pv = AuditPersonalValue.objects.get(audit_log=entry)
    assert pv.field_name == f"emergency_contacts[{added.pk}].phone"
    assert (pv.old_value_enc, pv.new_value_enc) == ("0988777666", "0999888777")
    # xóa: giá trị cũ vào nhật ký trước khi xóa dòng
    services.update_worker(user, worker, {}, contacts=[{"id": added.pk, "delete": True}])
    assert not EmergencyContact.objects.filter(pk=added.pk).exists()
    removed = AuditLog.objects.filter(worker=worker, note="Xóa người liên hệ khẩn cấp").get()
    old_values = {
        p.field_name: p.old_value_enc for p in AuditPersonalValue.objects.filter(audit_log=removed)
    }
    assert old_values[f"emergency_contacts[{added.pk}].full_name"] == "Người Thân Mới"
    assert "Người Thân Mới" not in dump_logs(worker)


def test_lien_he_none_la_khong_dung_toi_va_dong_trong_bi_bo_qua():
    worker = make_worker_in_status(VS.DRAFT)
    user = make_user("HR_STAFF")
    assert services.update_worker(user, worker, {}, contacts=None) == (False, False)
    blank = {"id": None, "delete": False, "full_name": "", "relationship": "", "phone": ""}
    assert services.update_worker(user, worker, {}, contacts=[blank]) == (False, False)
    assert worker.emergency_contacts.count() == 1


def test_khong_sua_duoc_lien_he_cua_ho_so_khac():
    a, b = make_worker_in_status(VS.DRAFT), make_worker_in_status(VS.DRAFT)
    other = b.emergency_contacts.get()
    with pytest.raises(PermissionDenied):
        services.update_worker(
            make_user("HR_STAFF"), a, {}, contacts=[{"id": other.pk, "delete": True}]
        )
    assert EmergencyContact.objects.filter(pk=other.pk).exists()


def test_lien_he_thieu_truong_bi_chan_khi_sua():
    worker = make_worker_in_status(VS.DRAFT)
    with pytest.raises(WorkerDataError) as exc:
        services.update_worker(
            make_user("HR_STAFF"), worker, {}, contacts=[{"id": None, "full_name": "Chỉ tên"}]
        )
    assert 0 in exc.value.contact_errors


def test_xoa_het_lien_he_van_cho_nhap_nhung_khong_gui_duyet_duoc():
    worker = make_worker_in_status(VS.DRAFT)
    contact = worker.emergency_contacts.get()
    services.update_worker(
        make_user("HR_STAFF"), worker, {}, contacts=[{"id": contact.pk, "delete": True}]
    )
    assert not worker.emergency_contacts.exists()
    with pytest.raises(TransitionError) as exc:
        workflow.transition(worker, VS.PENDING, worker.created_by)
    assert "emergency_contact" in [i.field for i in exc.value.issues]


# ===== Đồng ý xử lý dữ liệu ==================================================================
def test_ghi_nhan_dong_y_dien_tu():
    worker = make_worker_in_status(VS.DRAFT)
    user = make_user("HR_STAFF")
    consent = services.record_consent(
        user, worker, consented=True, consent_date=timezone.localdate(), method="ELECTRONIC"
    )
    assert (consent.recorded_by, consent.document) == (user, None)
    entry = AuditLog.objects.filter(worker=worker, action="CREATE").first()
    assert entry.object_repr == str(consent) and "Họ" not in entry.object_repr


def test_ky_giay_bat_buoc_tep_bien_ban_loai_dong_y_cua_chinh_ho_so():
    worker = make_worker_in_status(VS.DRAFT)
    other = make_worker_in_status(VS.DRAFT)
    user = make_user("HR_STAFF")
    today = timezone.localdate()
    kw = {"consented": True, "consent_date": today, "method": "PAPER"}
    with pytest.raises(WorkerDataError):  # không có tệp
        services.record_consent(user, worker, **kw)
    with pytest.raises(WorkerDataError):  # sai loại tài liệu
        services.record_consent(user, worker, document=make_document(worker, "CV"), **kw)
    with pytest.raises(WorkerDataError):  # tệp của hồ sơ khác
        services.record_consent(user, worker, document=make_document(other, "CONSENT"), **kw)
    with pytest.raises(WorkerDataError):  # điện tử mà lại đính kèm tệp
        services.record_consent(
            user,
            worker,
            document=make_document(worker, "CONSENT"),
            **{**kw, "method": "ELECTRONIC"},
        )
    doc = make_document(worker, "CONSENT")
    consent = services.record_consent(user, worker, document=doc, **kw)
    assert consent.document == doc


def test_dong_y_ngay_tuong_lai_hoac_thieu_ngay_bi_chan():
    worker = make_worker_in_status(VS.DRAFT)
    user = make_user("HR_STAFF")
    with pytest.raises(WorkerDataError):
        services.record_consent(
            user,
            worker,
            consented=True,
            consent_date=timezone.localdate() + datetime.timedelta(days=1),
            method="ELECTRONIC",
        )
    with pytest.raises(WorkerDataError):
        services.record_consent(
            user, worker, consented=True, consent_date=None, method="ELECTRONIC"
        )


@pytest.mark.parametrize("status", [VS.PENDING, VS.REJECTED, VS.ARCHIVED])
def test_dong_y_khong_ghi_duoc_khi_ho_so_bi_khoa(status):
    worker = make_worker_in_status(status)
    with pytest.raises(PermissionDenied):
        services.record_consent(
            make_user("ADMIN"),
            worker,
            consented=True,
            consent_date=timezone.localdate(),
            method="ELECTRONIC",
        )


def test_viewer_khong_ghi_nhan_duoc_dong_y():
    worker = make_worker_in_status(VS.DRAFT)
    with pytest.raises(PermissionDenied):
        services.record_consent(
            make_user("VIEWER"),
            worker,
            consented=True,
            consent_date=timezone.localdate(),
            method="ELECTRONIC",
        )


def test_rut_dong_y_ban_moi_nhat_la_khong_thi_khong_gui_duyet_duoc():
    worker = make_worker_in_status(VS.DRAFT)
    services.record_consent(
        make_user("HR_STAFF"),
        worker,
        consented=False,
        consent_date=timezone.localdate(),
        method="ELECTRONIC",
    )
    assert DataConsent.objects.filter(worker=worker).count() == 2  # lịch sử giữ cả hai
    with pytest.raises(TransitionError) as exc:
        workflow.transition(worker, VS.PENDING, worker.created_by)
    assert [i.field for i in exc.value.issues] == ["consent"]


# ===== Mở lại hồ sơ ==========================================================================
def catalog():
    return (
        Position.objects.get_or_create(name="Công nhân giả")[0],
        ApplicationSource.objects.get_or_create(name="Nguồn giả")[0],
    )


@pytest.mark.parametrize("role", EDITORS)
def test_mo_lai_ve_nhap_va_tao_ung_tuyen_moi_giu_ma_nv(role):
    worker = make_worker_in_status(VS.ARCHIVED)
    Worker.objects.filter(pk=worker.pk).update(employee_code="CN-00042")
    position, source = catalog()
    user = make_user(role)
    app = services.reopen_worker(user, worker, position=position, source=source)
    worker = fresh(worker)
    assert worker.verification_status == VS.DRAFT and worker.employee_code == "CN-00042"
    assert (app.status, app.created_by, app.position, app.source) == ("NEW", user, position, source)
    assert Application.objects.filter(worker=worker).count() == 1
    actions = list(AuditLog.objects.filter(worker=worker).values_list("action", flat=True))
    assert "REOPEN" in actions and actions[0] == "CREATE"  # ứng tuyển mới ghi sau REOPEN


def test_mo_lai_chi_voi_ho_so_luu_tru_va_chua_an_danh():
    position, source = catalog()
    for status in (VS.DRAFT, VS.PENDING, VS.VERIFIED, VS.REJECTED):
        worker = make_worker_in_status(status)
        with pytest.raises(TransitionError):
            services.reopen_worker(make_user("HR_STAFF"), worker, position=position, source=source)
    anonymized = make_worker_in_status(VS.ARCHIVED)
    Worker.objects.filter(pk=anonymized.pk).update(anonymized_at=timezone.now())
    with pytest.raises(TransitionError, match="ẩn danh"):
        services.reopen_worker(make_user("ADMIN"), anonymized, position=position, source=source)
    assert not Application.objects.exists()


def test_mo_lai_viewer_bi_chan_va_danh_muc_ngung_dung_bi_tu_choi():
    worker = make_worker_in_status(VS.ARCHIVED)
    position, source = catalog()
    with pytest.raises(PermissionDenied):
        services.reopen_worker(make_user("VIEWER"), worker, position=position, source=source)
    Position.objects.filter(pk=position.pk).update(is_active=False)
    position.refresh_from_db()
    with pytest.raises(WorkerDataError):
        services.reopen_worker(make_user("HR_STAFF"), worker, position=position, source=source)
    with pytest.raises(WorkerDataError):
        services.reopen_worker(make_user("HR_STAFF"), worker, position=None, source=source)
    assert fresh(worker).verification_status == VS.ARCHIVED  # không đổi gì
