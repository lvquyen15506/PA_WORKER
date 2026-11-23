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


# ===== Tuyển dụng ================================================================================
UI_WORKER_CODE = "HS-UI-P6"


def ensure_ui_worker():
    """Hồ sơ Nháp dành riêng cho kiểm thử giao diện (tên hư cấu); trả pk."""
    return int(
        db(
            "from apps.workers.models import Worker;from apps.accounts.models import User;"
            f"w=Worker.objects.filter(worker_code='{UI_WORKER_CODE}').first() or "
            f"Worker.objects.create(worker_code='{UI_WORKER_CODE}',"
            "full_name='Nguyễn Văn Thử Giao Diện',phone='0900000666',"
            "created_by=User.objects.get(username='admin'));print(w.pk)"
        )
    )


def part_recruitment(browser, s, size):
    pk = ensure_ui_worker()
    tab = f"/ho-so/{pk}/?tab=tuyen-dung"
    ctx, page = new_page(browser, size)
    login(page, "hr")
    goto(page, tab)
    check(
        f"[{s}] HR: tab Tuyển dụng có 4 nút thêm",
        all(
            page.locator(f"a.btn:has-text('{t}')").count() == 1
            for t in ("Thêm lần ứng tuyển", "Thêm học vấn", "Thêm chứng chỉ", "Thêm kinh nghiệm")
        ),
    )
    check(f"[{s}] HR: tab Tuyển dụng không cuộn ngang", no_h_scroll(page))
    pw.shot(OUT, page, s, "10-tab-tuyen-dung")

    # thêm lần ứng tuyển: sai rồi đúng
    page.click("a.btn:has-text('Thêm lần ứng tuyển')")
    page.wait_for_load_state("networkidle")
    page.select_option("select[name=position]", index=1)
    page.select_option("select[name=source]", index=1)
    page.fill("input[name=applied_date]", "01/03/2026")
    page.select_option("select[name=status]", "FAILED")
    pw.shot(OUT, page, s, "11-them-ung-tuyen")
    submit(page, "Lưu lần ứng tuyển")
    check(f"[{s}] HR: Không đạt thiếu lý do bị báo lỗi", "Nhập lý do không đạt." in page.content())
    pw.shot(OUT, page, s, "12-ung-tuyen-loi")
    page.fill("textarea[name=reject_reason]", "Không đủ sức khỏe theo khám tuyển")
    page.fill("input[name=expected_salary]", "8500000")
    submit(page, "Lưu lần ứng tuyển")
    check(f"[{s}] HR: thêm lần ứng tuyển thành công", "Đã thêm lần ứng tuyển." in page.content())
    check(
        f"[{s}] HR: bảng hiện mức lương 8.500.000 đ và nhãn Không đạt",
        "8.500.000 đ" in page.content()
        and page.locator(".pa-badge:has-text('Không đạt')").count() >= 1,
    )

    # học vấn: thêm, sửa sai, xóa qua hộp xác nhận
    goto(page, f"/ho-so/{pk}/hoc-van/them/")
    page.select_option("select[name=education_level]", index=3)
    page.fill("input[name=school_name]", f"Trường Thử {RUN_ID}")
    page.fill("input[name=start_year]", "2020")
    page.fill("input[name=end_year]", "2015")
    submit(page, "Lưu học vấn")
    check(
        f"[{s}] HR: năm kết thúc trước năm bắt đầu bị báo lỗi",
        "Năm kết thúc phải sau hoặc bằng năm bắt đầu." in page.content(),
    )
    page.fill("input[name=end_year]", "2023")
    submit(page, "Lưu học vấn")
    check(f"[{s}] HR: thêm học vấn thành công", f"Trường Thử {RUN_ID}" in page.content())
    pw.shot(OUT, page, s, "13-tab-tuyen-dung-day-du")
    confirm_menu(page, f"Trường Thử {RUN_ID}", "Xóa dòng")
    check(
        f"[{s}] HR: xóa dòng học vấn qua hộp xác nhận",
        "Đã xóa dòng học vấn." in page.content()
        and f"Trường Thử {RUN_ID}"
        not in page.locator("table").first.inner_text()
        + "".join(t.inner_text() for t in page.locator("table").all()),
    )
    ctx.close()

    # Viewer: thấy lương mong muốn (v1.1), không có nút, 403 khi gọi thẳng
    ctx, page = new_page(browser, size)
    login(page, "viewer")
    goto(page, tab)
    check(
        f"[{s}] Viewer: thấy mức lương mong muốn, không có nút thêm/sửa",
        "8.500.000 đ" in page.content()
        and page.locator("a.btn:has-text('Thêm')").count() == 0
        and "/sua/" not in page.content(),
    )
    check(
        f"[{s}] Viewer: gọi thẳng URL thêm bị 403",
        goto(page, f"/ho-so/{pk}/ung-tuyen/them/") == 403,
    )
    goto(page, "/tuyen-dung/")
    check(
        f"[{s}] Viewer: /tuyen-dung/ mở được, có cột Mức lương",
        "Mức lương mong muốn" in page.content(),
    )
    check(f"[{s}] Viewer: /tuyen-dung/ không cuộn ngang", no_h_scroll(page))
    pw.shot(OUT, page, s, "14-tuyen-dung-viewer")
    ctx.close()

    ctx, page = new_page(browser, size)
    login(page, "quanly")
    goto(page, "/tuyen-dung/?trang_thai=FAILED")
    check(f"[{s}] Quản lý: lọc Không đạt thấy hồ sơ thử", UI_WORKER_CODE in page.content())
    goto(page, "/tuyen-dung/?trang_thai=NEW,SCREENING,INTERVIEW")
    check(
        f"[{s}] Quản lý: lọc nhiều trạng thái không thấy hồ sơ Không đạt",
        UI_WORKER_CODE not in page.content(),
    )
    pw.shot(OUT, page, s, "15-tuyen-dung-loc")
    ctx.close()


