"""AuditLog và các bảng chỉ thêm không sửa/xóa được (Phase 2 bước 3a)."""

import pytest
from django.db import DatabaseError, connection, transaction

from apps.accounts.models import LoginHistory, Role, User
from apps.audit.models import AuditLog, AuditPersonalValue
from apps.core.models_base import AppendOnlyError
from tests.factories import make_worker


@pytest.fixture
def log(db):
    return AuditLog.objects.create(
        actor_label="Hệ thống",
        action="CREATE",
        object_type="workers.Worker",
        object_id="1",
        object_repr="HS-2026-00001",
    )


def test_auditlog_tao_duoc(log):
    assert AuditLog.objects.count() == 1


def test_auditlog_khong_sua_qua_model(log):
    log.note = "sửa"
    with pytest.raises(AppendOnlyError):
        log.save()


def test_auditlog_khong_xoa_qua_model(log):
    with pytest.raises(AppendOnlyError):
        log.delete()


def test_auditlog_khong_sua_xoa_qua_queryset(log):
    with pytest.raises(AppendOnlyError):
        AuditLog.objects.update(note="x")
    with pytest.raises(AppendOnlyError):
        AuditLog.objects.filter(pk=log.pk).delete()
    with pytest.raises(AppendOnlyError):
        AuditLog.objects.all().delete()
    with pytest.raises(AppendOnlyError):
        AuditLog.objects.bulk_update([log], ["note"])
    assert AuditLog.objects.get(pk=log.pk).note == ""


def test_trigger_postgres_chan_sql_tho(log):
    assert connection.vendor == "postgresql"
    with pytest.raises(DatabaseError, match="chỉ được thêm"), transaction.atomic():
        with connection.cursor() as cur:
            cur.execute("UPDATE audit_auditlog SET note = 'x'")
    with pytest.raises(DatabaseError, match="chỉ được thêm"), transaction.atomic():
        with connection.cursor() as cur:
            cur.execute("DELETE FROM audit_auditlog")
    assert AuditLog.objects.count() == 1


def test_personal_value_tao_duoc_ma_hoa_va_khong_sua(log):
    pv = AuditPersonalValue.objects.create(
        audit_log=log,
        worker=make_worker(),
        field_name="full_name",
        old_value_enc="Nguyễn Văn A",
        new_value_enc="Trần B",
    )
    pv.refresh_from_db()
    assert (pv.old_value_enc, pv.new_value_enc) == ("Nguyễn Văn A", "Trần B")
    with connection.cursor() as cur:
        cur.execute("SELECT old_value_enc FROM audit_auditpersonalvalue")
        raw = cur.fetchone()[0]
    assert "Nguyễn" not in raw
    pv.field_name = "khác"
    with pytest.raises(AppendOnlyError):
        pv.save()
    with pytest.raises(AppendOnlyError):
        AuditPersonalValue.objects.update(field_name="x")


def test_personal_value_update_sql_tho_bi_trigger_chan(log):
    AuditPersonalValue.objects.create(
        audit_log=log, worker=make_worker(), field_name="phone", new_value_enc="0900000000"
    )
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cur:
            cur.execute("UPDATE audit_auditpersonalvalue SET field_name = 'x'")


def test_personal_value_xoa_duoc_cho_an_danh_hoa(log):
    AuditPersonalValue.objects.create(
        audit_log=log, worker=make_worker(), field_name="phone", new_value_enc="0900000000"
    )
    AuditPersonalValue.objects.all().delete()
    assert AuditPersonalValue.objects.count() == 0
    assert AuditLog.objects.count() == 1  # dòng nhật ký vẫn còn


def test_login_history_chi_them(db):
    role = Role.objects.get(code="VIEWER")
    user = User.objects.create(username="u1", full_name="Người Giả", role=role)
    h = LoginHistory.objects.create(
        user=user, username_attempted="u1", ip_address="127.0.0.1", success=True
    )
    h.success = False
    with pytest.raises(AppendOnlyError):
        h.save()
    with pytest.raises(AppendOnlyError):
        h.delete()
    with pytest.raises(AppendOnlyError):
        LoginHistory.objects.update(success=False)
