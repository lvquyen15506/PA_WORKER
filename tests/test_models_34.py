"""34 model đúng thiết kế (models.md mục 1, erd.md): tên bảng, cột mã hóa/băm, ràng buộc."""

import datetime
import io
from pathlib import Path

import pytest
from django.apps import apps
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.audit.models import AuditLog, AuditPersonalValue
from apps.core.crypto import EncryptedTextField, compute_id_hash
from apps.core.models import Department, DocumentType, Position, Section, Team
from apps.core.models_base import AppendOnlyError
from apps.core.text import compute_name_search
from apps.documents.models import WorkerDocument
from apps.employment.models import Contract, Employment, EmploymentHistory
from apps.intake.models import IntakeSession
from apps.recruitment.models import Application
from apps.workers.models import IdentityDocument, StatusChange, Worker
from tests.factories import fake_id, make_user, make_worker

pytestmark = pytest.mark.django_db

# Bảng ánh xạ ở models.md mục 1.
EXPECTED_TABLES = {
    "accounts_role", "accounts_user", "accounts_loginhistory",
    "audit_auditlog", "audit_auditpersonalvalue",
    "core_department", "core_section", "core_team", "core_position", "core_shift",
    "core_applicationsource", "core_educationlevel", "core_requireddocumentgroup",
    "core_documenttype", "core_systemsetting", "core_codesequence", "core_qrformat",
    "workers_worker", "workers_identitydocument", "workers_identityfieldsource",
    "workers_emergencycontact", "workers_dataconsent", "workers_statuschange",
    "workers_anonymizationrecord", "workers_anonymizationitem",
    "documents_workerdocument",
    "intake_intakesession",
    "recruitment_application", "recruitment_education", "recruitment_certificate",
    "recruitment_workexperience",
    "employment_employment", "employment_employmenthistory", "employment_contract",
}  # fmt: skip

# erd.md mục 5 "Mã hóa và băm".
EXPECTED_ENCRYPTED = {
    ("workers", "identitydocument", "id_number_enc"),
    ("workers", "identitydocument", "old_id_number_enc"),
    ("workers", "identitydocument", "permanent_address_enc"),
    ("intake", "intakesession", "result_enc"),
    ("audit", "auditpersonalvalue", "old_value_enc"),
    ("audit", "auditpersonalvalue", "new_value_enc"),
    ("core", "systemsetting", "key_check_enc"),
}
EXPECTED_HASH = {
    ("workers", "identitydocument", "id_number_hash"),
    ("core", "systemsetting", "key_check_hash"),
}


def _project_models():
    return [m for m in apps.get_models() if m._meta.app_label in {
        "accounts", "audit", "core", "workers", "documents", "intake", "recruitment", "employment",
    }]  # fmt: skip


def test_dung_34_model_dung_ten_bang():
    assert {m._meta.db_table for m in _project_models()} == EXPECTED_TABLES
    assert len(_project_models()) == 34


def test_cot_ma_hoa_va_bam_khop_erd():
    enc = {
        (m._meta.app_label, m._meta.model_name, f.name)
        for m in _project_models()
        for f in m._meta.get_fields()
        if isinstance(f, EncryptedTextField)
    }
    hashed = {
        (m._meta.app_label, m._meta.model_name, f.name)
        for m in _project_models()
        for f in m._meta.get_fields()
        if f.name.endswith("_hash")
    }
    assert enc == EXPECTED_ENCRYPTED
    assert hashed == EXPECTED_HASH


def test_migrations_khop_model():
    """Không còn thay đổi model chưa có migration (ném SystemExit nếu có)."""
    call_command("makemigrations", check=True, dry_run=True, stdout=io.StringIO())


def test_migrate_tu_db_trong_khong_co_vong_phu_thuoc():
    # Cơ sở dữ liệu test được dựng bằng migrate; có tới đây nghĩa là không có vòng phụ thuộc.
    assert Worker.objects.count() == 0


# --- name_search ------------------------------------------------------------------------
@pytest.mark.parametrize(
    "ten, ky_vong",
    [
        ("Nguyễn Văn Đức", "nguyen van duc"),
        ("  TRẦN   thị  ĐÀO ", "tran thi dao"),
        ("Đặng Quốc Việt", "dang quoc viet"),
        ("", ""),
    ],
)
def test_name_search_bo_dau(ten, ky_vong):
    assert compute_name_search(ten) == ky_vong


def test_worker_save_tinh_name_search_va_cap_nhat_updated_at():
    w = make_worker(full_name="Lê Thị Ánh")
    assert w.name_search == "le thi anh"
    w.full_name = "Phạm Văn Ơn"
    w.save()
    w.refresh_from_db()
    assert w.name_search == "pham van on"


def test_worker_touch_cap_nhat_updated_at():
    w = make_worker()
    Worker.objects.filter(pk=w.pk).update(updated_at=timezone.now() - datetime.timedelta(days=200))
    w.refresh_from_db()
    old = w.updated_at
    w.touch()
    w.refresh_from_db()
    assert w.updated_at > old


