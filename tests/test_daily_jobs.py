"""run_daily_jobs, run_scheduler (Phase 2 bước 6)."""

import datetime
import io
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.core.management.commands.run_daily_jobs import ADVISORY_LOCK_KEY
from apps.intake.models import IntakeSession
from apps.workers import jobs
from tests.factories import make_user

pytestmark = pytest.mark.django_db


def make_session(user, hours_from_now):
    s = IntakeSession(
        created_by=user, expires_at=timezone.now() + datetime.timedelta(hours=hours_from_now)
    )
    s.front_image.save("a.jpg", ContentFile(b"\xff\xd8\xff"), save=False)
    s.result_enc = "{}"
    s.save()
    return s


def run(*args):
    out = io.StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


def test_xoa_phien_het_han_giu_phien_con_han_va_ghi_nhat_ky():
    user = make_user()
    old = make_session(user, -1)
    fresh = make_session(user, 5)
    old_path = Path(old.front_image.path)
    fresh_path = Path(fresh.front_image.path)
    assert old_path.exists()
    old_pk = str(old.pk)
    assert "Đã xóa 1 phiên" in run("run_daily_jobs")
    assert not IntakeSession.objects.filter(pk=old_pk).exists()
    assert IntakeSession.objects.filter(pk=fresh.pk).exists()
    assert not old_path.exists() and fresh_path.exists()
    entry = AuditLog.objects.get()
    assert (entry.action, entry.actor_label, entry.user, entry.object_id) == (
        "INTAKE_EXPIRE",
        "Hệ thống",
        None,
        old_pk,
    )


def test_idempotent_chay_lai_khong_doi_gi():
    user = make_user()
    make_session(user, -2)
    make_session(user, 3)
    first = jobs.run_daily_jobs()
    second = jobs.run_daily_jobs()
    assert first == {"intake_expired": 1, "auto_archived": 0}
    assert second == {"intake_expired": 0, "auto_archived": 0}
    assert IntakeSession.objects.count() == 1 and AuditLog.objects.count() == 1


def test_loi_o_mot_phien_khong_chan_phien_khac(monkeypatch):
    user = make_user()
    bad = make_session(user, -1)
    good = make_session(user, -1)
    original = IntakeSession.close

    def close(self):
        if self.pk == bad.pk:
            raise RuntimeError("hỏng")
        return original(self)

    monkeypatch.setattr(IntakeSession, "close", close)
    assert jobs.expire_intake_sessions() == 1
    assert IntakeSession.objects.filter(pk=bad.pk).exists()
    assert not IntakeSession.objects.filter(pk=good.pk).exists()
    # Phiên hỏng: giao dịch hoàn tác nên không có nhật ký của nó.
    assert AuditLog.objects.filter(object_id=str(bad.pk)).count() == 0


def test_khoa_advisory_lan_chay_thu_hai_bi_bo_qua():
    assert connection.vendor == "postgresql"
    user = make_user()
    make_session(user, -1)
    other = connection.copy()  # phiên PostgreSQL khác đang giữ khóa
    try:
        with other.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", [ADVISORY_LOCK_KEY])
        assert "bỏ qua" in run("run_daily_jobs")
        assert IntakeSession.objects.count() == 1  # chưa xử lý gì
    finally:
        with other.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", [ADVISORY_LOCK_KEY])
        other.close()
    assert "Đã xóa 1 phiên" in run("run_daily_jobs")  # khóa đã nhả: chạy được


def test_khoa_duoc_nha_sau_khi_chay():
    run("run_daily_jobs")
    other = connection.copy()
    try:
        with other.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", [ADVISORY_LOCK_KEY])
            assert cur.fetchone()[0] is True
            cur.execute("SELECT pg_advisory_unlock(%s)", [ADVISORY_LOCK_KEY])
    finally:
        other.close()


def test_run_scheduler_once_chay_tac_vu_va_ghi_gia_tri_kiem_tra_khoa():
    make_session(make_user(), -1)
    out = run("run_scheduler", "--once")
    assert "Đã xóa 1 phiên" in out
    assert "khớp" not in out  # run_scheduler không in; nhưng khóa đã được ghi
    from apps.core.models import SystemSetting

    assert SystemSetting.load().key_check_hash


def test_run_scheduler_thoat_khi_khoa_sai(settings):
    run("run_scheduler", "--once")  # lần đầu ghi giá trị kiểm tra
    import base64

    settings.HASH_KEY = base64.urlsafe_b64encode(b"Z" * 32).decode()
    with pytest.raises(CommandError, match="HASH_KEY không khớp"):
        run("run_scheduler", "--once")


def test_run_scheduler_cho_khi_con_migration(monkeypatch):
    import apps.core.management.commands.run_scheduler as sched

    monkeypatch.setattr(sched, "has_pending_migrations", lambda: True)
    make_session(make_user(), -1)
    out = run("run_scheduler", "--once")
    assert "Còn migration chưa áp dụng" in out and IntakeSession.objects.count() == 1


def test_auto_archive_la_khung_tra_ve_0():
    assert jobs.auto_archive() == 0
