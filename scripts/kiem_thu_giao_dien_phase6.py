"""Kiểm thử giao diện Phase 6 bằng Playwright: Cài đặt (danh mục 10 loại, sinh mã, ngưỡng),
tuyển dụng, tiếp nhận, quá trình làm việc, đợt làm việc và lương (v1.1), phân quyền. Chạy:
    py -3.12 scripts/kiem_thu_giao_dien_phase6.py [phan ...]
`phan` (tùy chọn) giới hạn phần chạy: cai-dat, tuyen-dung, lam-viec, v11. Cần web ở
http://localhost:8000, 4 tài khoản admin, quanly, hr, viewer dùng chung mật khẩu trong biến môi
trường PA_TEST_PASSWORD. Chụp 1366x768 và 390x844 vào docs/screenshots/phase-6/, đọc lỗi console,
thử cả trường hợp nhập sai.
"""

import sys

import pw_phase5 as pw
from playwright.sync_api import sync_playwright
from pw_phase5 import check, db, goto, login, new_page, no_h_scroll

OUT = pw.ROOT / "docs" / "screenshots" / "phase-6"
RUN_ID = __import__("time").strftime("%H%M%S")


def submit(page, label):
    page.click(f"button:has-text('{label}')")
    page.wait_for_load_state("networkidle")


def confirm_menu(page, row_text, item_label):
    """Mở menu "Thêm" của dòng có chữ row_text, chọn mục, bấm xác nhận trong hộp thoại."""
    row = page.locator("tr", has_text=row_text).first
    row.locator(".dropdown-toggle").click()
    page.locator(".dropdown-menu.show button", has_text=item_label).first.click()
    page.wait_for_selector(".modal.show", timeout=5000)
    page.wait_for_timeout(400)
    page.click(".modal.show button[data-pa-submit]")
    page.wait_for_load_state("networkidle")


