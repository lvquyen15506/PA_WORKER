"""Nghiệm thu Phase 6 bằng Playwright trên bản cài sạch: kịch bản 8, 9, 10 (yeu-cau.md mục X) và
kịch bản mới v1.1 (công ty khách, đợt làm việc, lương, cảnh báo 12 tháng, lọc theo công ty).
    py -3.12 scripts/nghiem_thu_phase6.py
Cần web ở http://localhost:8000, 4 tài khoản admin, quanly, hr, viewer dùng chung mật khẩu trong
PA_TEST_PASSWORD và đã chạy seed_demo. Đối chiếu AuditLog, AuditPersonalValue và SQL thô bằng
`manage.py shell`. Ảnh chụp vào docs/screenshots/phase-6/nghiem-thu/.
"""

import datetime
import re
import sys

import pw_phase5 as pw
from playwright.sync_api import sync_playwright
from pw_phase5 import check, db, goto, login, new_page, no_h_scroll

OUT = pw.ROOT / "docs" / "screenshots" / "phase-6" / "nghiem-thu"
SIZE = pw.SIZES["1366x768"]
FMT = "%d/%m/%Y"
TODAY = datetime.date.today()
RUN = datetime.datetime.now().strftime("%H%M%S")


def days(n):
    return (TODAY + datetime.timedelta(days=n)).strftime(FMT)


def submit(page, label):
    page.click(f"button:has-text('{label}')")
    page.wait_for_load_state("networkidle")


def shot(page, name):
    pw.shot(OUT, page, "1366x768", name)


def total(page):
    match = re.search(r"Hiển thị \d+–\d+ / (\d+)", page.content())
    return int(match.group(1)) if match else 0


def candidate():
    """Hồ sơ Đã xác minh chưa có thông tin làm việc, kèm lần ứng tuyển Đạt; trả (pk, mã hồ sơ)."""
    out = db(
        "from apps.workers.models import Worker;"
        "from apps.recruitment.models import Application;"
        "from apps.core.models import Position, ApplicationSource;"
        "import datetime;"
        "w=Worker.objects.filter(verification_status='VERIFIED',employment__isnull=True)"
        ".order_by('-pk').first();"
        "Application.objects.create(worker=w,position=Position.objects.first(),"
        "source=ApplicationSource.objects.first(),applied_date=datetime.date.today(),"
        "status='PASSED',result_date=datetime.date.today(),created_by=w.created_by);"
        "print(w.pk, w.worker_code)"
    )
    pk, code = out.split()
    return int(pk), code


def scenario_8(browser):
    pk, code = candidate()
    next_before = int(
        db(
            "from apps.core.codes import preview_code;"
            "print(preview_code('EMPLOYEE').split('-')[-1])"
        )
    )
    ctx, page = new_page(browser, SIZE)
    login(page, "hr")
    goto(page, f"/ho-so/{pk}/?tab=tuyen-dung")
    page.locator("tr", has_text="Đạt").first.locator(".dropdown-toggle").click()
    page.locator(".dropdown-menu.show a", has_text="Tiếp nhận vào làm").first.click()
    page.wait_for_load_state("networkidle")
    page.fill("input[name=received_date]", days(-3))
    page.fill("input[name=start_date]", days(0))
    shot(page, "kb8-1-form-tiep-nhan")
    submit(page, "Tiếp nhận vào làm")
    match = re.search(r"Mã nhân viên (CN-\d{5})", page.content())
    check("KB8: Đạt + Đã xác minh → Tiếp nhận sinh mã nhân viên đúng quy tắc CN-nnnnn", bool(match))
    code_nv = match.group(1) if match else ""
    check(
        "KB8: mã nhân viên bằng đúng mã kế tiếp theo cấu hình",
        bool(match) and int(code_nv.split("-")[1]) == next_before,
    )
    check(
        "KB8: trạng thái làm việc Chờ nhận việc",
        page.locator(".pa-badge:has-text('Chờ nhận việc')").count() >= 1,
    )
    goto(page, "/ho-so/?trang_thai_lam_viec=AWAITING")
    check("KB8: xuất hiện ở danh sách Chờ nhận việc", code_nv in page.content())
    shot(page, "kb8-2-danh-sach-cho-nhan-viec")
    history = db(
        "from apps.employment.models import EmploymentHistory as H;"
        f"print(H.objects.filter(worker_id={pk},change_type='ONBOARD').count())"
    )
    check("KB8: có đúng một dòng lịch sử Tiếp nhận vào làm", history == "1")
    log_count = db(
        "from apps.audit.models import AuditLog as A;"
        f"print(A.objects.filter(worker_id={pk},action__in=['CREATE','UPDATE']).count())"
    )
    check("KB8: thao tác ghi nhật ký (cấp mã và tạo thông tin làm việc)", int(log_count) >= 2)
    ctx.close()
    return pk, code_nv


