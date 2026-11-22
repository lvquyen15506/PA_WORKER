"""Nghiệm thu kịch bản 1 và 15 trên giao diện mới (Phase 3), bằng Playwright.

Chạy: py -3.12 scripts/nghiem_thu_1_15_phase3.py
Biến môi trường: PA_PW_ADMIN, PA_PW_QUANLY, PA_PW_HR, PA_PW_VIEWER (mật khẩu tạm in ra bởi
seed_demo), PA_NEW_PASSWORD (mật khẩu mới dùng khi bị buộc đổi), PA_BASE_URL (mặc định
http://localhost:8000). Ảnh chụp vào docs/screenshots/phase-3/nghiem-thu/.
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("PA_BASE_URL", "http://localhost:8000")
NEW_PASSWORD = os.environ["PA_NEW_PASSWORD"]
TEMP = {
    "admin": os.environ["PA_PW_ADMIN"],
    "quanly": os.environ["PA_PW_QUANLY"],
    "hr": os.environ["PA_PW_HR"],
    "viewer": os.environ["PA_PW_VIEWER"],
}
MENU = {"admin": 9, "quanly": 7, "hr": 5, "viewer": 4}
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots" / "phase-3" / "nghiem-thu"
OUT.mkdir(parents=True, exist_ok=True)

results, console_errors = [], []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("ĐẠT  " if ok else "LỖI  ") + name + (f" – {detail}" if detail and not ok else ""))


def new_page(browser, width=1366, height=768):
    ctx = browser.new_context(viewport={"width": width, "height": height}, locale="vi-VN")
    page = ctx.new_page()
    page.on(
        "console",
        lambda m: console_errors.append((page.url, m.text)) if m.type == "error" else None,
    )
    page.on("pageerror", lambda e: console_errors.append((page.url, str(e))))
    return ctx, page


def submit_login(page, username, password):
    page.goto(f"{BASE}/dang-nhap/")
    page.fill("input[name=username]", username)
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def alert_text(page):
    loc = page.locator(".alert")
    return loc.first.inner_text() if loc.count() else ""


with sync_playwright() as p:
    browser = p.chromium.launch()

    # ===== Kịch bản 1: cài mới, 4 tài khoản mẫu đăng nhập lần đầu =====
    for user, expected in MENU.items():
        ctx, page = new_page(browser)
        submit_login(page, user, TEMP[user])
        check(
            f"[1] {user}: mật khẩu tạm bị buộc đổi", page.url.endswith("/doi-mat-khau/"), page.url
        )
        check(f"[1] {user}: có thông báo mật khẩu tạm", "mật khẩu tạm" in alert_text(page))
        # chưa đổi thì mọi trang khác chuyển về đổi mật khẩu
        page.goto(f"{BASE}/")
        check(
            f"[1] {user}: trang khác bị chuyển về đổi mật khẩu", page.url.endswith("/doi-mat-khau/")
        )
        page.fill("input[name=old_password]", TEMP[user])
        page.fill("input[name=new_password1]", NEW_PASSWORD)
        page.fill("input[name=new_password2]", NEW_PASSWORD)
        page.click("main button[type=submit]")
        page.wait_for_load_state("networkidle")
        check(f"[1] {user}: đổi mật khẩu xong về trang tổng quan", page.url.rstrip("/") == BASE)
        check(f"[1] {user}: có thông báo đã đổi mật khẩu", "Đã đổi mật khẩu." in alert_text(page))
        count = page.locator(".pa-nav li").count()
        check(f"[1] {user}: menu có {expected} mục", count == expected, f"thực tế {count}")
        check(
            f"[1] {user}: tên và vai trò ở thanh trên",
            page.locator(".pa-topbar .dropdown-toggle").count() == 1,
        )
        page.screenshot(path=str(OUT / f"kb1-{user}.png"), full_page=True)
        page.click(".pa-topbar .dropdown-toggle")
        page.click("button:has-text('Đăng xuất')")
        page.wait_for_load_state("networkidle")
        check(f"[1] {user}: đăng xuất về trang đăng nhập", page.url.endswith("/dang-nhap/"))
        submit_login(page, user, NEW_PASSWORD)
        check(f"[1] {user}: đăng nhập lại bằng mật khẩu mới", page.url.rstrip("/") == BASE)
        ctx.close()

    # ===== Kịch bản 15: sai 5 lần -> khóa tạm -> Admin mở khóa =====
    ctx, page = new_page(browser)
    for i in range(1, 5):
        submit_login(page, "hr", f"sai-mat-khau-{i}")
        check(
            f"[15] lần sai {i}: báo sai chung", "không đúng" in alert_text(page), alert_text(page)
        )
    # Lần sai thứ 5 kích hoạt khóa tạm nên báo khóa tạm kèm giờ (xem tests/test_accounts_login.py)
    submit_login(page, "hr", "sai-mat-khau-5")
    msg5 = alert_text(page)
    check("[15] lần sai 5: khóa tạm kèm giờ", "tạm khóa" in msg5 and "Thử lại sau" in msg5, msg5)
    page.screenshot(path=str(OUT / "kb15-sai-5-lan.png"), full_page=True)
    submit_login(page, "hr", NEW_PASSWORD)  # đúng mật khẩu nhưng đang bị khóa tạm
    msg = alert_text(page)
    check(
        "[15] lần 6 (đúng mật khẩu): báo khóa tạm kèm giờ",
        "tạm khóa" in msg and "Thử lại sau" in msg,
        msg,
    )
    check("[15] lần 6: vẫn chưa vào được", page.url.endswith("/dang-nhap/"))
    page.screenshot(path=str(OUT / "kb15-khoa-tam.png"), full_page=True)
    ctx.close()

    ctx, page = new_page(browser)
    submit_login(page, "admin", NEW_PASSWORD)
    page.goto(f"{BASE}/tai-khoan/")
    row = page.locator("tbody tr", has_text="hr").filter(has_text="Nhân Viên").first
    check(
        "[15] Admin thấy hr ở trạng thái Khóa tạm", "Khóa tạm" in row.inner_text(), row.inner_text()
    )
    check("[15] nhãn Khóa tạm màu vàng", row.locator(".pa-badge--warning").count() == 1)
    page.screenshot(path=str(OUT / "kb15-admin-thay-khoa.png"), full_page=True)
    row.locator(".dropdown-toggle").click()
    page.locator(".dropdown-menu.show button", has_text="Mở khóa").click()
    page.wait_for_selector("#account-confirm.show")
    page.click("#account-confirm [data-pa-submit]")
    page.wait_for_load_state("networkidle")
    check(
        "[15] Admin mở khóa: thông báo thành công",
        "Đã mở khóa tài khoản." in alert_text(page),
        alert_text(page),
    )
    row = page.locator("tbody tr", has_text="hr").filter(has_text="Nhân Viên").first
    check("[15] hr trở lại Đang hoạt động", "Đang hoạt động" in row.inner_text(), row.inner_text())
    ctx.close()

    ctx, page = new_page(browser)
    submit_login(page, "hr", NEW_PASSWORD)
    check("[15] hr đăng nhập lại được sau khi mở khóa", page.url.rstrip("/") == BASE, page.url)
    ctx.close()

    # Tài khoản bị Admin khóa: thông báo khác với khóa tạm
    ctx, page = new_page(browser)
    submit_login(page, "admin", NEW_PASSWORD)
    page.goto(f"{BASE}/tai-khoan/")
    row = page.locator("tbody tr", has_text="Người Xem Mẫu").first
    row.locator(".dropdown-toggle").click()
    page.locator(".dropdown-menu.show button", has_text="Khóa tài khoản").click()
    page.wait_for_selector("#account-confirm.show")
    page.click("#account-confirm [data-pa-submit]")
    page.wait_for_load_state("networkidle")
    row = page.locator("tbody tr", has_text="Người Xem Mẫu").first
    check(
        "[15] Admin khóa viewer: nhãn Bị khóa màu đỏ",
        row.locator(".pa-badge--danger").count() == 1,
        row.inner_text(),
    )
    ctx2, page2 = new_page(browser)
    submit_login(page2, "viewer", NEW_PASSWORD)
    check(
        "[15] viewer bị Admin khóa: thông báo khác khóa tạm",
        "Tài khoản đã bị khóa. Liên hệ Admin." in alert_text(page2),
        alert_text(page2),
    )
    ctx2.close()
    row.locator(".dropdown-toggle").click()
    page.locator(".dropdown-menu.show button", has_text="Mở khóa").click()
    page.wait_for_selector("#account-confirm.show")
    page.click("#account-confirm [data-pa-submit]")
    page.wait_for_load_state("networkidle")
    check(
        "[15] Admin mở khóa viewer", "Đã mở khóa tài khoản." in alert_text(page), alert_text(page)
    )
    ctx.close()

    browser.close()

unexpected = [(u, t) for u, t in console_errors if "403" not in t and "Forbidden" not in t]
check("không có lỗi console", not unexpected, "; ".join(f"{u}: {t}" for u, t in unexpected))
print(f"\n{sum(results)}/{len(results)} bước đạt")
sys.exit(0 if all(results) else 1)