# --- ràng buộc duy nhất -----------------------------------------------------------------
def test_ma_ho_so_duy_nhat_ma_nhan_vien_cho_phep_nhieu_null():
    a, b = make_worker(), make_worker()
    assert a.employee_code is None and b.employee_code is None
    a.employee_code = "CN-00001"
    a.save()
    b.employee_code = "CN-00001"
    with pytest.raises(IntegrityError), transaction.atomic():
        b.save()
    with pytest.raises(IntegrityError), transaction.atomic():
        make_worker(worker_code=a.worker_code)


def test_so_dinh_danh_ma_hoa_va_bam_tu_dong():
    w = make_worker()
    so = fake_id()
    ident = IdentityDocument.objects.create(
        worker=w, id_number_enc=so, permanent_address_enc="1 Đường Giả, Phường Giả"
    )
    assert ident.id_number_hash == compute_id_hash(so)
    with connection.cursor() as cur:
        cur.execute(
            "SELECT id_number_enc, permanent_address_enc, id_number_hash "
            "FROM workers_identitydocument"
        )
        enc, addr, h = cur.fetchone()
    assert so not in enc and "Đường Giả" not in addr and h == compute_id_hash(so)
    ident.refresh_from_db()
    assert ident.id_number_enc == so


def test_tim_trung_theo_bam_va_chan_trung():
    so = fake_id()
    IdentityDocument.objects.create(worker=make_worker(), id_number_enc=so)
    assert IdentityDocument.objects.filter(id_number_hash=compute_id_hash(so)).count() == 1
    with pytest.raises(IntegrityError), transaction.atomic():
        IdentityDocument.objects.create(worker=make_worker(), id_number_enc=f" {so[:6]}-{so[6:]} ")


def test_nhieu_giay_to_khong_so_dinh_danh_duoc_phep():
    IdentityDocument.objects.create(worker=make_worker())
    IdentityDocument.objects.create(worker=make_worker(), id_number_enc="")
    assert IdentityDocument.objects.filter(id_number_hash=None).count() == 2


def test_status_change_va_employment_history_chi_them():
    w = make_worker()
    sc = StatusChange.objects.create(worker=w, from_status="", to_status="DRAFT")
    sc.reason = "x"
    with pytest.raises(AppendOnlyError):
        sc.save()
    with pytest.raises(AppendOnlyError):
        StatusChange.objects.update(reason="x")
    with pytest.raises(AppendOnlyError):
        sc.delete()
    eh = EmploymentHistory.objects.create(
        worker=w, change_type="ONBOARD", effective_date=datetime.date(2026, 1, 1)
    )
    with pytest.raises(AppendOnlyError):
        eh.delete()
    with pytest.raises(AppendOnlyError):
        EmploymentHistory.objects.all().delete()


# --- audit: trường worker ----------------------------------------------------------------
def test_auditlog_worker_tuy_chon_personal_value_bat_buoc_worker():
    log = AuditLog.objects.create(
        actor_label="Hệ thống", action="CREATE", object_type="x", object_id="1", object_repr="HS-1"
    )
    assert log.worker is None
    with pytest.raises(IntegrityError), transaction.atomic():
        AuditPersonalValue.objects.create(audit_log=log, field_name="phone")


# --- việc làm, hợp đồng -------------------------------------------------------------------
def _org():
    d = Department.objects.create(name="Sản xuất")
    s = Section.objects.create(department=d, name="Lắp ráp")
    t = Team.objects.create(section=s, name="Tổ 1")
    return d, s, t, Position.objects.create(name="Công nhân")


def _employment(worker, **kw):
    _, s, _, p = _org() if "section" not in kw else (None, None, None, kw["position"])
    data = {
        "worker": worker,
        "received_date": datetime.date(2026, 1, 1),
        "start_date": datetime.date(2026, 1, 5),
        "section": s,
        "position": p,
    }
    data.update(kw)
    return Employment.objects.create(**data)


def test_employment_mot_mot_va_phong_ban_suy_ra_tu_bo_phan():
    w = make_worker()
    e = _employment(w)
    assert e.work_status == "AWAITING"
    assert e.department.name == "Sản xuất"
    assert w.employment == e
    with pytest.raises(IntegrityError), transaction.atomic():
        Employment.objects.create(
            worker=w,
            received_date=datetime.date(2026, 1, 1),
            start_date=datetime.date(2026, 1, 1),
            section=e.section,
            position=e.position,
        )


