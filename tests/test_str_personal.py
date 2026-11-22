"""__str__ không được chứa giá trị của trường cá nhân (câu 30): __str__ dễ lọt vào
AuditLog.object_repr, log và trang lỗi."""

import datetime

import pytest
from django.apps import apps

from apps.audit.personal_fields import PERSONAL_FIELDS, attr_name
from apps.core.models import (
    ApplicationSource,
    ClientCompany,
    Department,
    EducationLevel,
    Position,
    Section,
)
from apps.employment.models import Contract, Employment, SalaryHistory, WorkAssignment
from apps.recruitment.models import Application, Certificate, Education, WorkExperience
from apps.workers.models import EmergencyContact, IdentityDocument
from tests.factories import fake_id, make_user, make_worker

pytestmark = pytest.mark.django_db

DOB = datetime.date(1990, 5, 17)


def _marker(model, field):
    return f"ZQX-{model}-{field}"


def _text_values(label, model_cls):
    """Giá trị giả có dấu hiệu nhận biết cho mọi trường chữ cá nhân của model."""
    values = {}
    for name in PERSONAL_FIELDS[label]:
        attr = attr_name(label, name)
        field = model_cls._meta.get_field(attr)
        if field.get_internal_type() in {"CharField", "TextField", "EmailField"}:
            values[attr] = _marker(label, name)[: field.max_length or 500]
    return values


def _build():
    user = make_user()
    worker = make_worker(
        created_by=user,
        date_of_birth=DOB,
        gender="MALE",
        email="zqx-email@example.invalid",
        current_address="ZQX-địa-chỉ-giả",
        skills="ZQX-kỹ-năng",
        note="ZQX-ghi-chú",
        full_name="Zqx Họ Tên Giả",
        phone="0911222333",
    )
    objs = {"workers.Worker": worker}

    def mk(label, cls, **extra):
        values = _text_values(label, cls)
        values.update(extra)
        obj = cls(**values)
        return obj

    objs["workers.IdentityDocument"] = IdentityDocument.objects.create(
        worker=worker,
        id_number_enc=fake_id(),
        old_id_number_enc="ZQX-cmnd-cu",
        permanent_address_enc="ZQX-thường-trú",
        issue_date=datetime.date(2021, 4, 9),
        expiry_date=datetime.date(2031, 4, 9),
        issue_place="ZQX-nơi-cấp",
        hometown="ZQX-quê",
        birth_registration_place="ZQX-khai-sinh",
    )
    objs["workers.EmergencyContact"] = mk(
        "workers.EmergencyContact", EmergencyContact, worker=worker, phone="0933444555"
    )
    objs["workers.EmergencyContact"].full_name = "Zqx Người Liên Hệ"
    objs["workers.EmergencyContact"].save()

    pos = Position.objects.create(name="Chức danh mẫu")
    app = Application.objects.create(
        worker=worker,
        position=pos,
        source=ApplicationSource.objects.create(name="Nguồn mẫu"),
        applied_date=datetime.date(2026, 3, 3),
        expected_salary=7500123,
        interview_notes="ZQX-phỏng-vấn",
        reject_reason="ZQX-lý-do",
        created_by=user,
    )
    objs["recruitment.Application"] = app
    level = EducationLevel.objects.get(name="THPT")
    for label, cls, extra in (
        ("recruitment.Education", Education, {"worker": worker, "education_level": level}),
        ("recruitment.Certificate", Certificate, {"worker": worker}),
        ("recruitment.WorkExperience", WorkExperience, {"worker": worker}),
    ):
        obj = mk(label, cls, **extra)
        obj.save()
        objs[label] = obj

    section = Section.objects.create(
        department=Department.objects.create(name="Phòng mẫu"), name="BP"
    )
    emp = Employment.objects.create(
        worker=worker,
        received_date=datetime.date(2026, 1, 1),
        start_date=datetime.date(2026, 1, 2),
        section=section,
        position=pos,
        resign_note="ZQX-ghi-chú-nghỉ",
    )
    objs["employment.Employment"] = emp
    objs["employment.Contract"] = Contract.objects.create(
        worker=worker,
        contract_no="HD-ZQX-1",
        contract_type="INDEFINITE",
        signed_date=datetime.date(2026, 1, 1),
        effective_date=datetime.date(2026, 1, 1),
        note="ZQX-ghi-chú-hợp-đồng",
        created_by=user,
    )
    # v1.1: đợt làm việc và lương.
    assignment = WorkAssignment.objects.create(
        worker=worker,
        client_company=ClientCompany.objects.create(name="Công ty Mẫu", location="Tỉnh Mẫu"),
        position=pos,
        start_date=datetime.date(2026, 2, 1),
        note="ZQX-ghi-chú-đợt",
        created_by=user,
    )
    objs["employment.WorkAssignment"] = assignment
    objs["employment.SalaryHistory"] = SalaryHistory.objects.create(
        assignment=assignment,
        worker=worker,
        monthly_salary_enc="7654321",
        client_unit_price_enc="9876543",
        effective_date=datetime.date(2026, 2, 1),
        reason="ZQX-lý-do-lương",
        created_by=user,
    )
    return objs


def _forbidden_values(obj, label):
    """Mọi giá trị cá nhân của đối tượng dưới dạng chuỗi (cả định dạng ngày dd/mm/yyyy)."""
    out = []
    for name in PERSONAL_FIELDS[label]:
        value = getattr(obj, attr_name(label, name))
        if value in (None, ""):
            continue
        out.append(str(value))
        if isinstance(value, datetime.date):
            out.append(value.strftime("%d/%m/%Y"))
    return out


def test_moi_model_co_truong_ca_nhan_deu_duoc_kiem_tra():
    objs = _build()
    assert set(objs) == set(PERSONAL_FIELDS)
    for label in PERSONAL_FIELDS:  # mọi nhãn model tồn tại, mọi tên trường tồn tại
        model = apps.get_model(label)
        for name in PERSONAL_FIELDS[label]:
            model._meta.get_field(attr_name(label, name))


def test_str_khong_chua_gia_tri_ca_nhan():
    objs = _build()
    for label, obj in objs.items():
        text = str(obj)
        assert text, label
        for value in _forbidden_values(obj, label):
            assert value not in text, f"{label}: __str__ chứa giá trị cá nhân {value!r}"


def test_str_dung_ma_ho_so():
    objs = _build()
    code = objs["workers.Worker"].worker_code
    assert str(objs["workers.Worker"]) == code
    assert str(objs["workers.EmergencyContact"]).startswith(code)
    assert "học vấn" in str(objs["recruitment.Education"])
    assert "chứng chỉ" in str(objs["recruitment.Certificate"])
    assert "kinh nghiệm" in str(objs["recruitment.WorkExperience"])


def test_user_str_la_ten_dang_nhap_khong_phai_ho_ten():
    user = make_user(username="nv_giaquyen")
    user.full_name = "Zqx Họ Tên Nhân Viên"
    assert str(user) == "nv_giaquyen"
