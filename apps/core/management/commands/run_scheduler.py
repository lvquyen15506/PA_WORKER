"""Vòng lặp của container scheduler: check_keys -> kiểm tra migration -> run_daily_jobs ->
sao lưu tự động (Phase 8) -> nghỉ.

Không có cron: máy demo không bật 24/7 nên chạy mỗi giờ, tác vụ idempotent
(kien-truc.md mục 2.1). Còn migration chưa áp dụng thì chờ rồi thử lại, không chạy tác vụ.
Sao lưu tự động chạy khi chưa có bản sao lưu nào trong BACKUP_INTERVAL_HOURS giờ qua; lỗi sao lưu
chỉ ghi log (không dừng scheduler). Đĩa còn dưới DISK_WARNING_BYTES thì ghi cảnh báo vào log.
"""

import logging
import time

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.core.backup import service as backup_service
from apps.core.backup.stream import BackupError
from apps.core.keys import KeyConfigError, check_against_database, check_format

logger = logging.getLogger(__name__)


def auto_backup():
    """Sao lưu tự động nếu đến hạn; trả tên file vừa tạo hoặc None."""
    for label, path, free, _total in backup_service.disk_status():
        if free < settings.DISK_WARNING_BYTES:
            logger.warning("%s (%s) còn trống %s", label, path, backup_service.human(free))
    if not settings.BACKUP_AUTO or not backup_service.auto_backup_due():
        return None
    try:
        result = backup_service.create_backup()
    except BackupError as exc:
        logger.error("Sao lưu tự động không thành công: %s", exc)
        return None
    logger.info("Đã sao lưu tự động: %s", result["path"].name)
    return result["path"].name


def has_pending_migrations():
    executor = MigrationExecutor(connection)
    return bool(executor.migration_plan(executor.loader.graph.leaf_nodes()))


class Command(BaseCommand):
    help = "Chạy run_daily_jobs định kỳ (mặc định mỗi giờ)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Chạy một vòng rồi thoát.")
        parser.add_argument("--interval", type=int, default=3600, help="Giây giữa hai vòng.")
        parser.add_argument(
            "--retry-wait", type=int, default=60, help="Giây chờ khi còn migration."
        )

    def handle(self, *args, **options):
        while True:
            try:  # khóa sai thì thoát để container báo lỗi rõ ràng
                check_format()
                check_against_database()
            except KeyConfigError as exc:
                raise CommandError(str(exc)) from exc
            if has_pending_migrations():
                self.stdout.write("Còn migration chưa áp dụng; chờ rồi thử lại.")
                if options["once"]:
                    return
                time.sleep(options["retry_wait"])
                continue
            call_command("run_daily_jobs", stdout=self.stdout)
            auto_backup()
            if options["once"]:
                return
            time.sleep(options["interval"])
