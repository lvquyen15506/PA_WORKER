"""Kiểm thử giao diện Phase 3 bằng Playwright (chạy: py -3.12 scripts/kiem_thu_giao_dien_phase3.py).

Cần web chạy ở http://localhost:8000 và 4 tài khoản mẫu với mật khẩu cho trong biến môi trường
PA_TEST_PASSWORD (script dùng chung một mật khẩu cho admin, quanly, hr, viewer).
Chụp 1366x768 và 390x844 vào docs/screenshots/phase-3/, đọc lỗi console, kiểm tra tương tác chính.
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("PA_BASE_URL", "http://localhost:8000")
PASSWORD = os.environ["PA_TEST_PASSWORD"]
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots" / "phase-3"
OUT.mkdir(parents=True, exist_ok=True)
SIZES = {"1366x768": (1366, 768), "390x844": (390, 844)}

results = []
console_errors = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("ĐẠT  " if ok else "LỖI  ") + name + (f" – {detail}" if detail and not ok else ""))


def new_page(browser, size):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, locale="vi-VN")
    page = ctx.new_page()

    def on_console(msg):
        if msg.type == "error":
            console_errors.append((page.url, msg.text))

    page.on("console", on_console)
    page.on("pageerror", lambda e: console_errors.append((page.url, f"pageerror: {e}")))
    return ctx, page


def login(page, username, password=PASSWORD):
    page.goto(f"{BASE}/dang-nhap/")
    page.fill("input[name=username]", username)
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def shot(page, size_name, name):
    page.screenshot(path=str(OUT / f"{name}-{size_name}.png"), full_page=True)


def no_h_scroll(page):
    return page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )


with sync_playwright() as p:
    browser = p.chromium.launch()

    for size_name, size in SIZES.items():
        # --- Đăng nhập (khung tối giản) ---
        ctx, page = new_page(browser, size)
        page.goto(f"{BASE}/dang-nhap/")
        check(
            f"[{size_name}] đăng nhập: không có sidebar/thanh trên",
            page.locator(".pa-sidebar, .pa-topbar").count() == 0,
        )
        check(
            f"[{size_name}] đăng nhập: có 'PA Worker' và chân trang QQIT",
            "Phát triển bởi QQIT" in page.content()
            and page.locator(".pa-auth__brand").count() == 1,
        )
        check(f"[{size_name}] đăng nhập: không cuộn ngang", no_h_scroll(page))
        shot(page, size_name, "dang-nhap")
        page.fill("input[name=username]", "admin")
        page.fill("input[name=password]", "sai-mat-khau-1")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        check(
            f"[{size_name}] đăng nhập sai: hiện thông báo chung",
            "Tên tài khoản hoặc mật khẩu không đúng." in page.content()
            or "không đúng" in page.content(),
        )
        shot(page, size_name, "dang-nhap-sai")
        ctx.close()

        # --- Admin: ui-kit và các trang đã chuyển ---
        ctx, page = new_page(browser, size)
        login(page, "admin")
        check(f"[{size_name}] admin vào được trang chủ", page.url.rstrip("/") == BASE)
        shot(page, size_name, "tong-quan")

        page.goto(f"{BASE}/ui-kit/")
        page.wait_for_load_state("networkidle")
        check(
            f"[{size_name}] /ui-kit/ mở được",
            page.locator("h1.pa-page-header__title").first.inner_text() == "Bộ giao diện mẫu",
        )
        check(f"[{size_name}] /ui-kit/ không cuộn ngang cả trang", no_h_scroll(page))
        check(
            f"[{size_name}] /ui-kit/ biểu đồ đã vẽ",
            page.evaluate("document.querySelector('canvas[data-pa-chart]').width") > 0,
        )
        font = page.evaluate("getComputedStyle(document.body).fontFamily")
        check(f"[{size_name}] font hệ thống (system-ui)", "system-ui" in font, font)
        check(
            f"[{size_name}] cỡ chữ thân 14px",
            page.evaluate("getComputedStyle(document.body).fontSize") == "14px",
        )
        shot(page, size_name, "ui-kit")

        # Hộp xác nhận có trường form: nút chỉ bật khi gõ đúng mã
        page.click("text=Mở hộp có trường form")
        page.wait_for_selector("#modal-form.show")
        btn = page.locator("#modal-form [data-pa-submit]")
        check(f"[{size_name}] hộp xác nhận: nút khóa khi chưa gõ mã", btn.is_disabled())
        page.fill("#modal-form [data-pa-match]", "HS-DEMO-0001")
        check(f"[{size_name}] hộp xác nhận: nút bật khi gõ đúng mã", btn.is_enabled())
        shot(page, size_name, "ui-kit-hop-xac-nhan")
        page.click("#modal-form .btn-close")
        page.wait_for_selector("#modal-form", state="hidden")

        # Menu "Thêm" trong bảng truyền địa chỉ và nội dung vào hộp xác nhận chung
        page.locator("#bang .dropdown-toggle").first.click()
        page.locator("#bang .dropdown-menu.show button.dropdown-item").first.click()
        page.wait_for_selector("#modal-row.show")
        check(
            f"[{size_name}] menu Thêm mở hộp xác nhận có nội dung",
            "HS-DEMO-0001" in page.locator("#modal-row [data-pa-message]").inner_text(),
        )
        page.click("#modal-row .btn-close")
        page.wait_for_selector("#modal-row", state="hidden")

        # Thông báo tự ẩn sau 5 giây
        check(
            f"[{size_name}] thông báo tự ẩn: đang hiện",
            page.locator("#demo-autohide .alert").count() == 1,
        )
        page.wait_for_timeout(5600)
        check(
            f"[{size_name}] thông báo tự ẩn: biến mất sau 5 giây",
            page.locator("#demo-autohide .alert").count() == 0,
        )

        # Nút Lưu của màn hình đối chiếu khóa đến khi tích Đã kiểm tra
        gate = page.locator("[data-pa-gate]")
        check(f"[{size_name}] đối chiếu: nút Lưu khóa khi chưa tích", gate.is_disabled())
        page.check("[data-pa-checked]")
        check(f"[{size_name}] đối chiếu: nút Lưu bật khi đã tích", gate.is_enabled())

        # Menu sidebar thu gọn ở màn hình hẹp
        if size[0] < 992:
            check(
                f"[{size_name}] sidebar ẩn ở màn hình hẹp",
                not page.locator("#paSidebar").is_visible(),
            )
            page.click("button:has-text('Menu')")
            page.wait_for_selector("#paSidebar.show")
            check(f"[{size_name}] nút Menu mở sidebar", page.locator("#paSidebar").is_visible())
            shot(page, size_name, "menu-mo")
            page.keyboard.press("Escape")
        else:
            check(
                f"[{size_name}] sidebar hiện ở màn hình rộng",
                page.locator("#paSidebar").is_visible(),
            )
            check(
                f"[{size_name}] sidebar rộng 240px",
                abs(page.locator("#paSidebar").bounding_box()["width"] - 240) < 1,
            )

        # Trang tài khoản và lịch sử đăng nhập
        for path, name in (
            ("/tai-khoan/", "tai-khoan"),
            ("/tai-khoan/lich-su-dang-nhap/", "lich-su-dang-nhap"),
            ("/tai-khoan/them/", "tai-khoan-them"),
            ("/doi-mat-khau/", "doi-mat-khau"),
            ("/gioi-thieu/", "gioi-thieu"),
        ):
            page.goto(f"{BASE}{path}")
            page.wait_for_load_state("networkidle")
            check(f"[{size_name}] {path} không cuộn ngang cả trang", no_h_scroll(page))
            check(
                f"[{size_name}] {path} có đầu trang",
                page.locator(".pa-page-header__title").count() == 1,
            )
            shot(page, size_name, name)

        # Form sai: thêm tài khoản bỏ trống
        page.goto(f"{BASE}/tai-khoan/them/")
        page.click("button:has-text('Lưu tài khoản')")
        page.wait_for_load_state("networkidle")
        check(
            f"[{size_name}] form thêm tài khoản bỏ trống: hiện lỗi dưới ô",
            page.locator(".pa-form-error").count() >= 1 or page.locator(".is-invalid").count() >= 1,
        )
        shot(page, size_name, "tai-khoan-them-loi")

        # Hộp xác nhận ở trang tài khoản
        page.goto(f"{BASE}/tai-khoan/")
        row = page.locator("tbody tr", has_text="viewer").first
        row.locator(".dropdown-toggle").click()
        page.locator(".dropdown-menu.show button", has_text="Đặt lại mật khẩu").first.click()
        page.wait_for_selector("#account-confirm.show")
        action = page.locator("#account-confirm form").get_attribute("action")
        check(
            f"[{size_name}] tài khoản: hộp xác nhận nhận địa chỉ POST",
            action and action.endswith("/dat-lai-mat-khau/"),
            str(action),
        )
        shot(page, size_name, "tai-khoan-hop-xac-nhan")
        ctx.close()

        # --- Vai trò khác: menu và 403 ---
        for username, expected_menu, forbidden in (
            ("quanly", 7, "/tai-khoan/"),
            ("hr", 5, "/ui-kit/"),
            ("viewer", 4, "/ui-kit/"),
        ):
            ctx, page = new_page(browser, size)
            login(page, username)
            count = page.locator(".pa-nav li").count()
            check(
                f"[{size_name}] {username}: menu có {expected_menu} mục",
                count == expected_menu,
                f"thực tế {count}",
            )
            resp = page.goto(f"{BASE}{forbidden}")
            check(
                f"[{size_name}] {username}: {forbidden} trả 403",
                resp.status == 403,
                str(resp.status),
            )
            check(
                f"[{size_name}] {username}: trang 403 dùng khung chung",
                page.locator(".pa-sidebar").count() == 1 and "Bạn không có quyền" in page.content(),
            )
            if size_name == "1366x768":
                shot(page, size_name, f"403-{username}")
            ctx.close()

    browser.close()

# Lỗi console: chỉ cho phép phản hồi 403 mong đợi
unexpected = [(u, t) for u, t in console_errors if "403" not in t and "Forbidden" not in t]
check(
    "không có lỗi console ngoài 403 mong đợi",
    not unexpected,
    "; ".join(f"{u}: {t}" for u, t in unexpected),
)
failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} bước đạt")
sys.exit(1 if failed else 0)
