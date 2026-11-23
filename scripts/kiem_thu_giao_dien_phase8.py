"""Kiểm thử giao diện Phase 8 (Playwright, Python 3.12 64-bit): trang lỗi tiếng Việt, phiên bản ở
chân trang, CSP không chặn chức năng nào của trang đổi ở Phase 8 (nút in, mở lại hộp xác nhận).
    py -3.12 scripts/kiem_thu_giao_dien_phase8.py
Cần web ở http://localhost:8000, 4 tài khoản admin, quanly, hr, viewer dùng chung mật khẩu trong
PA_TEST_PASSWORD. Ảnh chụp vào docs/screenshots/phase-8/.
"""

import sys

import pw_phase5 as pw
from playwright.sync_api import sync_playwright
from pw_phase5 import check, db, goto, login, new_page, no_h_scroll

OUT = pw.ROOT / "docs" / "screenshots" / "phase-8"
VERSION = "1.1.0"
# Trang 400 được gọi cố ý (sai địa chỉ) và kiểm tra riêng ở bước "400 sai địa chỉ".
pw.EXPECTED_NOISE = pw.EXPECTED_NOISE + ("status of 400",)


def run_size(browser, size_name, size):
    s = size_name
    ctx, page = new_page(browser, size)

    # Trang đăng nhập: phiên bản ở chân trang
    goto(page, "/dang-nhap/")
    check(f"[{s}] Đăng nhập: chân trang ghi v{VERSION}", f"PA Worker v{VERSION}" in page.content())
    pw.shot(OUT, page, s, "01-dang-nhap")

    # 404 khi chưa đăng nhập (đường dẫn không tồn tại): khung tối giản tiếng Việt
    status = goto(page, "/khong-co-trang-nay/")
    check(
        f"[{s}] 404 chưa đăng nhập: tiếng Việt",
        status == 404 and "Không tìm thấy trang" in page.content(),
    )
    check(f"[{s}] 404: không cuộn ngang", no_h_scroll(page))
    pw.shot(OUT, page, s, "02-loi-404")

    # 400 khi sai ALLOWED_HOSTS (gọi bằng 127.0.0.2 không có trong danh sách)
    status = page.goto("http://127.0.0.2:8000/dang-nhap/")
    status = status.status if status else 0
    check(
        f"[{s}] 400 sai địa chỉ: hướng dẫn ALLOWED_HOSTS",
        status == 400 and "ALLOWED_HOSTS" in page.content(),
    )
    pw.shot(OUT, page, s, "03-loi-400")

    # Đã đăng nhập: chân trang, Giới thiệu, 404
    login(page, "hr")
    goto(page, "/gioi-thieu/")
    check(f"[{s}] Giới thiệu: phiên bản {VERSION}", VERSION in page.content())
    check(f"[{s}] Chân trang: v{VERSION}", f"PA Worker v{VERSION}" in page.content())
    pw.shot(OUT, page, s, "04-gioi-thieu")
    status = goto(page, "/ho-so/999999999/")
    check(
        f"[{s}] 404 đã đăng nhập: tiếng Việt",
        status == 404 and "Không tìm thấy trang" in page.content(),
    )

    # Nút in (thay onclick nội tuyến): bấm được, gọi window.print
    pk = db(
        "from apps.workers.models import Worker;print(Worker.objects.order_by('pk').first().pk)"
    )
    goto(page, f"/ho-so/{pk}/dong-y/mau-in/")
    page.evaluate(
        "window.__printed = false; window.print = function () { window.__printed = true; }"
    )
    page.click("button[data-pa-print]")
    check(f"[{s}] Nút In văn bản chạy dưới CSP", page.evaluate("window.__printed") is True)
    goto(page, "/bao-cao/in/")
    page.evaluate(
        "window.__printed = false; window.print = function () { window.__printed = true; }"
    )
    page.click("button[data-pa-print]")
    check(f"[{s}] Nút In báo cáo chạy dưới CSP", page.evaluate("window.__printed") is True)
    ctx.close()

    # Hộp xác nhận mở lại khi máy chủ trả lỗi (thay script nội tuyến ở chi tiết hồ sơ):
    # Quản lý trả lại hồ sơ Chờ duyệt mà bỏ trống lý do.
    pending = db(
        "from apps.workers.models import Worker;"
        "w=Worker.objects.filter(verification_status='PENDING').exclude(created_by__username='quanly')"
        ".exclude(status_changes__changed_by__username='quanly').first();print(w.pk if w else '')"
    )
    if pending:
        ctx, page = new_page(browser, size)
        login(page, "quanly")
        goto(page, f"/ho-so/{pending}/")
        page.click("button:has-text('Trả lại')")
        page.wait_for_timeout(500)
        page.locator(".modal.show button[type=submit]").click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(600)
        check(
            f"[{s}] Lỗi lý do trống: hộp xác nhận tự mở lại",
            page.locator(".modal.show").count() == 1,
        )
        pw.shot(OUT, page, s, "05-hop-xac-nhan-mo-lai", modal=True)
        ctx.close()
    else:
        check(f"[{s}] Có hồ sơ Chờ duyệt để thử hộp xác nhận", False, "không tìm thấy")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, size in pw.SIZES.items():
            run_size(browser, name, size)
        browser.close()
    return pw.finish()


if __name__ == "__main__":
    sys.exit(main())