def test_employment_application_mot_mot():
    w = make_worker()
    pos_app = Position.objects.create(name="Vị trí A")
    from apps.core.models import ApplicationSource

    app = Application.objects.create(
        worker=w,
        position=pos_app,
        source=ApplicationSource.objects.create(name="Nguồn A"),
        applied_date=datetime.date(2026, 1, 1),
        created_by=make_user(),
    )
    assert app.status == "NEW"
    e = _employment(w, application=app)
    w2 = make_worker()
    with pytest.raises(IntegrityError), transaction.atomic():
        Employment.objects.create(
            worker=w2,
            application=app,
            received_date=datetime.date(2026, 1, 1),
            start_date=datetime.date(2026, 1, 1),
            section=e.section,
            position=e.position,
        )


def test_employment_clean_to_thuoc_bo_phan_va_quan_ly_khac_minh():
    from django.core.exceptions import ValidationError

    w = make_worker()
    d, s, t, p = _org() if False else (None, None, None, None)
    dep = Department.objects.create(name="Kho")
    s1 = Section.objects.create(department=dep, name="Bộ phận 1")
    s2 = Section.objects.create(department=dep, name="Bộ phận 2")
    team_s2 = Team.objects.create(section=s2, name="Tổ x")
    pos = Position.objects.create(name="Công nhân")
    e = Employment(
        worker=w,
        received_date=datetime.date(2026, 1, 1),
        start_date=datetime.date(2026, 1, 1),
        section=s1,
        team=team_s2,
        position=pos,
        manager=w,
    )
    with pytest.raises(ValidationError) as exc:
        e.clean()
    assert set(exc.value.message_dict) == {"team", "manager"}
    e.team, e.manager, e.work_status = None, None, "RESIGNED"
    with pytest.raises(ValidationError) as exc:
        e.clean()
    assert set(exc.value.message_dict) == {"resign_date", "resign_reason"}


def _doc(worker, user, **kw):
    dt = DocumentType.objects.get(system_code="CONTRACT")
    return WorkerDocument.objects.create(
        worker=worker,
        document_type=dt,
        original_name="hd.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        uploaded_by=user,
        **kw,
    )


def test_hop_dong_hien_thi_ban_tai_lieu_hien_hanh():
    user = make_user()
    w = make_worker(created_by=user)
    v1 = _doc(w, user, is_current=False)
    v2 = _doc(w, user, version=2, replaces=v1, is_current=False)
    v3 = _doc(w, user, version=3, replaces=v2, is_current=True)
    c = Contract.objects.create(
        worker=w,
        contract_no="HD-001",
        contract_type="INDEFINITE",
        signed_date=datetime.date(2026, 1, 1),
        effective_date=datetime.date(2026, 1, 1),
        document=v1,
        created_by=user,
    )
    assert c.current_document == v3
    c.document = None
    assert c.current_document is None
    with pytest.raises(IntegrityError), transaction.atomic():  # mỗi bản chỉ bị thay một lần
        _doc(w, user, version=9, replaces=v1)
    with pytest.raises(IntegrityError), transaction.atomic():
        Contract.objects.create(
            worker=w,
            contract_no="HD-001",
            contract_type="INDEFINITE",
            signed_date=datetime.date(2026, 1, 1),
            effective_date=datetime.date(2026, 1, 1),
            created_by=user,
        )


def test_hop_dong_clean_han_het_han():
    from django.core.exceptions import ValidationError

    w = make_worker()
    base = {
        "worker": w,
        "contract_no": "HD-002",
        "signed_date": datetime.date(2026, 1, 1),
        "effective_date": datetime.date(2026, 1, 1),
    }
    with pytest.raises(ValidationError):
        Contract(contract_type="FIXED_TERM", **base).clean()  # thiếu hạn
    with pytest.raises(ValidationError):
        Contract(contract_type="FIXED_TERM", expiry_date=datetime.date(2026, 1, 1), **base).clean()
    Contract(contract_type="FIXED_TERM", expiry_date=datetime.date(2027, 1, 1), **base).clean()
    Contract(contract_type="INDEFINITE", **base).clean()


# --- phiên nhận diện -------------------------------------------------------------------------
def test_intake_session_close_xoa_tep_va_dong(settings):
    user = make_user()
    s = IntakeSession(created_by=user, expires_at=timezone.now() + datetime.timedelta(hours=24))
    s.result_enc = '{"qr": "999000000001|..."}'
    s.front_image.save("mat-truoc.jpg", ContentFile(b"\xff\xd8\xff"), save=False)
    s.cv_file.save("cv.pdf", ContentFile(b"%PDF-"), save=False)
    s.save()
    s.refresh_from_db()
    assert s.result_enc.startswith("{")
    paths = [Path(s.front_image.path), Path(s.cv_file.path)]
    assert all(p.exists() for p in paths)
    assert str(s.pk) in str(paths[0]) and "mat-truoc" not in paths[0].name
    with connection.cursor() as cur:
        cur.execute("SELECT result_enc FROM intake_intakesession")
        assert "999000000001" not in cur.fetchone()[0]
    s.close()
    assert not any(p.exists() for p in paths)
    assert not paths[0].parent.exists()
    assert IntakeSession.objects.count() == 0
