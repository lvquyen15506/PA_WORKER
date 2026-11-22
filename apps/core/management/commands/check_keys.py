"""Kiểm tra khóa mã hóa và khóa băm. Dùng khi khởi động web/scheduler.

--format : chỉ kiểm tra có đủ khóa và đúng định dạng (chạy trước migrate, không cần CSDL).
Không có cờ: kiểm tra thêm khóa khớp dữ liệu hiện có (giá trị kiểm tra trong Settings);
lần chạy đầu tiên ghi giá trị đó. Bản SQLite dự phòng cũng phải chạy lệnh này trước runserver.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.core.keys import KeyConfigError, check_against_database, check_format


class Command(BaseCommand):
    help = "Kiểm tra khóa mã hóa FIELD_ENCRYPTION_KEY và khóa băm HASH_KEY."

    def add_arguments(self, parser):
        parser.add_argument("--format", action="store_true", help="Chỉ kiểm tra định dạng.")

    def handle(self, *args, **options):
        try:
            check_format()
            if options["format"]:
                self.stdout.write("Khóa mã hóa và khóa băm đúng định dạng.")
                return
            result = check_against_database()
        except KeyConfigError as exc:
            raise CommandError(str(exc)) from exc
        if result == "created":
            self.stdout.write("Đã ghi giá trị kiểm tra khóa (lần khởi động đầu).")
        else:
            self.stdout.write("Khóa mã hóa và khóa băm khớp với dữ liệu hiện có.")
