"""Kiểm thử giao diện Phase 7 bằng Playwright: Dashboard, Báo cáo (9 loại, in), Nhật ký, Chờ hủy,
Biên bản hủy, Nhập Excel, danh sách có nút xuất, /ui-kit/ (biểu đồ nhiều chuỗi, cột ngang, bảng
có ô chọn).
Chụp 1366x768 và 390x844 vào docs/screenshots/phase-7/, mỗi trang kiểm tra: mã trạng thái theo vai
trò, không cuộn ngang, đọc lỗi console; thử form với dữ liệu sai.
    py -3.12 scripts/kiem_thu_giao_dien_phase7.py
Cần web ở http://localhost:8000, 4 tài khoản admin, quanly, hr, viewer dùng chung mật khẩu trong
PA_TEST_PASSWORD và đã chạy seed_demo.
"""

import sys
import tempfile
from pathlib import Path

import pw_phase5 as pw
from playwright.sync_api import sync_playwright
from pw_phase5 import check, goto, login, new_page, no_h_scroll

OUT = pw.ROOT / "docs" / "screenshots" / "phase-7"
REPORTS = [
    "phong-ban",
    "gioi-tinh",
    "nhom-tuoi",
    "trinh-do",
    "chuc-danh",
    "hoan-thien",
    "ho-so-moi",
    "vao-lam-nghi-viec",
    "cong-ty-khach",
]
TMP = Path(tempfile.mkdtemp())


def visit(page, size_name, role, path, expected, shot=None):
    status = goto(page, path)
    check(f"{role} {size_name} {path} → {expected}", status == expected, str(status))
    if status == 200:
        check(f"{role} {size_name} {path}: không cuộn ngang", no_h_scroll(page))
        if shot:
            pw.shot(OUT, page, size_name, shot)
    return status


def audit_detail_url(page):
    goto(page, "/nhat-ky/?hanh_dong=IMPORT")
    link = page.locator("a[aria-label='Xem chi tiết']").first
    return link.get_attribute("href") if link.count() else None


def part_admin(browser, size_name, size):
    ctx, page = new_page(browser, size)
    login(page, "admin")
    visit(page, size_name, "admin", "/", 200, "kt-dashboard")
    check(
        "admin: Dashboard có 9 thẻ và 6 biểu đồ",
        page.locator("a.pa-stat").count() == 9 and page.locator("canvas").count() == 6,
    )
    for code in REPORTS:
        visit(page, size_name, "admin", f"/bao-cao/?loai={code}", 200, f"kt-bao-cao-{code}")
        check(
            f"admin: báo cáo {code} có biểu đồ hoặc thông báo không có số liệu",
            page.locator("canvas").count() == 1 or "Không có số liệu" in page.content(),
        )
    visit(page, size_name, "admin", "/bao-cao/in/?loai=nhom-tuoi", 200, "kt-bao-cao-in")
    # Form báo cáo sai: ngày đảo ngược
    goto(page, "/bao-cao/?loai=ho-so-moi&tu_ngay=01/12/2026&den_ngay=01/01/2026")
    check(
        "báo cáo: khoảng ngày sai hiện lỗi tiếng Việt, trang không sập",
        "Đến ngày phải sau hoặc bằng từ ngày." in page.content(),
    )
    pw.shot(OUT, page, size_name, "kt-bao-cao-loi-ngay")
    visit(page, size_name, "admin", "/nhat-ky/", 200, "kt-nhat-ky")
    goto(page, "/nhat-ky/?tu_ngay=2026-01-01")
    check("nhật ký: ngày sai hiện lỗi", "Nhập ngày đúng định dạng dd/mm/yyyy." in page.content())
    detail = audit_detail_url(page)
    if detail:
        visit(page, size_name, "admin", detail, 200, "kt-nhat-ky-chi-tiet")
    visit(page, size_name, "admin", "/cai-dat/cho-huy/", 200, "kt-cho-huy")
    visit(page, size_name, "admin", "/cai-dat/bien-ban-huy/", 200, "kt-bien-ban-huy")
    visit(page, size_name, "admin", "/ho-so/nhap-excel/", 200, "kt-nhap-excel")
    # Form nhập sai: không chọn tệp, tệp không phải Excel
    page.click("button:has-text('Nhập hồ sơ')")
    page.wait_for_load_state("networkidle")
    check("nhập Excel: không chọn tệp hiện lỗi", "Chọn tệp Excel để nhập." in page.content())
    bad = TMP / "khong-phai-excel.xlsx"
    bad.write_bytes(b"day khong phai file excel")
    page.set_input_files("input[type=file]", str(bad))
    page.click("button:has-text('Nhập hồ sơ')")
    page.wait_for_load_state("networkidle")
    check(
        "nhập Excel: tệp giả .xlsx bị từ chối bằng tiếng Việt",
        "Tệp phải là file Excel .xlsx." in page.content(),
    )
    pw.shot(OUT, page, size_name, "kt-nhap-excel-loi-tep")
    visit(page, size_name, "admin", "/ho-so/", 200, "kt-ho-so-nut-xuat")
    check(
        "admin: danh sách có Xuất Excel và Xuất kèm số CCCD",
        page.locator("text=Xuất Excel").count() >= 1
        and page.locator("text=Xuất kèm số CCCD").count() >= 1,
    )
    visit(
        page,
        size_name,
        "admin",
        "/ho-so/?trang_thai_lam_viec=PROBATION%2CACTIVE&tao_tu=01%2F01%2F2020&cccd_sap_het_han=1",
        200,
        "kt-ho-so-loc-moi",
    )
    check(
        "admin: ô lọc riêng của Dashboard hiện khi có giá trị",
        page.locator("input[name=tao_tu]").count() == 1
        and page.locator("select[name=cccd_sap_het_han]").count() == 1,
    )
    visit(page, size_name, "admin", "/ui-kit/", 200, "kt-ui-kit")
    check(
        "ui-kit: có biểu đồ nhiều chuỗi, cột ngang và bảng ô chọn",
        page.locator("canvas[data-pa-chart=chart-group]").count() == 1
        and page.locator("canvas[data-pa-chart=chart-horizontal]").count() == 1
        and page.locator("input[form=form-demo-chon]").count() >= 3,
    )
    ctx.close()


