"""Kiểm thử giao diện Phase 5 bằng Playwright: Cài đặt OCR/QR, tải ảnh, màn hình đối chiếu, trường
tô vàng, xoay ảnh, hủy phiên, CV "Đưa vào trường…", phân quyền. Chạy:
    py -3.12 scripts/kiem_thu_giao_dien_phase5.py
Chụp 1366x768 và 390x844 vào docs/screenshots/phase-5/, đọc lỗi console, thử cả trường hợp sai.
"""

import sys

import pw_phase5 as pw
from playwright.sync_api import sync_playwright
from pw_phase5 import CARD_DIR, check, goto, login, new_page, no_h_scroll

OUT = pw.ROOT / "docs" / "screenshots" / "phase-5"


def card(cards, kind, quality="good", nth=0):
    found = [c for c in cards if c["doc_type"] == kind and c["quality"] == quality]
    return found[nth]


def upload(page, c, sides=("front", "back"), cv=None):
    goto(page, "/nhap-cccd/")
    if "front" in sides:
        page.set_input_files("input[name=front_image]", str(CARD_DIR / c["files"]["front"]))
    if "back" in sides:
        page.set_input_files("input[name=back_image]", str(CARD_DIR / c["files"]["back"]))
    if cv:
        page.set_input_files("input[name=cv_file]", str(CARD_DIR / "cv" / cv))
    page.click("button:has-text('Nhận diện')")
    page.wait_for_load_state("networkidle")


def cancel_session(page):
    page.click("button:has-text('Hủy phiên')")
    page.wait_for_selector("#cancel-session.show", timeout=5000)
    page.wait_for_timeout(400)
    page.click("#cancel-session button[data-pa-submit]")
    page.wait_for_load_state("networkidle")


