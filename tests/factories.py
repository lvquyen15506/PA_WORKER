"""Hàm dựng dữ liệu giả cho test. Mọi số CCCD giả bắt đầu bằng 999, tên là tên hư cấu."""

import contextlib
import datetime
import itertools
from unittest import mock

from apps.accounts.models import Role, User
from apps.workers.models import Worker

_seq = itertools.count(1)


PASSWORD = "Mk123456a"  # mật khẩu giả dùng trong test


def make_user(role="HR_STAFF", username=None, password=PASSWORD, must_change=False, **kwargs):
    n = next(_seq)
    user = User(
        username=username or f"user{n}",
        full_name=f"Người Dùng Giả {n}",
        role=Role.objects.get(code=role),
        must_change_password=must_change,
        **kwargs,
    )
    user.set_password(password)
    user.save()
    return user


def login_client(user, **client_kwargs):
    """Client đã đăng nhập bằng chính trang đăng nhập (không bỏ qua middleware)."""
    from django.test import Client

    client = Client(**client_kwargs)
    response = client.post("/dang-nhap/", {"username": user.username, "password": PASSWORD})
    assert response.status_code == 302, "đăng nhập thử nghiệm thất bại"
    return client


def make_worker(created_by=None, **kwargs):
    n = next(_seq)
    defaults = {
        "worker_code": f"HS-TEST-{n:05d}",
        "full_name": f"Nguyễn Văn Giả {n}",
        "phone": f"09{n:08d}"[:10],
        "created_by": created_by or make_user(),
    }
    defaults.update(kwargs)
    return Worker.objects.create(**defaults)


def fake_id(n=None):
    """Số CCCD giả: 999 + 9 chữ số."""
    return f"999{(n if n is not None else next(_seq)):09d}"


def make_worker_full(created_by=None, **kwargs):
    """Hồ sơ đủ mọi trường bắt buộc để gửi duyệt (models.md mục 4.3), trạng thái Nháp.

    Ghi dòng thời gian "tạo hồ sơ" qua record_creation như dịch vụ thật.
    """
    from apps.core.choices import ConsentMethod, Gender, IdDocType
    from apps.workers.models import DataConsent, EmergencyContact, IdentityDocument
    from apps.workers.workflow import record_creation

    creator = created_by or make_user("HR_STAFF")
    fields = {
        "date_of_birth": datetime.date(1995, 5, 20),
        "gender": Gender.MALE,
        "current_address": "Số 1 đường giả, quận giả",
    }
    fields.update(kwargs)
    worker = make_worker(created_by=creator, **fields)
    IdentityDocument.objects.create(
        worker=worker, id_doc_type=IdDocType.CCCD_2021, id_number_enc=fake_id()
    )
    EmergencyContact.objects.create(
        worker=worker, full_name="Người Thân Giả", relationship="Anh", phone="0912345678"
    )
    DataConsent.objects.create(
        worker=worker,
        consented=True,
        consent_date=datetime.date.today(),
        method=ConsentMethod.ELECTRONIC,
        recorded_by=creator,
    )
    record_creation(worker, creator)
    return worker


def advance_to(worker, status, *, submitter=None, reviewer=None):
    """Đưa hồ sơ Nháp tới `status` bằng chính workflow.transition (không gán trực tiếp).

    Đường đi: PENDING = gửi duyệt; NEEDS_INFO/VERIFIED/REJECTED = gửi duyệt rồi QL xử lý;
    ARCHIVED = Lưu trữ thẳng từ Nháp. Người gửi mặc định là người tạo hồ sơ, người duyệt là
    một Quản lý nhân sự mới (khác người tạo).
    """
    from apps.core.choices import VerificationStatus as VS
    from apps.workers.workflow import transition

    status = VS(status)
    submitter = submitter or worker.created_by
    if status == VS.DRAFT:
        return worker
    if status == VS.ARCHIVED:
        transition(worker, VS.ARCHIVED, submitter)
        return worker
    transition(worker, VS.PENDING, submitter)
    if status != VS.PENDING:
        reviewer = reviewer or make_user("HR_MANAGER")
        transition(worker, status, reviewer, reason="Lý do thử")
    return worker


