"""Nghiệm thu Phase 5 bằng Playwright (kịch bản 3, 4, 5 của docs/yeu-cau.md mục X). Chạy:
    py -3.12 scripts/nghiem_thu_phase5.py
Chạy trên bản cài sạch (docker compose -f docker-compose.yml). Ảnh thẻ giả sinh mới mỗi lần
(số CCCD bắt đầu 999), kết quả đối chiếu với cơ sở dữ liệu qua manage.py shell. Ảnh chụp ở
docs/screenshots/phase-5/nghiem-thu/.
"""

import datetime
import sys

import pw_phase5 as pw
from playwright.sync_api import sync_playwright
from pw_phase5 import CARD_DIR, check, goto, login, new_page

OUT = pw.ROOT / "docs" / "screenshots" / "phase-5" / "nghiem-thu"
S = "1366x768"
SIZE = pw.SIZES[S]


def display(name, value):
    if name in ("date_of_birth", "issue_date", "expiry_date"):
        return datetime.date.fromisoformat(value).strftime("%d/%m/%Y")
    return value


def upload(page, card):
    goto(page, "/nhap-cccd/")
    page.set_input_files("input[name=front_image]", str(CARD_DIR / card["files"]["front"]))
    page.set_input_files("input[name=back_image]", str(CARD_DIR / card["files"]["back"]))
    page.click("button:has-text('Nhận diện')")
    page.wait_for_load_state("networkidle")


def field_value(page, name):
    return page.input_value(f"[name={name}]")


def worker_row(id_number):
    code = (
        "from apps.core.crypto import compute_id_hash;"
        "from apps.workers.models import IdentityDocument;"
        "q=IdentityDocument.objects.select_related('worker');"
        f"i=q.get(id_number_hash=compute_id_hash('{id_number}'));"
        "w=i.worker;"
        "print(w.verification_status, w.worker_code, i.id_doc_type, w.full_name, "
        "w.date_of_birth, w.gender, w.documents.count(), "
        "sorted(f'{s.field_name}={s.source}' for s in w.field_sources.all()))"
    )
    return pw.db(code)


def scenario_3(browser, cards):
    """HR tải ảnh CCCD giả có QR: điền đúng 100% trường có trong QR."""
    ctx, page = new_page(browser, SIZE)
    login(page, "hr")
    with_qr = [c for c in cards if c["has_qr"]]
    wrong, total = [], 0
    for i, c in enumerate(with_qr):
        upload(page, c)
        for name in c["qr_fields"]:
            total += 1
            expected = display(name, c["values"][name]) if name != "gender" else c["values"][name]
            actual = field_value(page, name)
            if actual != expected:
                wrong.append((c["id"], name, actual))
        tags = page.locator(".pa-source:has-text('QR')").count()
        if i == 0:
            pw.shot(OUT, page, S, "k3-doi-chieu-qr")
        # Tiêu chí kịch bản 3 (mục X): trường CÓ TRONG QR điền đúng, không tô vàng. Trường không
        # có trong QR (đọc bằng OCR, ví dụ nơi đăng ký khai sinh của Căn cước 2024) có thể tô vàng
        # tùy chữ của thẻ giả sinh ngẫu nhiên; HR đối chiếu và tích Đã kiểm tra như thao tác thật.
        low = page.evaluate(
            "[...document.querySelectorAll('.pa-field--low input, .pa-field--low select')]"
            ".map(e => e.name)"
        )
        low_qr = [name for name in low if name in c["qr_fields"]]
        check(
            f"K3 thẻ {c['id']} ({c['doc_type']}): có nhãn nguồn QR, trường QR không tô vàng",
            tags >= len(c["qr_fields"]) - 1 and not low_qr,
            str(low_qr),
        )
        for box in page.locator("[data-pa-checked]").all():
            box.check()
        page.fill("input[name=phone]", "0900000001")
        page.click("button[data-pa-gate]")
        page.wait_for_load_state("networkidle")
        saved = "Đã lưu hồ sơ ở trạng thái Nháp." in page.content()
        check(f"K3 thẻ {c['id']}: lưu thành hồ sơ Nháp", saved)
        if i == 0:
            pw.shot(OUT, page, S, "k3-sau-khi-luu")
    check(
        f"K3: điền đúng 100% trường có trong QR ({total} trường, {len(with_qr)} thẻ)",
        not wrong and total > 0,
        str(wrong[:5]),
    )
    ctx.close()


