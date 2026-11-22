"""Đo độ chính xác nhận diện và thời gian xử lý trên bộ thẻ CCCD giả.

Ghi kết quả vào docs/do-chinh-xac-nhan-dien.md."""

import datetime
import json
import os
import platform
import statistics
import time
from collections import defaultdict

import pytesseract
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import QrFormat, SystemSetting
from apps.intake import imaging
from apps.intake.fields import FIELD_LABELS
from apps.intake.pipeline import recognize

GOOD = "good"


def _pct(ok, total):
    return f"{ok}/{total} ({100 * ok / total:.0f}%)" if total else "—"


def _median(values):
    return f"{statistics.median(values):.2f}" if values else "—"


class Command(BaseCommand):
    help = "Chạy nhận diện trên bộ thẻ giả, so với truth.json, ghi bảng độ chính xác và thời gian."

    def add_arguments(self, parser):
        parser.add_argument("--dir", default="tests/fixtures/cccd")
        parser.add_argument("--out", default="docs/do-chinh-xac-nhan-dien.md")
        parser.add_argument("--repeat", type=int, default=3, help="Số lần đo thời gian mỗi thẻ.")

    def handle(self, *args, **options):
        folder = options["dir"]
        try:
            with open(os.path.join(folder, "truth.json"), encoding="utf-8") as handle:
                cards = json.load(handle)["cards"]
        except FileNotFoundError as exc:
            raise CommandError(
                f"Không thấy {folder}/truth.json. Chạy make_fake_cccd trước."
            ) from exc
        threshold = SystemSetting.load().ocr_confidence_threshold

        qr_stat = defaultdict(lambda: [0, 0])  # (mẫu thẻ, trường) -> [đúng, tổng]
        ocr_stat = defaultdict(lambda: [0, 0])
        wrong_not_low, low_total, empty_total, field_total = 0, 0, 0, 0
        wrong_details, timings = [], defaultdict(list)
        doc_type_ok = 0

        for card in cards:
            images = {
                side: imaging.load_image(open(os.path.join(folder, name), "rb").read())
                for side, name in card["files"].items()
            }
            for _ in range(options["repeat"]):
                started = time.monotonic()
                result = recognize(images["front"], images["back"], "", threshold)
                elapsed = time.monotonic() - started
                for stage in ("quality", "qr", "ocr", "total"):
                    timings[stage].append(result["timings"][stage])
                timings["wall"].append(elapsed)
                timings[f"total-{card['quality']}"].append(result["timings"]["total"])
            doc_type_ok += result["doc_type"] == card["doc_type"]
            for name in card["printed"]:
                field = result["fields"].get(name)
                truth = card["values"][name]
                is_qr = name in card["qr_fields"]
                key = (card["doc_type"], name)
                stat = qr_stat[key] if is_qr else ocr_stat[key]
                stat[1] += 1
                field_total += 1
                value = field["value"] if field else None
                if value == truth:
                    stat[0] += 1
                if field is None or value is None:
                    empty_total += 1
                elif value != truth and not field["low"]:
                    wrong_not_low += 1
                    wrong_details.append(f"thẻ {card['id']} trường {name}")
                if field and field["low"]:
                    low_total += 1

        self._write(
            options["out"],
            cards,
            qr_stat,
            ocr_stat,
            timings,
            {
                "threshold": threshold,
                "field_total": field_total,
                "low_total": low_total,
                "empty_total": empty_total,
                "wrong_not_low": wrong_not_low,
                "wrong_details": wrong_details,
                "doc_type_ok": doc_type_ok,
                "repeat": options["repeat"],
            },
        )
        self.stdout.write(f"Đã ghi {options['out']}.")
        if wrong_not_low:
            self.stdout.write(f"CẢNH BÁO: {wrong_not_low} trường sai nhưng không tô vàng.")

    def _write(self, path, cards, qr_stat, ocr_stat, timings, info):
        qr_total = [sum(v[0] for v in qr_stat.values()), sum(v[1] for v in qr_stat.values())]
        ocr_total = [sum(v[0] for v in ocr_stat.values()), sum(v[1] for v in ocr_stat.values())]
        formats = QrFormat.objects.order_by("id_doc_type")
        lines = [
            "# Độ chính xác nhận diện CCCD và thời gian xử lý",
            "",
            f"Đo ngày {datetime.date.today():%d/%m/%Y} bằng "
            "`python manage.py measure_intake_accuracy` "
            f"trên bộ {len(cards)} thẻ giả (`tests/fixtures/cccd/`, 2 mặt mỗi thẻ).",
            "",
            "## Phạm vi và giới hạn",
            "",
            "- **Dữ liệu hoàn toàn giả**: số CCCD bắt đầu `999`, tên hư cấu, mọi ảnh có dòng "
            '"MẪU – KHÔNG CÓ GIÁ TRỊ". Bố cục là chữ in rõ trên nền trắng, không có họa tiết, '
            "ánh sáng hay nghiêng như ảnh chụp thật.",
            "- QR sinh theo đúng cấu hình `QrFormat` đang dùng, nên kết quả QR chỉ chứng minh "
            "bộ tách trường **khớp cấu hình**, **chưa chứng minh khớp thẻ thật** (câu 20 của "
            "`docs/lam-ro-yeu-cau.md`). Cấu trúc QR của thẻ thật vẫn là giả định cần kiểm chứng "
            "khi triển khai.",
            "- Độ chính xác OCR trên ảnh sạch này **cao hơn nhiều so với ảnh chụp thật**; "
            "đừng dùng con số này để cam kết với khách hàng. "
            "Cần đo lại trên ảnh chụp thực tế khi có thể.",
            f"- Ngưỡng tin cậy OCR khi đo: {info['threshold']}%. Cấu hình QR khi đo:",
        ]
        for qr in formats:
            lines.append(
                f"  - `{qr.id_doc_type}`: phân cách `{qr.separator}`, ngày `{qr.date_format}`, "
                f"thứ tự `{', '.join(qr.field_order)}`"
            )
        lines += [
            "",
            "## Kết quả tổng hợp",
            "",
            "| Chỉ số | Kết quả |",
            "| --- | --- |",
            f"| Trường đọc từ QR đúng (kịch bản 3) | {_pct(*qr_total)} |",
            f"| Trường đọc từ OCR đúng (kịch bản 4) | {_pct(*ocr_total)} |",
            f"| Nhận đúng mẫu thẻ | {_pct(info['doc_type_ok'], len(cards))} |",
            f"| Trường để trống (không đọc được) | {info['empty_total']}/{info['field_total']} |",
            "| Trường bị tô vàng (phải tích Đã kiểm tra) | "
            f"{info['low_total']}/{info['field_total']} |",
            f"| **Trường sai mà KHÔNG tô vàng** | **{info['wrong_not_low']}** |",
            "",
            "Chỉ số quan trọng nhất là dòng đậm: một trường đọc sai mà không bị tô vàng sẽ lọt qua "
            "bước kiểm tra của người dùng.",
        ]
        if info["wrong_details"]:
            lines += ["", "Các trường sai không tô vàng: " + "; ".join(info["wrong_details"]) + "."]
        lines += [
            "",
            "## Theo mẫu thẻ và trường",
            "",
            "| Mẫu thẻ | Trường | QR đúng | OCR đúng |",
            "| --- | --- | --- | --- |",
        ]
        for doc_type, name in sorted(set(qr_stat) | set(ocr_stat)):
            q, o = qr_stat.get((doc_type, name)), ocr_stat.get((doc_type, name))
            lines.append(
                f"| {doc_type} | {FIELD_LABELS[name]} | "
                f"{_pct(*q) if q else '—'} | {_pct(*o) if o else '—'} |"
            )
        quality_rows = defaultdict(lambda: [0, 0])
        lines += ["", "## Theo chất lượng ảnh", "", "| Chất lượng | Số thẻ |", "| --- | --- |"]
        for card in cards:
            quality_rows[card["quality"]][1] += 1
        for quality, (_, count) in sorted(quality_rows.items()):
            lines.append(f"| {quality} | {count} |")
        lines += [
            "",
            "`good` ảnh rõ; `low_res` rộng 800 px (dưới 1000); `dark` rất tối; `blur` mờ vừa.",
            "",
            "## Thời gian xử lý một lượt ảnh trên CPU",
            "",
            f"Một lượt = kiểm tra ảnh + đọc QR + OCR cả hai mặt. Mỗi thẻ đo {info['repeat']} lần, "
            "tính trên toàn bộ các lần đo (giây).",
            "",
            "| Giai đoạn | Trung vị | Lớn nhất |",
            "| --- | --- | --- |",
        ]
        labels = {
            "quality": "Kiểm tra ảnh",
            "qr": "Đọc QR",
            "ocr": "OCR (Tesseract vie)",
            "total": "**Cả lượt**",
        }
        for stage, label in labels.items():
            values = timings[stage]
            lines.append(f"| {label} | {_median(values)} | {max(values):.2f} |")
        lines += [
            "",
            "Ngân sách cho cả lượt là 90 giây (Gunicorn timeout 120 giây); hết ngân sách thì "
            "trường chưa đọc để trống, tô vàng và có cảnh báo.",
            "",
            "## Máy đo",
            "",
            f"- Bộ xử lý: {platform.processor() or platform.machine()}, {os.cpu_count()} luồng",
            f"- Hệ điều hành trong container: {platform.platform()}",
            f"- Tesseract: {pytesseract.get_tesseract_version()}, gói ngôn ngữ `vie`",
            f"- Python: {platform.python_version()}",
            "- Chạy trong container `web`, không dùng GPU.",
            "",
        ]
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