def scenario_9(browser, pk):
    ctx, page = new_page(browser, SIZE)
    login(page, "hr")
    goto(page, f"/ho-so/{pk}/lam-viec/thay-doi/")
    sections = page.locator("select[name=section] option").all_inner_texts()
    target = next(s for s in sections if s not in ("Chưa có bộ phận",))
    page.select_option("select[name=section]", label=target)
    page.fill("input[name=effective_date]", days(0))
    page.fill("input[name=decision_no]", f"QĐ-NT-{RUN}")
    page.fill("textarea[name=reason]", "Điều chuyển theo nhu cầu sản xuất")
    submit(page, "Ghi nhận thay đổi")
    check("KB9: điều chuyển bộ phận thành công", "Đã ghi nhận thay đổi." in page.content())
    short = target.split(" (")[0]
    check(
        "KB9: thông tin hiện tại đổi sang bộ phận mới",
        page.locator(".pa-view-value", has_text=short).count() >= 1,
    )
    check(
        "KB9: lịch sử giữ dòng Tiếp nhận cũ và thêm dòng Điều chuyển mới",
        "Tiếp nhận vào làm" in page.content()
        and "Điều chuyển" in page.content()
        and f"QĐ-NT-{RUN}" in page.content(),
    )
    shot(page, "kb9-lich-su-dieu-chuyen")
    n = db(
        "from apps.employment.models import EmploymentHistory as H;"
        f"print(H.objects.filter(worker_id={pk}).count())"
    )
    check("KB9: lịch sử có đúng 2 dòng (không ghi đè)", n == "2")
    ctx.close()


def scenario_10(browser, pk, code_nv):
    ctx, page = new_page(browser, SIZE)
    login(page, "hr")
    goto(page, f"/ho-so/{pk}/hop-dong/them/")
    page.fill("input[name=contract_no]", f"HD-NT-{RUN}")
    page.fill("input[name=signed_date]", days(-340))
    page.fill("input[name=effective_date]", days(-345))
    page.fill("input[name=expiry_date]", days(20))
    submit(page, "Lưu hợp đồng")
    check("KB10: thêm hợp đồng hết hạn sau 20 ngày", "Đã thêm hợp đồng." in page.content())
    check(
        "KB10: tab hiện nhãn Sắp hết hạn",
        page.locator(".pa-badge:has-text('Sắp hết hạn')").count() == 1,
    )
    goto(page, "/ho-so/?hop_dong_sap_het_han=1")
    check(
        "KB10: danh sách Hợp đồng sắp hết hạn (liên kết của thẻ) có hồ sơ",
        code_nv in page.content(),
    )
    shot(page, "kb10-hop-dong-sap-het-han")
    ctx.close()