def run_size(browser, size_name, size, cards):
    s = size_name

    # ===== Admin: Cài đặt =====
    ctx, page = new_page(browser, size)
    login(page, "admin")
    status = goto(page, "/cai-dat/")
    check(
        f"[{s}] Admin: /cai-dat/ chuyển tới tab OCR và QR",
        page.url.endswith("/cai-dat/ocr-qr/") and status == 200,
    )
    check(
        f"[{s}] Admin: có tab OCR và QR và 2 khối cấu hình QR",
        page.locator("a.nav-link.active:has-text('OCR và QR')").count() == 1
        and page.locator("h2.pa-card-title:has-text('Cấu hình QR')").count() == 2,
    )
    check(f"[{s}] Admin: không cuộn ngang", no_h_scroll(page))
    check(
        f"[{s}] Admin: API OCR ngoài tắt, không có cảnh báo",
        page.locator(".alert-warning").count() == 0,
    )
    OUT.mkdir(parents=True, exist_ok=True)
    pw.shot(OUT, page, s, "01-cai-dat-ocr-qr")

    # nhập sai: bỏ ô Số CCCD khỏi cấu hình
    page.select_option("select[name=CCCD_2021__pos1]", "")
    page.click("button:has-text('Lưu cài đặt')")
    page.wait_for_load_state("networkidle")
    check(f"[{s}] Admin: cấu hình thiếu Số CCCD bị báo lỗi", "Vị trí 1 để trống" in page.content())
    check(f"[{s}] Admin: có tóm tắt lỗi đầu trang", page.locator(".alert-danger").count() >= 1)
    pw.shot(OUT, page, s, "02-cai-dat-loi")

    goto(page, "/cai-dat/ocr-qr/")
    page.fill("input[name=ocr_confidence_threshold]", "0")
    page.click("button:has-text('Lưu cài đặt')")
    page.wait_for_load_state("networkidle")
    check(
        f"[{s}] Admin: ngưỡng 0 bị báo lỗi", "Ngưỡng tin cậy phải từ 1 đến 100." in page.content()
    )

    if s == "1366x768":
        goto(page, "/cai-dat/ocr-qr/")
        page.fill("input[name=ocr_confidence_threshold]", "75")
        page.check("input[name=external_ocr_enabled]")
        page.fill("input[name=external_ocr_url]", "https://ocr.example.com/api")
        page.click("button:has-text('Lưu cài đặt')")
        page.wait_for_load_state("networkidle")
        check(
            f"[{s}] Admin: lưu thành công có thông báo",
            "Đã lưu cài đặt OCR và QR." in page.content(),
        )
        check(
            f"[{s}] Admin: bật API ngoài hiện cảnh báo gửi ảnh ra ngoài",
            "ảnh giấy tờ sẽ được gửi ra khỏi máy chủ" in page.content(),
        )
        pw.shot(OUT, page, s, "03-cai-dat-api-ngoai")
        page.fill("input[name=ocr_confidence_threshold]", "80")
        page.uncheck("input[name=external_ocr_enabled]")
        page.click("button:has-text('Lưu cài đặt')")
        page.wait_for_load_state("networkidle")
        check(
            f"[{s}] Admin: trả cài đặt về mặc định",
            page.input_value("input[name=ocr_confidence_threshold]") == "80",
        )
    ctx.close()

    # ===== Quản lý, HR, Viewer: không vào được Cài đặt =====
    for user in ("quanly", "hr", "viewer"):
        ctx, page = new_page(browser, size)
        login(page, user)
        check(f"[{s}] {user}: /cai-dat/ bị 403", goto(page, "/cai-dat/ocr-qr/") == 403)
        if user == "viewer":
            check(f"[{s}] viewer: /nhap-cccd/ bị 403", goto(page, "/nhap-cccd/") == 403)
            pw.shot(OUT, page, s, "04-viewer-403")
        ctx.close()

    # ===== HR =====
    ctx, page = new_page(browser, size)
    login(page, "hr")
    check(
        f"[{s}] HR: thẻ 'Từ CCCD và CV' ở trang Thêm hồ sơ mở được",
        goto(page, "/ho-so/them/") == 200
        and page.locator("a.pa-stat[href='/nhap-cccd/']").count() == 1,
    )
    status = goto(page, "/nhap-cccd/")
    check(
        f"[{s}] HR: trang tải ảnh mở được, có ô Loại giấy tờ",
        status == 200 and page.locator("select[name=doc_type]").count() == 1,
    )
    check(f"[{s}] HR: không cuộn ngang ở trang tải ảnh", no_h_scroll(page))
    pw.shot(OUT, page, s, "05-tai-anh")
    page.click("button:has-text('Nhận diện')")
    page.wait_for_load_state("networkidle")
    check(f"[{s}] HR: không chọn tệp nào thì báo lỗi", "Chọn ít nhất một tệp" in page.content())
    page.set_input_files("input[name=front_image]", str(CARD_DIR / "cv" / "cv-mau.pdf"))
    page.click("button:has-text('Nhận diện')")
    page.wait_for_load_state("networkidle")
    check(
        f"[{s}] HR: tệp PDF ở ô ảnh bị từ chối bằng tiếng Việt",
        "chỉ nhận JPG, PNG" in page.content(),
    )
    pw.shot(OUT, page, s, "06-tai-anh-loi")

    # thẻ CCCD 2021 có QR
    c = card(cards, "CCCD_2021")
    upload(page, c)
    check(
        f"[{s}] HR: nhận diện xong chuyển tới màn hình đối chiếu",
        "/nhap-cccd/" in page.url and "Đối chiếu thông tin" in page.content(),
    )
    check(
        f"[{s}] HR: có nhãn nguồn QR và OCR",
        page.locator(".pa-source:has-text('QR')").count() >= 5
        and page.locator(".pa-source:has-text('OCR')").count() >= 1,
    )
    check(f"[{s}] HR: không có trường tô vàng", page.locator(".pa-field--low").count() == 0)
    check(f"[{s}] HR: nút Lưu hồ sơ bật", page.locator("button[data-pa-gate]").is_enabled())
    check(
        f"[{s}] HR: số CCCD điền đúng từ QR",
        page.input_value("input[name=id_number]") == c["values"]["id_number"],
    )
    check(
        f"[{s}] HR: có ảnh hai mặt, nút Phóng to và Xoay ảnh",
        page.locator("img[src*='/tep/mat-truoc/']").count() == 1
        and page.locator("a:has-text('Phóng to')").count() == 2
        and page.locator("button:has-text('Xoay ảnh')").count() == 2,
    )
    check(
        f"[{s}] HR: ảnh tải được (có kích thước)",
        page.evaluate("document.querySelector('img').naturalWidth") > 100,
    )
    check(f"[{s}] HR: không cuộn ngang ở màn hình đối chiếu", no_h_scroll(page))
    pw.shot(OUT, page, s, "07-doi-chieu-qr")

    # sửa một ô máy đọc: nhãn đổi thành Nhập tay
    page.fill("input[name=full_name]", "TÊN SỬA TAY")
    label = page.locator("label[for=id_full_name] .pa-source").inner_text()
    check(f"[{s}] HR: sửa ô họ tên thì nhãn nguồn thành Nhập tay", label == "Nhập tay", label)
    page.fill("input[name=phone]", "0900000001")
    page.click("button[data-pa-gate]")
    page.wait_for_load_state("networkidle")
    check(
        f"[{s}] HR: lưu xong mở chi tiết hồ sơ Nháp",
        "/ho-so/" in page.url and "Đã lưu hồ sơ ở trạng thái Nháp." in page.content(),
    )
    pw.shot(OUT, page, s, "08-sau-khi-luu")

    # thẻ ảnh mờ: trường tô vàng, khóa nút Lưu, tích Đã kiểm tra mới bật
    blur = card(cards, "CCCD_2016", "blur")
    upload(page, blur)
    low = page.locator(".pa-field--low").count()
    check(f"[{s}] HR: thẻ ảnh mờ có trường tô vàng", low >= 5, str(low))
    check(f"[{s}] HR: nút Lưu hồ sơ bị khóa", page.locator("button[data-pa-gate]").is_disabled())
    check(f"[{s}] HR: hiện cảnh báo ảnh mờ", "Ảnh bị mờ" in page.content())
    pw.shot(OUT, page, s, "09-doi-chieu-to-vang")
    boxes = page.locator("input[data-pa-checked]")
    for i in range(boxes.count() - 1):
        boxes.nth(i).check()
    check(
        f"[{s}] HR: tích thiếu một ô thì vẫn khóa",
        page.locator("button[data-pa-gate]").is_disabled(),
    )
    boxes.nth(boxes.count() - 1).check()
    check(f"[{s}] HR: tích đủ thì nút Lưu bật", page.locator("button[data-pa-gate]").is_enabled())
    # hủy phiên qua hộp xác nhận
    page.click("button:has-text('Hủy phiên')")
    page.wait_for_selector("#cancel-session.show", timeout=5000)
    pw.shot(OUT, page, s, "10-hop-huy-phien", modal=True)
    page.click("#cancel-session button[data-pa-submit]")
    page.wait_for_load_state("networkidle")
    check(
        f"[{s}] HR: hủy phiên chuyển về Thêm hồ sơ có thông báo",
        page.url.endswith("/ho-so/them/") and "Đã hủy phiên nhận diện" in page.content(),
    )

    # xoay ảnh
    c12 = card(cards, "CCCD_2016", nth=0)
    upload(page, c12, sides=("front",))
    before = page.evaluate("document.querySelector('img').naturalWidth")
    page.click("button:has-text('Xoay ảnh')")
    page.wait_for_load_state("networkidle")
    after = page.evaluate("document.querySelector('img').naturalWidth")
    check(f"[{s}] HR: xoay ảnh đổi chiều ảnh", before != after, f"{before} -> {after}")
    check(f"[{s}] HR: xoay ảnh có thông báo", "Đã xoay ảnh và nhận diện lại." in page.content())
    cancel_session(page)

    # CV: bôi đen rồi "Đưa vào trường…"
    upload(page, c12, sides=(), cv="cv-mau.docx")
    check(f"[{s}] HR: CV hiện văn bản trích", "Vận hành máy may" in page.input_value("#id_cv_text"))
    check(
        f"[{s}] HR: gợi ý SĐT và email từ CV",
        page.locator("button:has-text('0999000111')").count() == 1
        and page.locator("button:has-text('mau.thu@example.com')").count() == 1,
    )
    check(
        f"[{s}] HR: gợi ý chưa tự điền vào hồ sơ",
        page.input_value("#id_phone") == "" and page.input_value("#id_email") == "",
    )
    pw.shot(OUT, page, s, "11-doi-chieu-cv")
    page.click("button:has-text('Đưa vào trường…')")
    page.click("button[data-pa-insert-selection='id_skills']")
    check(
        f"[{s}] HR: chưa bôi đen thì hiện nhắc",
        "Hãy bôi đen" in page.inner_text("[data-pa-cv-message]"),
    )
    page.evaluate(
        """() => { const t = document.getElementById('id_cv_text');
        const i = t.value.indexOf('Vận hành'); const j = t.value.indexOf('\\n', i);
        t.focus(); t.setSelectionRange(i, j); }"""
    )
    page.click("button:has-text('Đưa vào trường…')")
    page.click("button[data-pa-insert-selection='id_skills']")
    check(
        f"[{s}] HR: đoạn bôi đen vào ô Kỹ năng",
        "Vận hành máy may công nghiệp" in page.input_value("#id_skills"),
        page.input_value("#id_skills"),
    )
    page.click("button[data-pa-insert-value='0999000111']")
    check(f"[{s}] HR: bấm gợi ý SĐT điền vào ô SĐT", page.input_value("#id_phone") == "0999000111")
    pw.shot(OUT, page, s, "12-cv-da-dua-vao-truong")
    # lưu thiếu họ tên: báo lỗi dưới ô
    page.click("button[data-pa-gate]")
    page.wait_for_load_state("networkidle")
    check(
        f"[{s}] HR: thiếu họ tên bị báo lỗi, phiên còn nguyên",
        "Nhập họ và tên." in page.content() and "/nhap-cccd/" in page.url,
    )
    pw.shot(OUT, page, s, "13-doi-chieu-loi")
    cancel_session(page)
    ctx.close()


def main():
    cards = pw.gen_cards()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for size_name, size in pw.SIZES.items():
            run_size(browser, size_name, size, cards)
            cards = pw.gen_cards()  # số CCCD mới cho lượt kích thước sau
        browser.close()
    return pw.finish()


if __name__ == "__main__":
    sys.exit(main())
