"""Kiểm tra khóa mã hóa và khóa băm. Dùng khi khởi động web/scheduler.

--format : chỉ kiểm tra có đủ khóa và đúng định dạng (chạy trước migrate, không cần CSDL).
Bản đầy đủ (so khớp giá trị kiểm tra trong Settings) thêm ở bước 3a, sau khi có model.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.core.keys import KeyConfigError, check_format


class Command(BaseCommand):
    help = "Kiểm tra khóa mã hóa FIELD_ENCRYPTION_KEY và khóa băm HASH_KEY."

    def add_arguments(self, parser):
        parser.add_argument("--format", action="store_true", help="Chỉ kiểm tra định dạng.")

    def handle(self, *args, **options):
        try:
            check_format()
        except KeyConfigError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write("Khóa mã hóa và khóa băm đúng định dạng.")