def scenario_v11(browser):
    pk = int(
        db(
            "from apps.workers.models import Worker;"
            "w=Worker.objects.filter(verification_status='VERIFIED',employment__work_status='ACTIVE',"
            "work_assignments__isnull=True).order_by('-pk').first();print(w.pk)"
        )
    )
    code_nv = db(
        f"from apps.workers.models import Worker;print(Worker.objects.get(pk={pk}).employee_code)"
    )
    ten = f"Công ty Nghiệm Thu {RUN}"
    # 1. Admin tạo công ty khách ở hai địa điểm (hai dòng cùng tên)
    ctx, page = new_page(browser, SIZE)
    login(page, "admin")
    for location in ("Bình Dương", "Đồng Nai"):
        goto(page, "/cai-dat/danh-muc/cong-ty-khach/them/")
        page.fill("input[name=name]", ten)
        page.fill("input[name=location]", location)
        submit(page, "Lưu danh mục")
        check(
            f"v1.1: Admin tạo công ty khách tại {location}",
            "Đã thêm công ty khách" in page.content(),
        )
    goto(page, "/cai-dat/danh-muc/cong-ty-khach/them/")
    page.fill("input[name=name]", ten.upper())
    page.fill("input[name=location]", "bình dương")
    submit(page, "Lưu danh mục")
    check(
        "v1.1: thêm trùng tên + địa điểm (khác hoa thường) bị chặn",
        "Đã có công ty khách này ở địa điểm này" in page.content(),
    )
    shot(page, "v11-1-danh-muc-cong-ty-khach")
    ctx.close()

    # 2. Quản lý tạo hai đợt liền nhau cùng tên công ty khác địa điểm, bắt đầu 330 ngày trước
    ctx, page = new_page(browser, SIZE)
    login(page, "quanly")
    goto(page, f"/ho-so/{pk}/dot-lam-viec/them/")
    page.select_option("select[name=client_company]", label=f"{ten} – Bình Dương")
    page.select_option("select[name=position]", index=1)
    page.fill(
        "input[name=start_date]", days(-345)
    )  # đủ 12 tháng sau ~20 ngày: trong ngưỡng 30 ngày
    page.fill("input[name=end_date]", days(-151))
    submit(page, "Lưu đợt làm việc")
    check("v1.1: tạo đợt 1", "Đã thêm đợt làm việc." in page.content())
    goto(page, f"/ho-so/{pk}/dot-lam-viec/them/")
    page.select_option("select[name=client_company]", label=f"{ten} – Đồng Nai")
    page.select_option("select[name=position]", index=1)
    page.fill("input[name=start_date]", days(-150))  # liền nhau: ngay ngày sau
    submit(page, "Lưu đợt làm việc")
    check(
        "v1.1: tạo đợt 2 liền nhau (cùng tên, khác địa điểm)",
        "Đã thêm đợt làm việc." in page.content(),
    )
    goto(page, f"/ho-so/{pk}/dot-lam-viec/them/")
    page.select_option("select[name=client_company]", label=f"{ten} – Bình Dương")
    page.select_option("select[name=position]", index=1)
    page.fill("input[name=start_date]", days(-100))
    submit(page, "Lưu đợt làm việc")
    check(
        "v1.1: thêm đợt thứ ba khi đang có đợt mở bị chặn",
        "Nhập ngày kết thúc của đợt đó." in page.content(),
    )

    # 3. Thêm 2 lần lương cho đợt 2
    assignment = db(
        "from apps.employment.models import WorkAssignment as W;"
        f"print(W.objects.filter(worker_id={pk}).order_by('-start_date').first().pk)"
    )
    url = f"/dot-lam-viec/{assignment}/luong/them/"
    for amount, day, reason in (
        ("8700000", -150, "Thiết lập ban đầu"),
        ("9400000", -30, "Tăng lương theo bậc"),
    ):
        goto(page, url)
        page.fill("input[name=monthly_salary]", amount)
        page.fill("input[name=client_unit_price]", "12100000")
        page.fill("input[name=effective_date]", days(day))
        page.fill("textarea[name=reason]", reason)
        submit(page, "Ghi nhận thay đổi lương")
        check(f"v1.1: Quản lý thêm lương {amount}", "Đã ghi nhận thay đổi lương." in page.content())
    goto(page, f"/ho-so/{pk}/?tab=lam-viec")
    check(
        "v1.1: tab hiện 2 dòng lịch sử lương, lương hiện tại 9.400.000",
        page.locator("td:has-text('8.700.000 đ')").count() == 1
        and page.locator("td:has-text('9.400.000 đ')").count() == 1,
    )
    check(
        "v1.1: cảnh báo sắp đủ 12 tháng tính từ đầu chuỗi (đợt 1), không phải đợt 2",
        "đủ thời hạn vào" in page.content() and days(-345) in page.content(),
    )
    check("v1.1: tab không cuộn ngang", no_h_scroll(page))
    shot(page, "v11-2-tab-lam-viec-dot-va-luong")
    ctx.close()

    # 4. HR và Viewer: xem được, không thêm được lương
    for user, can_add_assignment in (("hr", True), ("viewer", False)):
        ctx, page = new_page(browser, SIZE)
        login(page, user)
        goto(page, f"/ho-so/{pk}/?tab=lam-viec")
        check(
            f"v1.1: {user} thấy lương và đơn giá",
            "9.400.000 đ" in page.content() and "12.100.000 đ" in page.content(),
        )
        check(
            f"v1.1: {user} không có nút ghi nhận lương",
            page.locator("a.btn:has-text('Ghi nhận thay đổi lương')").count() == 0,
        )
        check(f"v1.1: {user} gọi thẳng URL thêm lương bị 403", goto(page, url) == 403)
        check(
            f"v1.1: {user} {'thêm được' if can_add_assignment else 'không thêm được'} đợt làm việc",
            (goto(page, f"/ho-so/{pk}/dot-lam-viec/them/") == 200) == can_add_assignment,
        )
        ctx.close()

    # 5. Lọc danh sách và đối chiếu số liệu với CSDL
    ctx, page = new_page(browser, SIZE)
    login(page, "hr")
    cid = db(
        "from apps.core.models import ClientCompany as C;"
        f"print(C.objects.get(name='{ten}',location='Đồng Nai').pk)"
    )
    goto(page, f"/ho-so/?cong_ty_khach={cid}")
    expected = int(
        db(
            "from apps.employment.models import WorkAssignment as W;import datetime;"
            "t=datetime.date.today();"
            f"print(W.objects.filter(client_company_id={cid},start_date__lte=t).exclude("
            "end_date__lt=t).values('worker').distinct().count())"
        )
    )
    check(
        f"v1.1: lọc theo công ty khách đúng số người ({expected})",
        total(page) == expected == 1 and code_nv in page.content(),
    )
    check(
        "v1.1: cột Công ty khách hiện tên và địa điểm",
        f"{ten} – Đồng Nai" in page.content(),
    )
    shot(page, "v11-3-loc-cong-ty-khach")
    goto(page, "/ho-so/?dot_sap_du_han=1")
    due_in_db = int(
        db("from apps.workers import indicators;print(len(indicators.assignment_due_info()))")
    )
    check(
        f"v1.1: lọc đợt sắp đủ 12 tháng đúng số người ({due_in_db}) và có hồ sơ vừa tạo",
        total(page) == due_in_db and code_nv in page.content(),
    )
    shot(page, "v11-4-dot-sap-du-han")
    ctx.close()

    # 6. Đối chiếu nhật ký và CSDL
    raw = db(
        "from django.db import connection;c=connection.cursor();"
        "c.execute('select monthly_salary_enc, client_unit_price_enc "
        "from employment_salaryhistory');"
        "rows=c.fetchall();"
        "print(all(('8700000' not in a and '9400000' not in a and '12100000' not in (b or '')) "
        "for a,b in rows))"
    )
    check("v1.1: SQL thô không thấy số lương rõ (đã mã hóa)", raw == "True")
    leaked = db(
        "from apps.audit.models import AuditLog as A;"
        "print(any(('8700000' in str(a.changes) or '9400000' in str(a.changes)) "
        "for a in A.objects.filter(object_type='employment.SalaryHistory')))"
    )
    check("v1.1: AuditLog.changes không chứa số lương", leaked == "False")
    stored = db(
        "from apps.audit.models import AuditPersonalValue as P;"
        f"print(P.objects.filter(worker_id={pk},field_name__contains='monthly_salary').count())"
    )
    check("v1.1: giá trị lương nằm ở AuditPersonalValue (2 dòng)", stored == "2")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pk, code_nv = scenario_8(browser)
        scenario_9(browser, pk)
        scenario_10(browser, pk, code_nv)
        scenario_v11(browser)
        browser.close()
    noise = [e for e in pw.console_errors if not any(n in e[1] for n in pw.EXPECTED_NOISE)]
    check("Không có lỗi console ngoài 403/404/405 mong đợi", not noise, str(noise[:5]))
    failed = [r for r in pw.results if not r[1]]
    print(f"\n{len(pw.results) - len(failed)}/{len(pw.results)} bước đạt")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