def scenario_4(browser, cards):
    """HR tải ảnh CCCD không QR: OCR điền được, trường không chắc tô vàng, chưa tích không lưu."""
    ctx, page = new_page(browser, SIZE)
    login(page, "hr")
    good = next(c for c in cards if c["doc_type"] == "CCCD_2016" and c["quality"] == "good")
    upload(page, good)
    ocr_ok = (
        all(
            field_value(page, n) == display(n, good["values"][n])
            for n in good["printed"]
            if n != "gender"
        )
        and field_value(page, "gender") == good["values"]["gender"]
    )
    check("K4: ảnh không QR, OCR điền đúng mọi trường in trên thẻ", ocr_ok)
    check("K4: nhãn nguồn OCR hiển thị", page.locator(".pa-source:has-text('OCR')").count() >= 8)
    pw.shot(OUT, page, S, "k4-ocr-the-ro")
    page.click("button:has-text('Hủy phiên')")
    page.wait_for_selector("#cancel-session.show", timeout=5000)
    page.wait_for_timeout(400)
    page.click("#cancel-session button[data-pa-submit]")
    page.wait_for_load_state("networkidle")

    blur = next(c for c in cards if c["quality"] == "blur")
    upload(page, blur)
    low = page.locator(".pa-field--low").count()
    check("K4: ảnh mờ có trường tô vàng", low >= 5, str(low))
    check(
        "K4: nút Lưu hồ sơ bị khóa khi chưa tích Đã kiểm tra",
        page.locator("button[data-pa-gate]").is_disabled(),
    )
    pw.shot(OUT, page, S, "k4-to-vang-khoa-nut-luu")
    # HR nhập tay các trường đọc không được, KHÔNG tích Đã kiểm tra, rồi cố gửi form bằng cách
    # gỡ thuộc tính khóa: máy chủ phải từ chối.
    for name in blur["printed"]:
        if name == "gender":
            page.select_option("select[name=gender]", blur["values"]["gender"])
        else:
            page.fill(f"[name={name}]", display(name, blur["values"][name]))
    page.fill("input[name=phone]", "0900000001")
    before = int(pw.db("from apps.workers.models import Worker;print(Worker.objects.count())"))
    page.evaluate("document.querySelector('button[data-pa-gate]').disabled = false")
    page.click("button[data-pa-gate]")
    page.wait_for_load_state("networkidle")
    after = int(pw.db("from apps.workers.models import Worker;print(Worker.objects.count())"))
    check(
        "K4: gỡ khóa nút rồi gửi vẫn bị máy chủ từ chối (chưa tích Đã kiểm tra)",
        "Cần tích Đã kiểm tra" in page.content() and before == after,
        f"{before}->{after}",
    )
    pw.shot(OUT, page, S, "k4-may-chu-tu-choi")
    # tích đủ thì lưu được
    for box in page.locator("input[data-pa-checked]").all():
        box.check()
    check("K4: tích đủ thì nút Lưu bật", page.locator("button[data-pa-gate]").is_enabled())
    page.click("button[data-pa-gate]")
    page.wait_for_load_state("networkidle")
    check(
        "K4: tích đủ thì lưu được hồ sơ Nháp", "Đã lưu hồ sơ ở trạng thái Nháp." in page.content()
    )
    row = worker_row(blur["values"]["id_number"])
    check(
        "K4: hồ sơ có nguồn từng trường và 2 tài liệu ảnh",
        row.startswith("DRAFT") and " 2 [" in row,
        row,
    )
    ctx.close()


def scenario_5(browser, cards):
    """Nhập CCCD đã có trong hệ thống: báo trùng, mở hồ sơ cũ, không tạo hồ sơ mới."""
    ctx, page = new_page(browser, SIZE)
    login(page, "hr")
    c = next(c for c in cards if c["has_qr"])  # đã lưu ở kịch bản 3
    id_number = c["values"]["id_number"]
    check("K5: trước khi thử đã có đúng 1 hồ sơ giữ số CCCD này", pw.count_by_id(id_number) == 1)
    upload(page, c)
    html = page.content()
    check("K5: màn hình đối chiếu báo trùng ngay khi mở", "Số CCCD này đã có hồ sơ" in html)
    check("K5: có nút Mở hồ sơ cũ", page.locator("button:has-text('Mở hồ sơ cũ')").count() == 1)
    pw.shot(OUT, page, S, "k5-bao-trung")
    page.fill("input[name=phone]", "0900000001")
    page.click("button[data-pa-gate]")
    page.wait_for_load_state("networkidle")
    check(
        "K5: bấm Lưu hồ sơ bị chặn, không tạo hồ sơ mới",
        "Số CCCD này đã có hồ sơ" in page.content() and pw.count_by_id(id_number) == 1,
    )
    session_url = page.url
    sessions_before = pw.count_sessions()
    page.click("button:has-text('Mở hồ sơ cũ')")
    page.wait_for_load_state("networkidle")
    check(
        "K5: Mở hồ sơ cũ chuyển tới trang chi tiết hồ sơ",
        "/ho-so/" in page.url and "/nhap-cccd/" not in page.url,
        page.url,
    )
    pw.shot(OUT, page, S, "k5-ho-so-cu")
    check("K5: vẫn chỉ có 1 hồ sơ với số CCCD này", pw.count_by_id(id_number) == 1)
    check("K5: phiên nhận diện đã đóng", pw.count_sessions() == sessions_before - 1)
    check("K5: phiên cũ không còn mở được", goto(page, session_url.replace(pw.BASE, "")) == 404)
    ctx.close()


def main():
    cards = pw.gen_cards()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        scenario_3(browser, cards)
        scenario_4(browser, cards)
        scenario_5(browser, cards)
        browser.close()
    events = {a: pw.audit_count(a) for a in ("INTAKE_CREATE", "INTAKE_SAVE", "INTAKE_CANCEL")}
    check(
        "Nhật ký ghi đủ INTAKE_CREATE, INTAKE_SAVE, INTAKE_CANCEL",
        all(v > 0 for v in events.values()),
        str(events),
    )
    return pw.finish()


if __name__ == "__main__":
    sys.exit(main())
