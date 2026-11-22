"""apps.audit.services.log(): tách trường cá nhân theo PERSONAL_FIELDS (Phase 2 bước 4)."""

import datetime
import decimal
import json

import pytest
from django.apps import apps
from django.db import connection, transaction
from django.test import RequestFactory

from apps.audit.models import AuditLog, AuditPersonalValue
from apps.audit.personal_fields import (
    COLLECTION_PREFIX,
    LOGICAL_TO_ATTR,
    PERSONAL_FIELDS,
    SINGLE_PREFIX,
    attr_name,
    field_label,
)
from apps.audit.services import PERSONAL_PLACEHOLDER, log
from apps.core.models import Department, Position, Section
from apps.employment.models import Employment
from apps.recruitment.models import Application
from apps.workers.models import EmergencyContact, IdentityDocument
from tests.factories import fake_id, make_user, make_worker

pytestmark = pytest.mark.django_db


def _pv(entry):
    return {p.field_name: (p.old_value_enc, p.new_value_enc) for p in entry.personal_values.all()}


def test_truong_ca_nhan_khong_lo_gia_tri_ro_trong_changes():
    w = make_worker()
    e = log(
        "UPDATE",
        user=make_user(),
        obj=w,
        changes={
            "full_name": ("Zqx Tên Cũ", "Zqx Tên Mới"),
            "phone": ("0911000111", "0911000222"),
            "verification_status": ("DRAFT", "PENDING"),
        },
    )
    assert e.changes == {
        "full_name": PERSONAL_PLACEHOLDER,
        "phone": PERSONAL_PLACEHOLDER,
        "verification_status": ["DRAFT", "PENDING"],
    }
    # Không giá trị rõ nào xuất hiện ở bất kỳ cột nào của dòng nhật ký.
    dump = json.dumps(e.changes, ensure_ascii=False) + e.object_repr + e.note
    for rõ in ("Zqx", "0911000111", "0911000222"):
        assert rõ not in dump
    assert _pv(e) == {
        "full_name": ("Zqx Tên Cũ", "Zqx Tên Mới"),
        "phone": ("0911000111", "0911000222"),
    }


def test_gia_tri_ca_nhan_luu_ma_hoa_trong_csdl():
    w = make_worker()
    log("UPDATE", obj=w, changes={"full_name": (None, "Zqx Bí Mật")})
    with connection.cursor() as cur:
        cur.execute("SELECT old_value_enc, new_value_enc FROM audit_auditpersonalvalue")
        old, new = cur.fetchone()
        cur.execute("SELECT changes::text FROM audit_auditlog")
        changes_raw = cur.fetchone()[0]
    assert old is None and "Zqx" not in new and "Zqx" not in changes_raw


def test_giay_to_dung_ten_logic_va_tien_to_identity():
    w = make_worker()
    ident = IdentityDocument.objects.create(worker=w, id_number_enc=fake_id())
    so_cu, so_moi = fake_id(), fake_id()
    e = log(
        "UPDATE",
        obj=ident,
        changes={
            "id_number": (so_cu, so_moi),
            "permanent_address": ("1 Đường Giả", "2 Đường Giả"),
            "id_doc_type": ("CCCD_2016", "CCCD_2021"),
        },
    )
    assert e.object_type == "workers.IdentityDocument" and e.worker == w
    assert e.changes == {
        "identity.id_number": PERSONAL_PLACEHOLDER,
        "identity.permanent_address": PERSONAL_PLACEHOLDER,
        "identity.id_doc_type": ["CCCD_2016", "CCCD_2021"],
    }
    assert _pv(e)["identity.id_number"] == (so_cu, so_moi)
    assert so_cu not in json.dumps(e.changes) and e.object_repr == f"Giấy tờ của {w.worker_code}"


def test_lien_he_khan_cap_dung_ten_theo_dong():
    w = make_worker()
    c = EmergencyContact.objects.create(
        worker=w, full_name="Zqx Liên Hệ", relationship="Anh", phone="0922333444"
    )
    e = log("UPDATE", obj=c, changes={"phone": ("0922333444", "0922333555")})
    name = f"emergency_contacts[{c.pk}].phone"
    assert e.changes == {name: PERSONAL_PLACEHOLDER}
    assert _pv(e) == {name: ("0922333444", "0922333555")}
    assert e.worker == w and "Zqx" not in e.object_repr


def test_kieu_gia_tri_ngay_so_thap_phan_none():
    w = make_worker()
    pos = Position.objects.create(name="CD")
    from apps.core.models import ApplicationSource

    app = Application.objects.create(
        worker=w,
        position=pos,
        source=ApplicationSource.objects.create(name="N"),
        applied_date=datetime.date(2026, 1, 1),
        created_by=make_user(),
    )
    e = log(
        "UPDATE",
        obj=app,
        changes={
            "expected_salary": (None, decimal.Decimal("7500000")),
            "available_date": (None, datetime.date(2026, 5, 17)),
            "status": ("NEW", "SCREENING"),
        },
    )
    assert _pv(e) == {f"applications[{app.pk}].expected_salary": (None, "7500000")}
    assert e.changes[f"applications[{app.pk}].status"] == ["NEW", "SCREENING"]
    # available_date không phải trường cá nhân: ghi ISO, không mã hóa
    assert e.changes[f"applications[{app.pk}].available_date"] == [None, "2026-05-17"]