def part_other_roles(browser, size_name, size):
    matrix = {
        "quanly": {
            "/": 200,
            "/bao-cao/": 200,
            "/nhat-ky/": 200,
            "/cai-dat/cho-huy/": 403,
            "/ho-so/nhap-excel/": 200,
            "/bao-cao/in/": 200,
        },
        "hr": {
            "/": 200,
            "/bao-cao/": 200,
            "/nhat-ky/": 403,
            "/cai-dat/bien-ban-huy/": 403,
            "/ho-so/nhap-excel/": 200,
            "/bao-cao/xuat-excel/": 200,
        },
        "viewer": {
            "/": 200,
            "/bao-cao/": 200,
            "/nhat-ky/": 403,
            "/ho-so/nhap-excel/": 403,
            "/bao-cao/in/": 403,
            "/bao-cao/xuat-excel/": 403,
            "/ho-so/xuat-excel/": 403,
        },
    }
    for role, pages in matrix.items():
        ctx, page = new_page(browser, size)
        login(page, role)
        for path, expected in pages.items():
            if path.endswith("xuat-excel/") and expected == 200:
                continue  # trả tệp tải xuống, đã kiểm ở nghiem_thu_phase7
            shot = f"kt-{role}-dashboard" if path == "/" else None
            visit(page, size_name, role, path, expected, shot)
        if role == "viewer":
            goto(page, "/bao-cao/")
            pw.shot(OUT, page, size_name, "kt-viewer-bao-cao")
            check(
                "viewer: báo cáo không có nút In/Xuất Excel",
                page.locator("text=Xuất Excel").count() == 0
                and page.locator("a:text-is('In')").count() == 0,
            )
            goto(page, "/ho-so/")
            check(
                "viewer: danh sách không có nút xuất", page.locator("text=Xuất Excel").count() == 0
            )
        if role == "hr":
            goto(page, "/ho-so/")
            check(
                "hr: có Xuất Excel nhưng không có Xuất kèm số CCCD",
                page.locator("text=Xuất Excel").count() >= 1
                and page.locator("text=Xuất kèm số CCCD").count() == 0,
            )
        ctx.close()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for size_name, size in pw.SIZES.items():
            part_admin(browser, size_name, size)
            part_other_roles(browser, size_name, size)
        browser.close()
    return pw.finish()


if __name__ == "__main__":
    sys.exit(main())
