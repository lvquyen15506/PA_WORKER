"""Vòng lặp của container scheduler: check_keys -> kiểm tra migration -> run_daily_jobs -> nghỉ.

Không có cron: máy demo không bật 24/7 nên chạy mỗi giờ, tác vụ idempotent
(kien-truc.md mục 2.1). Còn migration chưa áp dụng thì chờ rồi thử lại, không chạy tác vụ.
"""

import time

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.core.keys import KeyConfigError, check_against_database, check_format


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
            if options["once"]:
                return
            time.sleep(options["interval"])
