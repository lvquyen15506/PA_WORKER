"""Model v1.1 (câu 39–48; models.md mục 3.9): công ty khách, đợt làm việc, lịch sử lương.

Kiểm tra ở tầng model và CSDL: ràng buộc một đợt mở, ngày kết thúc, lương chỉ thêm (model,
QuerySet, trigger PostgreSQL), lương mã hóa thật trong CSDL (đọc SQL thô), bộ phận không bắt
buộc, loại tài liệu "Bản cam kết", ẩn danh hóa xóa lịch sử lương và ghi chú của đợt.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction

from apps.audit.models import AuditLog
from apps.audit.services import log
from apps.core.models import ClientCompany, Department, DocumentType, Position, Section, Team
from apps.core.models_base import AppendOnlyError
from apps.employment.models import Employment, SalaryHistory, WorkAssignment
from tests.factories import make_employment, make_worker
from tests.test_anonymize import rich_worker, run

pytestmark = pytest.mark.django_db
D = datetime.date
SALARY = "8765432"
PRICE = "11223344"
JAN_1 = D(2026, 1, 1)


def company(name="Công ty Mẫu A", location="Tỉnh Mẫu"):
    return ClientCompany.objects.create(name=name, location=location)


def default_company():
    return ClientCompany.objects.get_or_create(name="Công ty Mặc định", location="Tỉnh Mẫu")[0]


def assignment(worker, *, start=JAN_1, end=None, client=None, note=""):
    return WorkAssignment.objects.create(
        worker=worker,
        client_company=client or default_company(),
        position=Position.objects.get_or_create(name="Công nhân lắp ráp")[0],
        start_date=start,
        end_date=end,
        note=note,
        created_by=worker.created_by,
    )


def salary(a, *, amount=SALARY, price=PRICE, day=JAN_1):
    return SalaryHistory.objects.create(
        assignment=a,
        worker=a.worker,
        monthly_salary_enc=amount,
        client_unit_price_enc=price,
        effective_date=day,
        reason="Thiết lập ban đầu",
        created_by=a.worker.created_by,
    )


# ----- Công ty khách --------------------------------------------------------------------------
def test_cong_ty_khach_moi_dia_diem_mot_dong_va_khong_trung_ten_dia_diem():
    company("Công ty Mẫu A", "Tỉnh Một")
    company("Công ty Mẫu A", "Tỉnh Hai")  # cùng tên, khác địa điểm: được
    with pytest.raises(IntegrityError), transaction.atomic():
        company("Công ty Mẫu A", "Tỉnh Một")
    assert str(ClientCompany.objects.first()).startswith("Công ty Mẫu A – ")


# ----- Đợt làm việc ---------------------------------------------------------------------------
def test_moi_cong_nhan_toi_da_mot_dot_dang_mo():
    worker = make_worker()
    assignment(worker, start=D(2026, 1, 1))
    with pytest.raises(IntegrityError), transaction.atomic():
        assignment(worker, start=D(2026, 3, 1))
    # Đợt đã kết thúc thì không tính là đợt mở.
    assignment(worker, start=D(2025, 1, 1), end=D(2025, 6, 30))
    assert WorkAssignment.objects.filter(worker=worker).count() == 2


def test_hai_cong_nhan_moi_nguoi_mot_dot_mo_duoc():
    assignment(make_worker())
    assignment(make_worker())
    assert WorkAssignment.objects.filter(end_date__isnull=True).count() == 2


def test_ngay_ket_thuc_khong_truoc_ngay_bat_dau():
    worker = make_worker()
    assignment(worker, start=D(2026, 1, 1), end=D(2026, 1, 1))  # cùng ngày: được (làm 1 ngày)
    with pytest.raises(IntegrityError), transaction.atomic():
        assignment(worker, start=D(2026, 2, 1), end=D(2026, 1, 31))


# ----- Lịch sử lương: chỉ thêm ----------------------------------------------------------------
def test_luong_khong_sua_khong_xoa_qua_model_va_queryset():
    row = salary(assignment(make_worker()))
    row.reason = "sửa"
    with pytest.raises(AppendOnlyError):
        row.save()
    with pytest.raises(AppendOnlyError):
        SalaryHistory.objects.update(reason="x")
    with pytest.raises(AppendOnlyError):
        SalaryHistory.objects.bulk_update([row], ["reason"])
    assert SalaryHistory.objects.get(pk=row.pk).reason == "Thiết lập ban đầu"


def test_trigger_postgres_chan_update_luong_bang_sql_tho():
    salary(assignment(make_worker()))
    assert connection.vendor == "postgresql"
    with pytest.raises(DatabaseError, match="chỉ được thêm"), transaction.atomic():
        with connection.cursor() as cur:
            cur.execute("UPDATE employment_salaryhistory SET reason = 'x'")


def test_luong_va_don_gia_ma_hoa_that_trong_csdl():
    row = salary(assignment(make_worker()))
    with connection.cursor() as cur:
        cur.execute(
            "SELECT monthly_salary_enc, client_unit_price_enc FROM employment_salaryhistory"
            " WHERE id = %s",
            [row.pk],
        )
        raw = cur.fetchone()
    assert SALARY not in raw[0] and PRICE not in raw[1]
    assert raw[0].startswith("gAAAA")  # dạng Fernet
    fresh = SalaryHistory.objects.get(pk=row.pk)
    assert (fresh.monthly_salary, fresh.client_unit_price) == (int(SALARY), int(PRICE))


def test_don_gia_duoc_de_trong():
    row = salary(assignment(make_worker()), price=None)
    assert SalaryHistory.objects.get(pk=row.pk).client_unit_price is None


def test_nhat_ky_luong_khong_ghi_so_ro_vao_changes():
    row = salary(assignment(make_worker()))
    entry = log(
        "CREATE",
        user=row.created_by,
        obj=row,
        changes={"monthly_salary": (None, SALARY), "client_unit_price": (None, PRICE)},
    )
    entry = AuditLog.objects.get(pk=entry.pk)
    text = str(entry.changes)
    assert SALARY not in text and PRICE not in text
    names = set(entry.personal_values.values_list("field_name", flat=True))
    assert names == {
        f"salary_history[{row.pk}].monthly_salary",
        f"salary_history[{row.pk}].client_unit_price",
    }
    with connection.cursor() as cur:
        cur.execute("SELECT new_value_enc FROM audit_auditpersonalvalue")
        assert all(SALARY not in v and PRICE not in v for (v,) in cur.fetchall())


# ----- Bộ phận không bắt buộc (câu 48) --------------------------------------------------------
def test_employment_khong_co_bo_phan_luu_duoc_phong_ban_rong():
    worker = make_worker()
    emp = Employment.objects.create(
        worker=worker,
        received_date=D(2026, 1, 1),
        start_date=D(2026, 1, 1),
        position=Position.objects.create(name="Chức danh X"),
    )
    assert emp.section is None and emp.department is None
    emp.full_clean()


def test_co_to_ma_khong_co_bo_phan_thi_loi():
    emp = make_employment(make_worker())
    emp.team = Team.objects.create(section=emp.section, name="Tổ 1")
    emp.section = None
    with pytest.raises(ValidationError, match="Chọn bộ phận trước khi chọn tổ"):
        emp.clean()
    other = Section.objects.create(department=Department.objects.create(name="PB2"), name="BP2")
    emp.section = other
    with pytest.raises(ValidationError, match="Tổ phải thuộc bộ phận"):
        emp.clean()


# ----- Loại tài liệu "Bản cam kết" (câu 45) ---------------------------------------------------
def test_co_loai_tai_lieu_ban_cam_ket_khong_bat_buoc():
    doc_type = DocumentType.objects.get(name="Bản cam kết")
    assert doc_type.system_code is None and doc_type.required_group_id is None
    assert doc_type.is_active
    other = DocumentType.objects.get(name="Khác")
    assert other.sort_order > doc_type.sort_order  # "Khác" vẫn ở cuối


# ----- Ẩn danh hóa (models.md 4.7) ------------------------------------------------------------
def test_an_danh_xoa_lich_su_luong_va_ghi_chu_dot_giu_cong_ty_va_ngay(
    django_capture_on_commit_callbacks,
):
    worker, _ = rich_worker()
    client = company()
    a = assignment(worker, start=D(2025, 1, 1), end=D(2025, 12, 31), client=client, note="ZQX")
    salary(a, day=D(2025, 1, 1))
    salary(a, amount="9000000", day=D(2025, 6, 1))
    other = assignment(make_worker(), client=client)  # hồ sơ khác không bị đụng tới
    salary(other)
    with django_capture_on_commit_callbacks(execute=True):
        run(worker)
    assert not SalaryHistory.objects.filter(worker=worker).exists()
    kept = WorkAssignment.objects.get(pk=a.pk)
    assert kept.note == ""
    assert (kept.client_company_id, kept.start_date, kept.end_date) == (
        client.pk,
        D(2025, 1, 1),
        D(2025, 12, 31),
    )
    assert SalaryHistory.objects.filter(worker=other.worker).count() == 1


def test_chi_retention_xoa_lich_su_luong():
    """Quét mã nguồn: chỉ apps/workers/retention.py gọi xóa SalaryHistory."""
    from pathlib import Path

    from django.conf import settings

    hits = []
    for path in (Path(settings.BASE_DIR) / "apps").rglob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if ("SalaryHistory" in line or "salary_history" in line) and ".delete(" in line:
                hits.append(path.relative_to(settings.BASE_DIR).as_posix())
    assert hits == ["apps/workers/retention.py"]
