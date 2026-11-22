"""Chạy các tác vụ định kỳ một lần. Chống chạy chồng bằng pg_try_advisory_lock (PostgreSQL);
bản SQLite dự phòng chạy một tiến trình nên bỏ qua khóa."""

from django.core.management.base import BaseCommand
from django.db import connection

from apps.workers.jobs import run_daily_jobs

ADVISORY_LOCK_KEY = 7_260_001  # khóa riêng cho run_daily_jobs


class Command(BaseCommand):
    help = "Chạy tác vụ định kỳ (xóa phiên nhận diện hết hạn, tự Lưu trữ)."

    def handle(self, *args, **options):
        locked = False
        if connection.vendor == "postgresql":
            with connection.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s)", [ADVISORY_LOCK_KEY])
                if not cur.fetchone()[0]:
                    self.stdout.write("Lần chạy trước chưa xong, bỏ qua lần này.")
                    return
                locked = True
        try:
            result = run_daily_jobs()
            self.stdout.write(
                f"Đã xóa {result['intake_expired']} phiên nhận diện hết hạn; "
                f"tự Lưu trữ {result['auto_archived']} hồ sơ."
            )
        finally:
            if locked:
                with connection.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(%s)", [ADVISORY_LOCK_KEY])