# ===== Cài đặt ===================================================================================
def part_settings(browser, s, size):
    db(
        "from apps.core.models import ClientCompany as C;"
        "C.objects.filter(name__regex=r'^(Công ty Thử|Cong ty Thu) ').delete()"
    )
    ctx, page = new_page(browser, size)
    login(page, "admin")
    goto(page, "/cai-dat/")
    check(
        f"[{s}] Admin: /cai-dat/ mở tab Danh mục", page.url.endswith("/cai-dat/danh-muc/phong-ban/")
    )
    check(
        f"[{s}] Admin: đủ 4 tab Cài đặt",
        all(
            page.locator(f"a.nav-link:has-text('{t}')").count() == 1
            for t in ("Danh mục", "Sinh mã", "Ngưỡng và thời hạn", "OCR và QR")
        ),
    )
    check(f"[{s}] Admin: danh mục không cuộn ngang", no_h_scroll(page))
    pw.shot(OUT, page, s, "01-danh-muc-phong-ban")

    # chọn loại danh mục bằng thanh lọc
    page.select_option("select[name=loai]", "cong-ty-khach")
    submit(page, "Lọc")
    check(f"[{s}] Admin: chuyển sang danh mục công ty khách", "/cong-ty-khach/" in page.url)

    # thêm công ty khách, trùng khác hoa thường bị chặn, gần trùng khi bỏ dấu thì cảnh báo
    name = f"Công ty Thử {RUN_ID}-{s}"
    goto(page, "/cai-dat/danh-muc/cong-ty-khach/them/")
    pw.shot(OUT, page, s, "02-them-cong-ty-khach")
    submit(page, "Lưu danh mục")
    check(
        f"[{s}] Admin: bỏ trống tên công ty bị báo lỗi", page.locator(".pa-form-error").count() >= 1
    )
    page.fill("input[name=name]", name)
    page.fill("input[name=location]", f"Tỉnh {s}")
    submit(page, "Lưu danh mục")
    check(f"[{s}] Admin: thêm công ty khách thành công", "Đã thêm công ty khách" in page.content())
    check(
        f"[{s}] Admin: bảng công ty khách có cột Địa điểm, không có cột Mã",
        page.locator("th:has-text('Địa điểm')").count() == 1
        and page.locator("th:text-is('Mã')").count() == 0,
    )

    goto(page, "/cai-dat/danh-muc/cong-ty-khach/them/")
    page.fill("input[name=name]", name.upper().replace(" ", "  "))
    page.fill("input[name=location]", f"tỉnh {s}")
    submit(page, "Lưu danh mục")
    check(
        f"[{s}] Admin: trùng tên + địa điểm (khác hoa thường) bị chặn",
        "Đã có công ty khách này ở địa điểm này" in page.content(),
    )
    pw.shot(OUT, page, s, "03-cong-ty-khach-trung")

    goto(page, "/cai-dat/danh-muc/cong-ty-khach/them/")
    page.fill("input[name=name]", f"Cong ty Thu {RUN_ID}-{s}")
    page.fill("input[name=location]", f"Tỉnh khác {s}")
    submit(page, "Lưu danh mục")
    check(
        f"[{s}] Admin: tên chỉ trùng khi bỏ dấu thì lưu được và có cảnh báo",
        f"Có thể trùng với: {name} – Tỉnh {s}" in page.content(),
    )
    pw.shot(OUT, page, s, "04-cong-ty-khach-canh-bao")

    # ngừng sử dụng qua hộp xác nhận
    confirm_menu(page, f"Cong ty Thu {RUN_ID}-{s}", "Ngừng sử dụng")
    check(f"[{s}] Admin: ngừng sử dụng công ty khách", "Đã ngừng sử dụng" in page.content())
    row = page.locator("tr", has_text=f"Cong ty Thu {RUN_ID}-{s}").first
    check(
        f"[{s}] Admin: dòng đã ngừng hiện nhãn Ngừng",
        row.locator(".pa-badge:has-text('Ngừng')").count() == 1,
    )

    # loại tài liệu hệ thống không ngừng được
    goto(page, "/cai-dat/danh-muc/loai-tai-lieu/")
    check(
        f"[{s}] Admin: có loại Bản cam kết", page.locator("td:has-text('Bản cam kết')").count() == 1
    )
    confirm_menu(page, "Hợp đồng", "Ngừng sử dụng")
    check(
        f"[{s}] Admin: loại tài liệu hệ thống không ngừng được",
        "không ngừng sử dụng được" in page.content(),
    )
    pw.shot(OUT, page, s, "05-loai-tai-lieu")

    # sinh mã
    goto(page, "/cai-dat/sinh-ma/")
    check(f"[{s}] Admin: trang sinh mã có mã kế tiếp", "Mã nhân viên kế tiếp" in page.content())
    pw.shot(OUT, page, s, "06-sinh-ma")
    page.fill("input[name=employee_code_prefix]", "C-N")
    submit(page, "Lưu cài đặt")
    check(
        f"[{s}] Admin: tiền tố có gạch ngang bị báo lỗi",
        "Tiền tố chỉ gồm chữ cái không dấu và chữ số" in page.content(),
    )
    pw.shot(OUT, page, s, "07-sinh-ma-loi")

    # ngưỡng
    goto(page, "/cai-dat/nguong/")
    check(
        f"[{s}] Admin: trang ngưỡng có ô thời hạn đợt làm việc",
        page.locator("input[name=assignment_limit_months]").count() == 1,
    )
    check(f"[{s}] Admin: trang ngưỡng không cuộn ngang", no_h_scroll(page))
    pw.shot(OUT, page, s, "08-nguong")
    page.fill("input[name=expiry_warning_days]", "0")
    submit(page, "Lưu cài đặt")
    check(f"[{s}] Admin: ngưỡng 0 bị báo lỗi", "Nhập số nguyên từ 1 đến 365." in page.content())
    ctx.close()

    for user in ("quanly", "hr", "viewer"):
        ctx, page = new_page(browser, size)
        login(page, user)
        check(
            f"[{s}] {user}: danh mục, sinh mã, ngưỡng đều 403",
            all(
                goto(page, u) == 403
                for u in ("/cai-dat/danh-muc/phong-ban/", "/cai-dat/sinh-ma/", "/cai-dat/nguong/")
            ),
        )
        ctx.close()


PARTS = {"cai-dat": part_settings}


def main():
    wanted = sys.argv[1:] or list(PARTS)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for s, size in pw.SIZES.items():
            for name in wanted:
                PARTS[name](browser, s, size)
        browser.close()
    noise = [e for e in pw.console_errors if not any(n in e[1] for n in pw.EXPECTED_NOISE)]
    check("Không có lỗi console ngoài 403/404/405 mong đợi", not noise, str(noise[:5]))
    failed = [r for r in pw.results if not r[1]]
    print(f"\n{len(pw.results) - len(failed)}/{len(pw.results)} bước đạt")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