def test_ngay_sinh_cua_ho_so_la_ca_nhan_ghi_iso_ma_hoa():
    w = make_worker()
    e = log("UPDATE", obj=w, changes={"date_of_birth": (None, datetime.date(1990, 5, 17))})
    assert e.changes == {"date_of_birth": PERSONAL_PLACEHOLDER}
    assert _pv(e) == {"date_of_birth": (None, "1990-05-17")}


def test_employment_tien_to_va_truong_khong_ca_nhan():
    w = make_worker()
    sec = Section.objects.create(department=Department.objects.create(name="P"), name="B")
    emp = Employment.objects.create(
        worker=w,
        received_date=datetime.date(2026, 1, 1),
        start_date=datetime.date(2026, 1, 2),
        section=sec,
        position=Position.objects.create(name="X"),
    )
    e = log(
        "UPDATE",
        obj=emp,
        changes={"work_status": ("AWAITING", "ACTIVE"), "resign_note": ("", "Zqx ghi chú")},
    )
    assert e.changes == {
        "employment.work_status": ["AWAITING", "ACTIVE"],
        "employment.resign_note": PERSONAL_PLACEHOLDER,
    }
    assert e.worker == w


def test_nguoi_thuc_hien_va_he_thong():
    user = make_user(username="hr_giaquyen")
    w = make_worker()
    e1 = log("CREATE", user=user, obj=w)
    assert (e1.user, e1.actor_label) == (user, "hr_giaquyen")
    e2 = log("INTAKE_EXPIRE", obj=w)
    assert e2.user is None and e2.actor_label == "Hệ thống"
    assert e1.object_repr == w.worker_code and e1.object_id == str(w.pk) and e1.worker == w


def test_dia_chi_ip_tu_request():
    request = RequestFactory().get("/", REMOTE_ADDR="10.1.2.3")
    e = log("VIEW_FULL_ID", obj=make_worker(), request=request)
    assert e.ip_address == "10.1.2.3"
    assert log("CREATE", obj=make_worker()).ip_address is None


def test_su_kien_khong_co_doi_tuong():
    e = log(
        "EXPORT",
        user=make_user(),
        object_type="reports.Report",
        object_id="phong-ban",
        object_repr="Báo cáo theo phòng ban",
        note="Bộ lọc: tháng 11/2026",
    )
    assert (e.object_type, e.object_repr, e.worker) == (
        "reports.Report",
        "Báo cáo theo phòng ban",
        None,
    )
    with pytest.raises(ValueError):
        log("EXPORT")


def test_loi_lap_trinh_bi_chan():
    w = make_worker()
    with pytest.raises(ValueError, match="không hợp lệ"):
        log("KHONG_CO", obj=w)
    with pytest.raises(ValueError, match="không có trường"):
        log("UPDATE", obj=w, changes={"id_number_enc": ("a", "b")})  # phải dùng tên logic
    with pytest.raises(ValueError, match="không có trường"):
        log("UPDATE", obj=w, changes={"ten_sai": ("a", "b")})
    assert AuditLog.objects.count() == 0


def test_ghi_trong_mot_giao_dich_rollback_mat_ca_hai():
    w = make_worker()
    with pytest.raises(RuntimeError), transaction.atomic():
        log("UPDATE", obj=w, changes={"full_name": ("a", "b")})
        raise RuntimeError("lỗi sau khi ghi nhật ký")
    assert AuditLog.objects.count() == 0
    assert AuditPersonalValue.objects.count() == 0


def test_loi_giua_chung_khong_de_lai_dong_nhat_ky_mo_coi(monkeypatch):
    w = make_worker()

    def hong(*args, **kwargs):
        raise RuntimeError("hỏng khi ghi giá trị cá nhân")

    monkeypatch.setattr(AuditPersonalValue.objects, "create", hong)
    with pytest.raises(RuntimeError):
        log("UPDATE", obj=w, changes={"full_name": ("a", "b")})
    assert AuditLog.objects.count() == 0


# --- PERSONAL_FIELDS khớp models.md mục 3.2 --------------------------------------------------
def test_personal_fields_dung_ten_logic_va_anh_xa():
    assert PERSONAL_FIELDS["workers.IdentityDocument"] == {
        "id_number",
        "old_id_number",
        "issue_date",
        "issue_place",
        "expiry_date",
        "hometown",
        "birth_registration_place",
        "permanent_address",
    }
    assert LOGICAL_TO_ATTR == {
        "workers.IdentityDocument": {
            "id_number": "id_number_enc",
            "old_id_number": "old_id_number_enc",
            "permanent_address": "permanent_address_enc",
        }
    }
    assert all(not n.endswith("_enc") for names in PERSONAL_FIELDS.values() for n in names)


def test_moi_ten_logic_ung_voi_mot_truong_that_cua_model():
    for label, names in PERSONAL_FIELDS.items():
        model = apps.get_model(label)
        for name in names:
            model._meta.get_field(attr_name(label, name))


def test_ten_luu_tru_nhu_models_md():
    assert field_label("workers.Worker", "full_name") == "full_name"
    assert field_label("workers.IdentityDocument", "id_number") == "identity.id_number"
    assert field_label("workers.EmergencyContact", "phone", pk=2) == "emergency_contacts[2].phone"
    assert set(SINGLE_PREFIX) | set(COLLECTION_PREFIX) <= set(PERSONAL_FIELDS) | {
        "employment.Contract"
    }
