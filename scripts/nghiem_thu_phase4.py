"""Nghiệm thu kịch bản 2, 5, 6, 7, 14 (docs/yeu-cau.md mục X) bằng Playwright trên bản cài sạch.

Chạy: py -3.12 scripts/nghiem_thu_phase4.py
Cần web ở http://localhost:8000 có dữ liệu mẫu (seed_demo) và 4 tài khoản admin, quanly, hr, viewer
dùng chung mật khẩu trong PA_TEST_PASSWORD. Ảnh chụp vào docs/screenshots/phase-4/nghiem-thu/.
Đối chiếu nhật ký bằng `docker compose -f docker-compose.yml exec web python manage.py shell`
(chỉ in số đếm và mã trạng thái, không in dữ liệu cá nhân).
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("PA_BASE_URL", "http://localhost:8000")
PASSWORD = os.environ["PA_TEST_PASSWORD"]
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots" / "phase-4" / "nghiem-thu"
OUT.mkdir(parents=True, exist_ok=True)
PDF_BYTES = b"%PDF-1.4\n% tai lieu mau de nghiem thu\n%%EOF\n"
UNIQ = str(time.time_ns())

results, console_errors = [], []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("ĐẠT  " if ok else "LỖI  ") + name + (f" – {detail}" if detail and not ok else ""))


def new_page(browser, width=1366, height=768):
    ctx = browser.new_context(viewport={"width": width, "height": height}, locale="vi-VN")
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


def goto(page, path):
    response = page.goto(f"{BASE}{path}")
    page.wait_for_load_state("networkidle")
    return response.status if response else 0


def shot(page, name, modal=False):
    if modal:
        page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=not modal)


def db(code):
    """Chạy một đoạn Python trong container web; trả dòng cuối của kết quả."""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.yml",
            "exec",
            "-T",
            "web",
            "python",
            "manage.py",
            "shell",
            "-c",
            code,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""


def post_with_csrf(page, path, data=None):
    """POST từ phiên đang đăng nhập (như một form bị gọi thẳng), trả mã trạng thái."""
    token = next(c["value"] for c in page.context.cookies() if c["name"] == "csrftoken")
    response = page.request.post(
        f"{BASE}{path}", form=data or {}, headers={"X-CSRFToken": token, "Referer": BASE}
    )
    return response.status


def create_worker(page, name, phone, cccd, contact=True):
    """HR/QL nhập đủ trường qua form thêm hồ sơ; trả đường dẫn chi tiết."""
    goto(page, "/ho-so/them/nhap-tay/")
    page.fill("input[name=full_name]", name)
    page.fill("input[name=phone]", phone)
    page.fill("input[name=date_of_birth]", "05/03/1995")
    page.select_option("select[name=gender]", "MALE")
    page.fill("input[name=current_address]", "Số 1 đường giả, quận giả")
    page.select_option("select[name=id_doc_type]", "CCCD_2021")
    page.fill("input[name=id_number]", cccd)
    if contact:
        page.fill("input[name=contacts-0-full_name]", "Người Thân Giả")
        page.fill("input[name=contacts-0-relationship]", "Anh")
        page.fill("input[name=contacts-0-phone]", "0988777666")
    page.click("button:has-text('Lưu hồ sơ')")
    page.wait_for_load_state("networkidle")
    return page.url.replace(BASE, "").split("?")[0]


def record_consent(page, worker_path):
    goto(page, worker_path + "dong-y/")
    page.select_option("select[name=method]", "ELECTRONIC")
    page.click("button:has-text('Lưu ghi nhận')")
    page.wait_for_load_state("networkidle")


def upload_pdf(page, worker_path, type_label, file_path):
    goto(page, worker_path + "tai-lieu/them/")
    page.select_option("select[name=document_type]", label=type_label)
    page.set_input_files("input[name=file]", str(file_path))
    page.click("button:has-text('Tải tài liệu lên')")
    page.wait_for_load_state("networkidle")


def find_row(page, code):
    """Dòng (văn bản) của hồ sơ `code` trong hàng đợi Duyệt hồ sơ; hàng đợi xếp cũ nhất trước nên
    hồ sơ vừa gửi nằm ở trang sau. None nếu không thấy."""
    for number in range(1, 40):
        goto(page, f"/duyet-ho-so/?trang={number}")
        for row in page.locator(".pa-table tbody tr").all():
            text = row.inner_text()
            if code in text:
                return text
        if page.locator(".pa-pagination .page-item.disabled:has-text('Sau')").count():
            return None
    return None


def status_badge(page):
    return page.locator("p.pa-small .pa-badge").first.inner_text()


tmp = Path(tempfile.mkdtemp(prefix="pa_nt_"))
pdf = tmp / "mau.pdf"
pdf.write_bytes(PDF_BYTES)

with sync_playwright() as p:
    browser = p.chromium.launch()

    # ===== Chuẩn bị: HR nhập hồ sơ, tải tài liệu, ghi đồng ý, gửi duyệt =====
    ctx_hr, hr = new_page(browser)
    login(hr, "hr")
    path = create_worker(hr, "Nghiệm Thu Sáu Bảy", "09" + UNIQ[-8:], "999" + UNIQ[-9:])
    check(
        "[chuẩn bị] HR lưu hồ sơ Nháp",
        path.startswith("/ho-so/") and path.rstrip("/").split("/")[-1].isdigit(),
        path,
    )
    worker_id = path.strip("/").split("/")[-1]
    upload_pdf(hr, path, "CCCD mặt trước", pdf)
    record_consent(hr, path)
    goto(hr, path)
    code = hr.locator(".pa-breadcrumb li").last.inner_text().strip()

    # ===== Kịch bản 2: Viewer mở hồ sơ =====
    ctx_v, viewer = new_page(browser)
    login(viewer, "viewer")
    status = goto(viewer, path)
    text = viewer.locator(".pa-content").inner_text()
    check("[2] Viewer mở được hồ sơ", status == 200 and code in text)
    check("[2] Số CCCD bị che", "••••" in text and ("999" + UNIQ[-9:]) not in viewer.content())
    check(
        "[2] Không có trường nhạy cảm và nút Hiện số đầy đủ",
        all(t not in text for t in ("Số CMND cũ", "Nơi thường trú", "Quê quán", "Hiện số đầy đủ")),
    )
    shot(viewer, "kb2-viewer-chi-tiet")
    check("[2] Gọi thẳng đường dẫn sửa bị từ chối (403)", goto(viewer, path + "sua/") == 403)
    shot(viewer, "kb2-viewer-sua-403")
    goto(hr, path + "?tab=tai-lieu")
    doc_id = hr.locator("a[href$='/tai-xuong/']").first.get_attribute("href").split("/")[2]
    check(
        "[2] Gọi thẳng đường dẫn tải tệp bị từ chối (403)",
        goto(viewer, f"/tai-lieu/{doc_id}/tai-xuong/") == 403,
    )
    check(
        "[2] Gọi thẳng đường dẫn xem tệp bị từ chối (403)",
        goto(viewer, f"/tai-lieu/{doc_id}/xem/") == 403,
    )
    shot(viewer, "kb2-viewer-tai-tep-403")
    check(
        "[2] Viewer POST sửa/gửi duyệt bị 403", post_with_csrf(viewer, f"{path}gui-duyet/") == 403
    )
    ctx_v.close()

    # ===== Kịch bản 5: nhập CCCD đã có =====
    before = db("from apps.workers.models import Worker; print(Worker.objects.count())")
    goto(hr, "/ho-so/them/nhap-tay/")
    hr.fill("input[name=full_name]", "Trùng Số Căn Cước")
    hr.fill("input[name=phone]", "0911555666")
    hr.fill("input[name=id_number]", "999000000001")  # có trong dữ liệu mẫu seed_demo
    hr.press("input[name=id_number]", "Tab")
    hr.wait_for_selector("#duplicate-check .alert", timeout=5000)
    check("[5] Rời ô CCCD: báo trùng", "đã có hồ sơ" in hr.locator("#duplicate-check").inner_text())
    shot(hr, "kb5-bao-trung")
    hr.click("button:has-text('Lưu hồ sơ')")
    hr.wait_for_load_state("networkidle")
    check(
        "[5] Bấm Lưu: bị chặn, vẫn ở form",
        "/ho-so/them/nhap-tay/" in hr.url and "Mở hồ sơ cũ" in hr.content(),
    )
    shot(hr, "kb5-bi-chan-khi-luu")
    after = db("from apps.workers.models import Worker; print(Worker.objects.count())")
    check("[5] Không tạo hồ sơ mới", before == after, f"{before} -> {after}")
    hr.click("a:has-text('Mở hồ sơ cũ')")
    hr.wait_for_load_state("networkidle")
    check(
        "[5] Mở hồ sơ cũ thấy đúng hồ sơ đang giữ số đó",
        hr.url.rstrip("/").split("/")[-1].isdigit() and "Thông tin cơ bản" in hr.content(),
    )
    shot(hr, "kb5-ho-so-cu")

    # ===== Kịch bản 6: gửi duyệt -> trả lại -> bổ sung -> duyệt =====
    goto(hr, path)
    hr.click(".pa-page-header__actions button:has-text('Gửi duyệt')")
    hr.wait_for_load_state("networkidle")
    check("[6] HR gửi duyệt: Chờ duyệt", status_badge(hr) == "Chờ duyệt")
    shot(hr, "kb6-1-hr-gui-duyet")

    ctx_q, ql = new_page(browser)
    login(ql, "quanly")
    row = find_row(ql, code)
    check("[6] Hồ sơ có trong hàng đợi Duyệt hồ sơ", row is not None)
    check(
        "[6] Dòng không có ghi chú 'không duyệt được' (người duyệt là người khác)",
        row is not None and "không duyệt được" not in row,
    )
    shot(ql, "kb6-2-hang-doi")
    goto(ql, path)
    ql.click(".pa-page-header__actions button:has-text('Trả lại')")
    ql.wait_for_selector("#return-modal.show")
    ql.fill("#return-modal textarea", "Bổ sung ảnh CCCD mặt sau")
    shot(ql, "kb6-3-hop-tra-lai", modal=True)
    ql.click("#return-modal button[type=submit]")
    ql.wait_for_load_state("networkidle")
    check("[6] Quản lý trả lại: Cần bổ sung", status_badge(ql) == "Cần bổ sung")
    goto(hr, path)
    check("[6] HR thấy nội dung cần bổ sung", "Trả lại: Bổ sung ảnh CCCD mặt sau" in hr.content())
    shot(hr, "kb6-4-hr-thay-ly-do")
    upload_pdf(hr, path, "CCCD mặt sau", pdf)
    goto(hr, path)
    hr.click(".pa-page-header__actions button:has-text('Gửi duyệt')")
    hr.wait_for_load_state("networkidle")
    check("[6] HR bổ sung rồi gửi duyệt lại: Chờ duyệt", status_badge(hr) == "Chờ duyệt")
    goto(ql, path)
    ql.click(".pa-page-header__actions button:has-text('Duyệt hồ sơ')")
    ql.wait_for_load_state("networkidle")
    check("[6] Quản lý duyệt: Đã xác minh", status_badge(ql) == "Đã xác minh")
    shot(ql, "kb6-5-da-xac-minh")
    goto(ql, path + "?tab=lich-su")
    ql.wait_for_selector("section:has-text('Chi tiết thay đổi') .pa-table", timeout=5000)
    timeline = ql.locator(
        "section:has-text('Dòng thời gian trạng thái') .pa-table tbody tr"
    ).count()
    check("[6] Tab Lịch sử có đủ 5 dòng thời gian", timeline == 5, f"thực tế {timeline}")
    check("[6] Dòng thời gian có lý do trả lại", "Bổ sung ảnh CCCD mặt sau" in ql.content())
    shot(ql, "kb6-6-lich-su")
    sequence = db(
        "from apps.workers.models import StatusChange as S; "
        f"qs = S.objects.filter(worker_id={worker_id}).order_by('id'); "
        "print('>'.join(c.to_status for c in qs))"
    )
    check(
        "[6] StatusChange đúng từng bước",
        sequence == "DRAFT>PENDING>NEEDS_INFO>PENDING>VERIFIED",
        sequence,
    )
    audit = db(
        "from apps.audit.models import AuditLog as A; "
        f"qs = A.objects.filter(worker_id={worker_id}); "
        "print(','.join(sorted(set(qs.values_list('action', flat=True)))))"
    )
    check(
        "[6] Nhật ký có STATUS_CHANGE, UPLOAD_FILE, CREATE",
        all(a in audit for a in ("STATUS_CHANGE", "UPLOAD_FILE", "CREATE")),
        audit,
    )

    # ===== Kịch bản 7: không tự duyệt =====
    path7 = create_worker(
        hr, "Tự Duyệt Hồ Sơ Mình", "09" + UNIQ[-7:] + "7", "999" + UNIQ[-8:] + "7"
    )
    upload_pdf(hr, path7, "CCCD mặt trước", pdf)
    record_consent(hr, path7)
    goto(hr, path7)
    hr.click(".pa-page-header__actions button:has-text('Gửi duyệt')")
    hr.wait_for_load_state("networkidle")
    check("[7] HR gửi duyệt hồ sơ mình nhập", status_badge(hr) == "Chờ duyệt")
    check(
        "[7] HR không thấy nút Duyệt hồ sơ",
        hr.locator(".pa-page-header__actions:has-text('Duyệt hồ sơ')").count() == 0,
    )
    check("[7] HR gọi thẳng /duyet/ bị chặn (403)", post_with_csrf(hr, f"{path7}duyet/") == 403)
    check(
        "[7] HR gọi thẳng /tra-lai/ bị chặn (403)",
        post_with_csrf(hr, f"{path7}tra-lai/", {"return-reason": "x"}) == 403,
    )
    shot(hr, "kb7-1-hr-khong-co-nut-duyet")
    goto(hr, path7)
    check("[7] Trạng thái vẫn Chờ duyệt", status_badge(hr) == "Chờ duyệt")
    # Quản lý tự nhập, tự gửi, rồi thử tự duyệt: cũng bị chặn
    pathq = create_worker(ql, "Quản Lý Tự Duyệt", "09" + UNIQ[-6:] + "77", "999" + UNIQ[-7:] + "77")
    upload_pdf(ql, pathq, "CCCD mặt trước", pdf)
    record_consent(ql, pathq)
    goto(ql, pathq)
    ql.click(".pa-page-header__actions button:has-text('Gửi duyệt')")
    ql.wait_for_load_state("networkidle")
    check("[7] Quản lý tự gửi duyệt hồ sơ mình tạo", status_badge(ql) == "Chờ duyệt")
    check(
        "[7] Quản lý không thấy nút Duyệt hồ sơ của chính mình",
        ql.locator(".pa-page-header__actions:has-text('Duyệt hồ sơ')").count() == 0
        and "không duyệt được" in ql.content(),
    )
    check(
        "[7] Quản lý gọi thẳng /duyet/ bị chặn (403)", post_with_csrf(ql, f"{pathq}duyet/") == 403
    )
    shot(ql, "kb7-2-ql-tu-duyet-bi-chan")
    goto(ql, pathq)
    code_q = ql.locator(".pa-breadcrumb li").last.inner_text().strip()
    row_q = find_row(ql, code_q)
    check(
        "[7] Hàng đợi ghi chú 'Bạn không duyệt được hồ sơ này' đúng dòng của mình",
        row_q is not None and "Bạn không duyệt được hồ sơ này" in row_q,
    )
    shot(ql, "kb7-3-hang-doi-ghi-chu")

    # ===== Kịch bản 14: sửa họ tên hồ sơ đã xác minh =====
    goto(hr, path + "sua/")
    hr.fill("input[name=full_name]", "Nghiệm Thu Đã Đổi Tên")
    shot(hr, "kb14-1-form-sua")
    hr.click("button:has-text('Lưu hồ sơ')")
    hr.wait_for_load_state("networkidle")
    check("[14] Sau khi sửa họ tên: về Chờ duyệt", status_badge(hr) == "Chờ duyệt")
    check("[14] Có thông báo hồ sơ về Chờ duyệt", "chuyển về Chờ duyệt" in hr.content())
    goto(hr, path + "?tab=lich-su")
    check(
        "[14] HR thấy lý do 'Sửa trường định danh: họ tên' ở dòng thời gian",
        "Sửa trường định danh: họ tên" in hr.content(),
    )
    check(
        "[14] HR không thấy chi tiết trước/sau (câu 11)",
        "Chi tiết thay đổi từng trường" not in hr.content(),
    )
    shot(hr, "kb14-2-hr-lich-su")
    goto(ql, path + "?tab=lich-su")
    ql.wait_for_selector("section:has-text('Chi tiết thay đổi') .pa-table", timeout=5000)
    detail = ql.locator("section:has-text('Chi tiết thay đổi')").inner_text()
    check(
        "[14] Quản lý thấy giá trị cũ và mới trong chi tiết",
        "Nghiệm Thu Sáu Bảy" in detail and "Nghiệm Thu Đã Đổi Tên" in detail,
    )
    shot(ql, "kb14-3-ql-chi-tiet-thay-doi")
    leak = db(
        "from apps.audit.models import AuditLog as A; "
        f"qs = A.objects.filter(worker_id={worker_id}); "
        "print(any('Nghiệm Thu' in (str(e.changes)+e.note+e.object_repr) for e in qs))"
    )
    check("[14] AuditLog không chứa họ tên (chỉ AuditPersonalValue mã hóa)", leak == "False", leak)
    pv = db(
        "from apps.audit.models import AuditPersonalValue as P; "
        f"print(P.objects.filter(worker_id={worker_id}, field_name='full_name').count())"
    )
    check("[14] AuditPersonalValue có dòng giá trị cũ/mới của họ tên", pv == "1", pv)

    ctx_hr.close()
    ctx_q.close()
    browser.close()

expected_noise = ("status of 403", "status of 404", "status of 405")
real_errors = [(u, m) for u, m in console_errors if not any(n in m for n in expected_noise)]
check("Không có lỗi console ngoài 403/404 mong đợi", not real_errors, str(real_errors[:5]))

failed = [r for r in results if not r[1]]
print(f"\nTổng: {len(results)} bước, đạt {len(results) - len(failed)}, lỗi {len(failed)}")
sys.exit(1 if failed else 0)
