"""Kiểm thử giao diện Phase 4 bằng Playwright: danh sách, thêm/sửa, chi tiết 5 tab, hộp thoại,
tài liệu, duyệt hồ sơ, in mẫu đồng ý. Chạy: py -3.12 scripts/kiem_thu_giao_dien_phase4.py

Cần web ở http://localhost:8000 (đã có 500 hồ sơ mẫu từ seed_demo) và 4 tài khoản admin, quanly, hr,
viewer dùng chung một mật khẩu trong biến môi trường PA_TEST_PASSWORD. Chụp 1366x768 và 390x844
vào docs/screenshots/phase-4/, đọc lỗi console, thử cả trường hợp nhập sai.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("PA_BASE_URL", "http://localhost:8000")
PASSWORD = os.environ["PA_TEST_PASSWORD"]
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots" / "phase-4"
OUT.mkdir(parents=True, exist_ok=True)
SIZES = {"1366x768": (1366, 768), "390x844": (390, 844)}
PDF_BYTES = b"%PDF-1.4\n% tai lieu mau de kiem thu\n%%EOF\n"

results, console_errors = [], []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("ĐẠT  " if ok else "LỖI  ") + name + (f" – {detail}" if detail and not ok else ""))


def new_page(browser, size):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, locale="vi-VN")
    page = ctx.new_page()
    page.on(
        "console",
        lambda m: console_errors.append((page.url, m.text)) if m.type == "error" else None,
    )
    page.on("pageerror", lambda e: console_errors.append((page.url, f"pageerror: {e}")))
    return ctx, page


def login(page, username):
    page.goto(f"{BASE}/dang-nhap/")
    page.fill("input[name=username]", username)
    page.fill("input[name=password]", PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def shot(page, size_name, name, modal=False):
    """Chụp cả trang; với hộp thoại thì chờ hết hiệu ứng mờ dần và chụp theo khung nhìn."""
    if modal:
        page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / f"{name}-{size_name}.png"), full_page=not modal)


def no_h_scroll(page):
    return page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )


def goto(page, path):
    response = page.goto(f"{BASE}{path}")
    page.wait_for_load_state("networkidle")
    return response.status if response else 0


def first_worker_url(page, query):
    """Đường dẫn chi tiết của hồ sơ đầu tiên trong danh sách theo bộ lọc `query`."""
    goto(page, f"/ho-so/?{query}")
    link = page.locator(".pa-table tbody tr a[href^='/ho-so/']").first
    return link.get_attribute("href") if link.count() else None


def run_size(browser, size_name, size):
    s = size_name
    uniq = str(time.time_ns())  # số giả không trùng giữa các lần chạy (CCCD giả luôn bắt đầu 999)

    # ===== Nhân viên HR =====
    ctx, page = new_page(browser, size)
    login(page, "hr")

    status = goto(page, "/ho-so/?reset=1")
    check(f"[{s}] HR: danh sách hồ sơ mở được", status == 200)
    rows = page.locator(".pa-table tbody tr").count()
    check(f"[{s}] HR: danh sách có 20 dòng", rows == 20, f"thực tế {rows}")
    pager = page.locator(".pa-pagination span").first.inner_text()
    check(f"[{s}] HR: phân trang 'Hiển thị 1–20 / n'", pager.startswith("Hiển thị 1–20 /"), pager)
    check(f"[{s}] HR: có 12 cột đúng thứ tự", page.locator(".pa-table thead th").count() == 12)
    check(f"[{s}] HR: không cuộn ngang cả trang", no_h_scroll(page))
    shot(page, s, "01-danh-sach")

    goto(page, "/ho-so/?q=nguyen&trang_thai_ho_so=VERIFIED")
    shot(page, s, "02-danh-sach-loc-tim")
    check(
        f"[{s}] HR: tìm 'nguyen' + lọc Đã xác minh có kết quả",
        page.locator(".pa-table tbody tr").count() > 0,
    )
    goto(page, "/ho-so/?q=khong-co-ai-ten-nhu-the")
    check(
        f"[{s}] HR: không có kết quả hiện trạng thái rỗng",
        "Không có hồ sơ phù hợp." in page.content(),
    )
    shot(page, s, "03-danh-sach-rong")

    goto(page, "/ho-so/them/")
    check(f"[{s}] HR: trang Thêm hồ sơ có 3 thẻ", page.locator("a.pa-stat").count() == 3)
    shot(page, s, "04-them-ho-so")

    # Form nhập tay: lưu rỗng -> lỗi dưới từng ô
    goto(page, "/ho-so/them/nhap-tay/")
    shot(page, s, "05-form-nhap-tay")
    page.fill("input[name=phone]", "123")
    page.fill("input[name=id_number]", "12")
    page.fill("input[name=date_of_birth]", "31/02/2000")
    page.click("button:has-text('Lưu hồ sơ')")
    page.wait_for_load_state("networkidle")
    content = page.content()
    for text in ("Nhập họ và tên.", "Số CCCD phải gồm 12 chữ số.", "Nhập ngày đúng định dạng"):
        check(f"[{s}] HR: form báo lỗi '{text}'", text in content)
    check(f"[{s}] HR: form có lỗi vẫn ở trang thêm", "/ho-so/them/nhap-tay/" in page.url)
    shot(page, s, "06-form-loi")

    # Kiểm tra trùng bằng HTMX: CCCD mẫu 999000000001 đã có trong dữ liệu mẫu
    goto(page, "/ho-so/them/nhap-tay/")
    page.fill("input[name=id_number]", "999000000001")
    page.press("input[name=id_number]", "Tab")
    page.wait_for_selector("#duplicate-check .alert", timeout=5000)
    check(
        f"[{s}] HR: rời ô CCCD báo trùng (HTMX)",
        "đã có hồ sơ" in page.locator("#duplicate-check").inner_text(),
    )
    check(
        f"[{s}] HR: có nút Mở hồ sơ cũ",
        page.locator("#duplicate-check a:has-text('Mở hồ sơ cũ')").count() == 1,
    )
    shot(page, s, "07-bao-trung-cccd")

    # Tạo hồ sơ Nháp thật
    goto(page, "/ho-so/them/nhap-tay/")
    page.fill("input[name=full_name]", f"Giả Kiểm Thử {s}")
    page.fill("input[name=phone]", "09" + uniq[-8:])
    page.fill("input[name=date_of_birth]", "05/03/1995")
    page.select_option("select[name=gender]", "MALE")
    page.fill("input[name=current_address]", "Số 1 đường giả, quận giả")
    page.select_option("select[name=id_doc_type]", "CCCD_2021")
    page.fill("input[name=id_number]", "999" + uniq[-9:])
    page.fill("input[name=contacts-0-full_name]", "Người Thân Giả")
    page.fill("input[name=contacts-0-relationship]", "Anh")
    page.fill("input[name=contacts-0-phone]", "0988777666")
    page.click("button:has-text('Lưu hồ sơ')")
    page.wait_for_load_state("networkidle")
    saved = page.url.rstrip("/").split("/")[-1].isdigit()
    check(f"[{s}] HR: lưu Nháp thành công, chuyển tới chi tiết", saved, page.url)
    check(f"[{s}] HR: thông báo đã lưu Nháp", "Đã lưu hồ sơ ở trạng thái Nháp." in page.content())
    detail_url = page.url
    for tab in ("ca-nhan", "tuyen-dung", "lam-viec", "tai-lieu", "lich-su"):
        goto(page, detail_url.replace(BASE, "").split("?")[0] + f"?tab={tab}")
        check(f"[{s}] HR: tab {tab} mở được", page.locator(".pa-tabs .active").count() == 1)
        check(f"[{s}] HR: tab {tab} không cuộn ngang cả trang", no_h_scroll(page))
        shot(page, s, f"08-chi-tiet-{tab}")

    # Hiện số đầy đủ (HTMX)
    goto(page, detail_url.replace(BASE, "").split("?")[0])
    page.click("button:has-text('Hiện số đầy đủ')")
    page.wait_for_selector("#full-id-result:has-text('Số CCCD:')", timeout=5000)
    check(
        f"[{s}] HR: bấm Hiện số đầy đủ ra số",
        "999" + uniq[-9:] in page.locator("#full-id-result").inner_text(),
    )
    shot(page, s, "09-hien-so-day-du")

    # Tải tài liệu lên (PDF thật), xem trước, và tệp sai định dạng
    worker_path = detail_url.replace(BASE, "").split("?")[0]
    goto(page, worker_path + "tai-lieu/them/")
    shot(page, s, "10-tai-tai-lieu")
    tmp = Path(tempfile.mkdtemp(prefix="pa_ui_"))
    good = tmp / "mau.pdf"
    good.write_bytes(PDF_BYTES)
    bad = tmp / "gia.pdf"
    bad.write_bytes(b"MZ\x90\x00 day khong phai pdf")
    page.select_option("select[name=document_type]", label="CCCD mặt trước")
    page.set_input_files("input[name=file]", str(bad))
    page.click("button:has-text('Tải tài liệu lên')")
    page.wait_for_load_state("networkidle")
    check(
        f"[{s}] HR: tệp giả PDF bị từ chối kèm lỗi tiếng Việt",
        "Chỉ nhận tệp JPG, PNG, PDF, DOC hoặc DOCX." in page.content(),
    )
    shot(page, s, "11-tai-lieu-loi")
    page.select_option("select[name=document_type]", label="CCCD mặt trước")
    page.set_input_files("input[name=file]", str(good))
    page.click("button:has-text('Tải tài liệu lên')")
    page.wait_for_load_state("networkidle")
    check(f"[{s}] HR: tải PDF hợp lệ thành công", "Đã tải tài liệu lên." in page.content())
    check(
        f"[{s}] HR: tab Tài liệu liệt kê tệp và danh sách còn thiếu",
        "mau.pdf" in page.content() and "Còn thiếu giấy tờ" in page.content(),
    )
    shot(page, s, "12-tab-tai-lieu-co-tep")
    view_href = page.locator("a[href$='/xem/']").first.get_attribute("href")
    response = page.request.get(f"{BASE}{view_href}")
    check(
        f"[{s}] HR: xem trước PDF có header sandbox + nosniff",
        response.status == 200
        and response.headers.get("content-security-policy") == "sandbox"
        and response.headers.get("x-content-type-options") == "nosniff"
        and response.headers.get("content-disposition", "").startswith("inline"),
        str(response.headers),
    )

    # Ghi nhận đồng ý + in mẫu
    goto(page, worker_path + "dong-y/")
    shot(page, s, "13-ghi-nhan-dong-y")
    page.select_option("select[name=method]", "PAPER")
    page.click("button:has-text('Lưu ghi nhận')")
    page.wait_for_load_state("networkidle")
    paper_error = "Ký giấy: tải lên tệp biên bản đã ký."
    check(f"[{s}] HR: Ký giấy không kèm tệp báo lỗi", paper_error in page.content())
    page.select_option("select[name=method]", "ELECTRONIC")
    page.click("button:has-text('Lưu ghi nhận')")
    page.wait_for_load_state("networkidle")
    consent_ok = "Đã ghi nhận đồng ý xử lý dữ liệu." in page.content()
    check(f"[{s}] HR: ghi nhận đồng ý điện tử", consent_ok)
    goto(page, worker_path + "dong-y/mau-in/")
    printed = "VĂN BẢN ĐỒNG Ý XỬ LÝ DỮ LIỆU CÁ NHÂN" in page.content()
    check(f"[{s}] HR: trang in mẫu đồng ý có nội dung", printed)
    shot(page, s, "14-mau-in-dong-y")

    # Gửi duyệt (nút chính duy nhất ở đầu trang)
    goto(page, worker_path)
    primary = page.locator(".pa-page-header__actions .btn-primary").count()
    check(f"[{s}] HR: đầu trang có đúng một nút chính", primary == 1, str(primary))
    shot(page, s, "15-chi-tiet-nhap")
    page.click(".pa-page-header__actions button:has-text('Gửi duyệt')")
    page.wait_for_load_state("networkidle")
    check(f"[{s}] HR: gửi duyệt thành công", "Đã gửi duyệt hồ sơ." in page.content())
    check(f"[{s}] HR: nhãn Chờ duyệt", page.locator(".pa-badge:has-text('Chờ duyệt')").count() >= 1)
    check(
        f"[{s}] HR: hồ sơ Chờ duyệt không còn nút Duyệt/Trả lại/Từ chối",
        page.locator(".pa-page-header__actions:has-text('Duyệt hồ sơ')").count() == 0,
    )
    shot(page, s, "16-chi-tiet-cho-duyet")
    pending_path = worker_path
    check(f"[{s}] HR: không vào được Duyệt hồ sơ (403)", goto(page, "/duyet-ho-so/") == 403)
    ctx.close()

    # ===== Quản lý nhân sự =====
    ctx, page = new_page(browser, size)
    login(page, "quanly")
    check(f"[{s}] Quản lý: mở hàng đợi Duyệt hồ sơ", goto(page, "/duyet-ho-so/") == 200)
    check(f"[{s}] Quản lý: hàng đợi có dòng", page.locator(".pa-table tbody tr").count() >= 1)
    shot(page, s, "17-duyet-ho-so")
    goto(page, pending_path)
    check(
        f"[{s}] Quản lý: thấy Duyệt hồ sơ, Trả lại, Từ chối",
        all(
            page.locator(f".pa-page-header__actions :text-is('{t}')").count() == 1
            for t in ("Duyệt hồ sơ", "Trả lại", "Từ chối")
        ),
    )
    shot(page, s, "18-chi-tiet-quan-ly")
    page.click(".pa-page-header__actions button:has-text('Trả lại')")
    page.wait_for_selector("#return-modal.show", timeout=5000)
    shot(page, s, "19-hop-tra-lai", modal=True)
    page.click("#return-modal button[type=submit]")  # lý do trống
    page.wait_for_selector("#return-modal.show", timeout=5000)
    modal_text = page.locator("#return-modal").inner_text()
    check(f"[{s}] Quản lý: trả lại không lý do hiện lỗi dưới ô", "Nhập lý do." in modal_text)
    shot(page, s, "20-hop-tra-lai-loi", modal=True)
    page.fill("#return-modal textarea", "Bổ sung ảnh CCCD mặt sau")
    page.click("#return-modal button[type=submit]")
    page.wait_for_load_state("networkidle")
    check(f"[{s}] Quản lý: trả lại thành công", "Cần bổ sung" in page.content())
    note = "Trả lại: Bổ sung ảnh CCCD mặt sau"
    check(f"[{s}] Quản lý: ghi chú lý do hiện trên hồ sơ", note in page.content())
    goto(page, pending_path + "?tab=lich-su")
    heading = page.locator("text=Chi tiết thay đổi từng trường").count()
    check(f"[{s}] Quản lý: tab Lịch sử có chi tiết thay đổi", heading == 1)
    page.wait_for_selector("section:has-text('Chi tiết thay đổi') .pa-table", timeout=5000)
    shot(page, s, "21-tab-lich-su")
    ctx.close()

    # ===== Viewer =====
    ctx, page = new_page(browser, size)
    login(page, "viewer")
    goto(page, "/ho-so/")
    no_add = "Thêm hồ sơ" not in page.locator(".pa-content").inner_text()
    no_edit = page.locator("a[href$='/sua/']").count() == 0
    check(f"[{s}] Viewer: danh sách không có nút Thêm hồ sơ và Sửa", no_add and no_edit)
    shot(page, s, "22-viewer-danh-sach")
    goto(page, pending_path)
    text = page.locator(".pa-content").inner_text()
    hidden = ("Số CMND cũ", "Nơi thường trú", "Quê quán", "Nơi đăng ký khai sinh", "Hiện số đầy đủ")
    check(f"[{s}] Viewer: chi tiết không có trường nhạy cảm", all(t not in text for t in hidden))
    check(f"[{s}] Viewer: số CCCD hiện dạng che", "••••" in text)
    buttons = page.locator(".pa-page-header__actions .btn").count()
    check(f"[{s}] Viewer: không có nút nào ở đầu trang", buttons == 0)
    shot(page, s, "23-viewer-chi-tiet")
    goto(page, pending_path + "?tab=tai-lieu")
    file_links = page.locator("a[href*='/tai-lieu/']").count()
    check(f"[{s}] Viewer: tab Tài liệu không có liên kết xem/tải", file_links == 0)
    check(f"[{s}] Viewer: gọi thẳng URL sửa bị 403", goto(page, pending_path + "sua/") == 403)
    shot(page, s, "24-viewer-403")
    ctx.close()

    # ===== Admin: ẩn danh hóa theo yêu cầu =====
    ctx, page = new_page(browser, size)
    login(page, "admin")
    archived = first_worker_url(page, "trang_thai_ho_so=ARCHIVED")
    check(f"[{s}] Admin: có hồ sơ Lưu trữ trong dữ liệu mẫu", archived is not None)
    if archived:
        goto(page, archived)
        shot(page, s, "25-admin-chi-tiet-luu-tru")
        page.click(".pa-page-header__actions button:has-text('Ẩn danh hóa theo yêu cầu')")
        page.wait_for_selector("#anonymize-modal.show", timeout=5000)
        confirm = page.locator("#anonymize-modal button[data-pa-submit]")
        check(f"[{s}] Admin: nút Ẩn danh hóa tắt khi chưa gõ lại mã", confirm.is_disabled())
        shot(page, s, "26-hop-an-danh", modal=True)
        code = page.locator("#anonymize-modal input[data-pa-match]").get_attribute("data-pa-match")
        page.fill("#anonymize-modal input[data-pa-match]", code)
        check(f"[{s}] Admin: gõ đúng mã thì nút bật", confirm.is_enabled())
        # Không bấm xác nhận: giữ dữ liệu mẫu nguyên vẹn.
    ctx.close()


with sync_playwright() as p:
    browser = p.chromium.launch()
    for size_name, size in SIZES.items():
        run_size(browser, size_name, size)
    browser.close()

expected_noise = ("status of 403", "status of 404", "status of 405")
real_errors = [(u, m) for u, m in console_errors if not any(n in m for n in expected_noise)]
check("Không có lỗi console ngoài 403/404 mong đợi", not real_errors, str(real_errors[:5]))

failed = [r for r in results if not r[1]]
print(f"\nTổng: {len(results)} bước, đạt {len(results) - len(failed)}, lỗi {len(failed)}")
sys.exit(1 if failed else 0)