# ===== Tiếp nhận, quá trình làm việc, hợp đồng =================================================
def pick_candidate():
    """Hồ sơ Đã xác minh chưa có thông tin làm việc, kèm một lần ứng tuyển Đạt; trả pk."""
    return int(
        db(
            "from apps.workers.models import Worker;"
            "from apps.recruitment.models import Application;"
            "from apps.core.models import Position, ApplicationSource;"
            "import datetime;"
            "w=Worker.objects.filter(verification_status='VERIFIED',employment__isnull=True)"
            ".order_by('-pk').first();"
            "Application.objects.create(worker=w,position=Position.objects.first(),"
            "source=ApplicationSource.objects.first(),applied_date=datetime.date.today(),"
            "status='PASSED',result_date=datetime.date.today(),created_by=w.created_by);"
            "print(w.pk)"
        )
    )


def part_employment(browser, s, size):
    import datetime
    import tempfile

    pk = pick_candidate()
    today = datetime.date.today()
    ctx, page = new_page(browser, size)
    login(page, "hr")
    goto(page, f"/ho-so/{pk}/?tab=tuyen-dung")
    page.locator("tr", has_text="Đạt").first.locator(".dropdown-toggle").click()
    pw.shot(OUT, page, s, "20-menu-tiep-nhan")
    page.locator(".dropdown-menu.show a", has_text="Tiếp nhận vào làm").first.click()
    page.wait_for_load_state("networkidle")
    check(f"[{s}] HR: mở form Tiếp nhận vào làm", "Tiếp nhận vào làm" in page.content())
    pw.shot(OUT, page, s, "21-form-tiep-nhan")
    page.fill("input[name=received_date]", "09/03/2026")
    page.fill("input[name=start_date]", "05/03/2026")
    page.fill("input[name=manager_code]", "ZZZ-999")
    submit(page, "Tiếp nhận vào làm")
    check(
        f"[{s}] HR: ngày bắt đầu trước ngày tiếp nhận và mã quản lý sai bị báo lỗi",
        "Không tìm thấy công nhân có mã nhân viên này." in page.content(),
    )
    page.fill("input[name=manager_code]", "")
    submit(page, "Tiếp nhận vào làm")
    check(
        f"[{s}] HR: ngày bắt đầu trước ngày tiếp nhận bị báo lỗi",
        "Ngày bắt đầu không được trước ngày tiếp nhận." in page.content(),
    )
    pw.shot(OUT, page, s, "22-tiep-nhan-loi")
    page.fill("input[name=start_date]", "10/03/2026")
    submit(page, "Tiếp nhận vào làm")
    check(f"[{s}] HR: tiếp nhận thành công, có mã nhân viên", "Mã nhân viên CN-" in page.content())
    check(
        f"[{s}] HR: trạng thái Chờ nhận việc",
        page.locator(".pa-badge:has-text('Chờ nhận việc')").count() >= 1,
    )
    check(f"[{s}] HR: tab Quá trình làm việc không cuộn ngang", no_h_scroll(page))
    pw.shot(OUT, page, s, "23-lam-viec-sau-tiep-nhan")
    check(
        f"[{s}] HR: không còn nút Tiếp nhận vào làm cho lần đã tiếp nhận",
        goto(page, f"/ho-so/{pk}/?tab=tuyen-dung") == 200
        and "Tiếp nhận vào làm" not in page.content(),
    )

    # Ghi nhận thay đổi: không đổi gì thì báo lỗi; đổi trạng thái thì thêm dòng lịch sử
    goto(page, f"/ho-so/{pk}/lam-viec/thay-doi/")
    page.fill("input[name=effective_date]", "01/04/2026")
    pw.shot(OUT, page, s, "24-form-thay-doi")
    submit(page, "Ghi nhận thay đổi")
    check(
        f"[{s}] HR: không đổi gì bị báo lỗi", "Không có thay đổi nào để ghi nhận." in page.content()
    )
    page.select_option("select[name=work_status]", "RESIGNED")
    submit(page, "Ghi nhận thay đổi")
    check(
        f"[{s}] HR: nghỉ việc thiếu ngày và lý do bị báo lỗi",
        "Nhập ngày nghỉ việc." in page.content() and "Chọn lý do nghỉ việc." in page.content(),
    )
    page.select_option("select[name=work_status]", "PROBATION")
    page.fill("input[name=decision_no]", "QĐ-UI-01")
    submit(page, "Ghi nhận thay đổi")
    check(f"[{s}] HR: đổi trạng thái thành công", "Đã ghi nhận thay đổi." in page.content())
    check(
        f"[{s}] HR: lịch sử giữ dòng Tiếp nhận và thêm dòng Đổi trạng thái",
        "Tiếp nhận vào làm" in page.content()
        and "Đổi trạng thái làm việc" in page.content()
        and "Chờ nhận việc → Thử việc" in page.content(),
    )

    # Hợp đồng: thiếu hạn, rồi có tệp và hết hạn sau 20 ngày → nhãn Sắp hết hạn
    pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    pdf.write(b"%PDF-1.4 hop dong gia de kiem thu giao dien")
    pdf.close()
    goto(page, f"/ho-so/{pk}/hop-dong/them/")
    page.fill("input[name=contract_no]", f"HD-UI-{RUN_ID}-{s}")
    page.fill("input[name=signed_date]", "01/03/2026")
    page.fill("input[name=effective_date]", "05/03/2026")
    submit(page, "Lưu hợp đồng")
    check(
        f"[{s}] HR: hợp đồng xác định thời hạn thiếu ngày hết hạn bị báo lỗi",
        "Nhập ngày hết hạn." in page.content(),
    )
    page.fill(
        "input[name=effective_date]", (today - datetime.timedelta(days=345)).strftime("%d/%m/%Y")
    )
    page.fill("input[name=expiry_date]", (today + datetime.timedelta(days=20)).strftime("%d/%m/%Y"))
    page.set_input_files("input[name=file]", pdf.name)
    pw.shot(OUT, page, s, "25-form-hop-dong")
    submit(page, "Lưu hợp đồng")
    check(f"[{s}] HR: thêm hợp đồng thành công", "Đã thêm hợp đồng." in page.content())
    check(
        f"[{s}] HR: hợp đồng sắp hết hạn có nhãn Sắp hết hạn và nút tải tệp",
        page.locator(".pa-badge:has-text('Sắp hết hạn')").count() == 1
        and page.locator("a[href*='/tai-xuong/']").count() == 1,
    )
    pw.shot(OUT, page, s, "26-lam-viec-day-du")
    goto(page, "/ho-so/?hop_dong_sap_het_han=1")
    check(
        f"[{s}] HR: lọc hợp đồng sắp hết hạn thấy hồ sơ vừa thêm",
        page.locator("td", has_text="CN-").count() >= 1,
    )
    ctx.close()

    ctx, page = new_page(browser, size)
    login(page, "viewer")
    goto(page, f"/ho-so/{pk}/?tab=lam-viec")
    check(
        f"[{s}] Viewer: thấy lịch sử và hợp đồng, không có nút thao tác",
        "Sắp hết hạn" in page.content()
        and page.locator("a.btn:has-text('Ghi nhận thay đổi')").count() == 0
        and "/sua/" not in page.content(),
    )
    check(
        f"[{s}] Viewer: gọi thẳng các URL ghi nhận bị 403",
        all(
            goto(page, u) == 403
            for u in (f"/ho-so/{pk}/lam-viec/thay-doi/", f"/ho-so/{pk}/hop-dong/them/")
        ),
    )
    ctx.close()


PARTS = {
    "cai-dat": part_settings,
    "tuyen-dung": part_recruitment,
    "lam-viec": part_employment,
}


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