SENSITIVE = {
    "id_number": "999314159265",
    "old_id_number": "999271828",
    "permanent_address": "Số 9 ngõ Bí Mật, phường Thường Trú Giả",
    "hometown": "Làng Quê Quán Kín",
    "birth_registration_place": "Xã Nơi Khai Sinh Kín",
    "salary": 13579246,
    "salary_text": "13.579.246",
    "file_name": "TenTepRieng.pdf",
}


def make_sensitive_worker(status="DRAFT"):
    """Hồ sơ đủ trường, mọi giá trị Viewer không được thấy (câu 13) là chuỗi dễ nhận ra, kèm
    ứng tuyển có mức lương, học vấn, tài liệu và hợp đồng."""
    from apps.core.models import EducationLevel
    from apps.recruitment.models import Application, Education
    from apps.workers.models import IdentityDocument

    worker = make_worker_full()
    identity = IdentityDocument.objects.get(worker=worker)
    identity.id_number_enc = SENSITIVE["id_number"]
    identity.old_id_number_enc = SENSITIVE["old_id_number"]
    identity.permanent_address_enc = SENSITIVE["permanent_address"]
    identity.hometown = SENSITIVE["hometown"]
    identity.birth_registration_place = SENSITIVE["birth_registration_place"]
    identity.issue_place = "Cục Cấp Giả"
    identity.save()
    application = make_application(worker, "NEW")
    Application.objects.filter(pk=application.pk).update(expected_salary=SENSITIVE["salary"])
    Education.objects.create(
        worker=worker,
        education_level=EducationLevel.objects.get(rank=4),
        school_name="Trường Giả",
        start_year=2010,
        end_year=2013,
    )
    make_document(worker, "CCCD_FRONT", name=SENSITIVE["file_name"])
    return advance_to(worker, status)


def make_worker_in_status(status, **kwargs):
    """Hồ sơ đủ trường, đã đưa tới `status` bằng workflow (người tạo/gửi là một HR)."""
    return advance_to(make_worker_full(**kwargs), status)


@contextlib.contextmanager
def freeze_time(moment):
    """Mọi timezone.now() trong khối này trả `moment` (aware). Dùng để tạo bản ghi "trong quá
    khứ" (auto_now_add) mà không sửa dữ liệu chỉ-thêm."""
    with mock.patch("django.utils.timezone.now", return_value=moment):
        yield


def at(year, month, day, hour=10, minute=0):
    """Thời điểm giờ Việt Nam (aware)."""
    from django.utils import timezone

    return timezone.make_aware(datetime.datetime(year, month, day, hour, minute))


def make_application(worker, status="NEW", result_date=None, applied_date=None, created_by=None):
    from apps.core.models import ApplicationSource, Position
    from apps.recruitment.models import Application

    position, _ = Position.objects.get_or_create(name="Chức danh test")
    source, _ = ApplicationSource.objects.get_or_create(name="Nguồn test")
    return Application.objects.create(
        worker=worker,
        position=position,
        source=source,
        applied_date=applied_date or datetime.date.today(),
        status=status,
        result_date=result_date,
        created_by=created_by or worker.created_by,
    )


def make_document(worker, type_code="CCCD_FRONT", *, content=b"%PDF-1.4 test", name="a.pdf", **kw):
    """Tài liệu có tệp thật trong kho riêng (PRIVATE_MEDIA_ROOT của test)."""
    from django.core.files.base import ContentFile

    from apps.core.models import DocumentType
    from apps.documents.models import WorkerDocument

    doc = WorkerDocument(
        worker=worker,
        document_type=DocumentType.objects.get(system_code=type_code),
        original_name=name,
        mime_type="application/pdf",
        size_bytes=len(content),
        uploaded_by=worker.created_by,
        **kw,
    )
    doc.stored_file.save(name, ContentFile(content), save=False)
    doc.save()
    return doc


def make_employment(worker, work_status="ACTIVE"):
    """Thông tin làm việc tối thiểu cho test (danh mục tạo sẵn nếu chưa có)."""
    from apps.core.models import Department, Position, Section
    from apps.employment.models import Employment

    department, _ = Department.objects.get_or_create(name="Phòng ban test")
    section, _ = Section.objects.get_or_create(department=department, name="Bộ phận test")
    position, _ = Position.objects.get_or_create(name="Chức danh test")
    today = datetime.date.today()
    return Employment.objects.create(
        worker=worker,
        received_date=today,
        start_date=today,
        section=section,
        position=position,
        work_status=work_status,
    )
