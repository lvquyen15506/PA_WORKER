"""Sinh bộ ảnh CCCD giả (15 thẻ) và CV giả. QR sinh theo QrFormat đang dùng trong CSDL."""

import os

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import QrFormat
from apps.intake import fake_cards

README = """# Dữ liệu giả để kiểm thử

Mọi ảnh và tệp trong thư mục này là **dữ liệu hư cấu**, không có thông tin của người thật.

- Số CCCD giả luôn bắt đầu bằng `999`; họ tên, địa chỉ là tên hư cấu.
- Mọi mặt thẻ có dòng "MẪU – KHÔNG CÓ GIÁ TRỊ". Bố cục chỉ là chữ, không có quốc huy hay
  họa tiết thẻ thật.
- QR được sinh theo cấu hình QrFormat tại thời điểm chạy lệnh (`python manage.py make_fake_cccd`),
  nên bộ ảnh chỉ chứng minh bộ tách trường khớp cấu hình, **chưa chứng minh khớp thẻ thật**
  (câu 20).
- `truth.json`: giá trị đúng của từng thẻ (`values`), trường in trên thẻ (`printed`), trường có
  trong QR (`qr_fields`), chất lượng ảnh (`good`, `low_res`, `dark`, `blur`).
- Sinh lại: `docker compose exec web python manage.py make_fake_cccd --out tests/fixtures/cccd`
"""


class Command(BaseCommand):
    help = "Sinh 15 thẻ CCCD giả (30 ảnh) và CV giả."

    def add_arguments(self, parser):
        parser.add_argument("--out", default="tests/fixtures/cccd", help="Thư mục ảnh thẻ.")
        parser.add_argument("--cv", default="", help="Thư mục CV giả (bỏ trống thì không sinh CV).")
        parser.add_argument(
            "--offset", type=int, default=0, help="Dịch số CCCD giả để không trùng lần chạy trước."
        )

    def handle(self, *args, **options):
        formats = {q.id_doc_type: q for q in QrFormat.objects.all()}
        if not formats:
            raise CommandError("Chưa có cấu hình QR trong cơ sở dữ liệu.")
        if not 0 <= options["offset"] < 900_000_000:
            raise CommandError("--offset phải từ 0 đến dưới 900000000.")
        cards = fake_cards.generate_cards(options["out"], formats, offset=options["offset"])
        with open(os.path.join(options["out"], "README.md"), "w", encoding="utf-8") as handle:
            handle.write(README)
        self.stdout.write(
            f"Đã sinh {len(cards)} thẻ giả ({len(cards) * 2} ảnh) vào {options['out']}."
        )
        if options["cv"]:
            os.makedirs(options["cv"], exist_ok=True)
            fake_cards.write_cv_docx(os.path.join(options["cv"], "cv-mau.docx"))
            fake_cards.write_cv_pdf(os.path.join(options["cv"], "cv-mau.pdf"))
            fake_cards.write_cv_image(os.path.join(options["cv"], "cv-mau.png"))
            self.stdout.write(f"Đã sinh CV giả vào {options['cv']}.")
