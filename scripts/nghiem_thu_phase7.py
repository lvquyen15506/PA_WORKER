"""Nghiệm thu Phase 7 bằng Playwright trên bản cài sạch: kịch bản 10, 11, 12, 13, 16 (yeu-cau.md mục
X), ẩn danh hóa từ danh sách chờ hủy sinh biên bản đúng (câu 2), khối "đợt sắp đủ 12 tháng" và báo
cáo theo công ty khách khớp danh sách đích.
    py -3.12 scripts/nghiem_thu_phase7.py
Cần web ở http://localhost:8000, 4 tài khoản admin, quanly, hr, viewer dùng chung mật khẩu trong
PA_TEST_PASSWORD và đã chạy seed_demo. Đối chiếu AuditLog, AuditPersonalValue bằng
`manage.py shell`.
Ảnh chụp vào docs/screenshots/phase-7/nghiem-thu/. Cần openpyxl cho Python 3.12 trên máy chạy.
"""

import datetime
import re
import sys
import tempfile
import time
from pathlib import Path

import pw_phase5 as pw
from openpyxl import Workbook, load_workbook
from playwright.sync_api import sync_playwright
from pw_phase5 import check, db, goto, login, new_page

sys.path.insert(0, str(pw.ROOT))
from apps.reports.excel_columns import COLUMNS, HEADERS  # noqa: E402  (chỉ hằng số, không cần Django)

OUT = pw.ROOT / "docs" / "screenshots" / "phase-7" / "nghiem-thu"
SIZE = pw.SIZES["1366x768"]
TODAY = datetime.date.today()
RUN = int(time.time()) % 10000
TMP = Path(tempfile.mkdtemp())
LIMIT = 2.0


def shot(page, name):
    pw.shot(OUT, page, "1366x768", name)


def total(page):
    match = re.search(r"Hiển thị \d+–\d+ / (\d+)", page.content())
    return int(match.group(1)) if match else 0


def timed_goto(page, path):
    started = time.perf_counter()
    status = goto(page, path)
    return status, time.perf_counter() - started


def card_values(page):
    """{nhãn thẻ: (số, liên kết)} của 9 thẻ Dashboard."""
    cards = {}
    for card in page.locator("a.pa-stat").all():
        label = card.locator(".pa-stat__label").inner_text().strip()
        value = card.locator(".pa-stat__value").inner_text().strip()
        cards[label] = (int(value), card.get_attribute("href"))
    return cards


def xlsx_rows(download, name):
    path = TMP / name
    download.save_as(str(path))
    return [list(r) for r in load_workbook(path).active.iter_rows(values_only=True)]


# --- Kịch bản 10: hợp đồng hết hạn sau 20 ngày hiện ở thẻ Dashboard ---------------------------
def scenario_10(browser):
    ctx, page = new_page(browser, SIZE)
    login(page, "hr")
    goto(page, "/")
    before = card_values(page)["Hợp đồng sắp hết hạn"][0]
    out = db(
        "import datetime;"
        "from apps.workers.models import Worker;"
        "from apps.employment.models import Contract;"
        "t=datetime.date.today();"
        "w=Worker.objects.filter(employment__work_status='ACTIVE')"
        ".exclude(contracts__expiry_date__range=(t,t+datetime.timedelta(days=30))).first();"
        f"Contract.objects.create(worker=w,contract_no='HD-NT7-{RUN}',contract_type='FIXED_TERM',"
        "signed_date=t-datetime.timedelta(days=300),effective_date=t-datetime.timedelta(days=300),"
        "expiry_date=t+datetime.timedelta(days=20),created_by=w.created_by);"
        "print(w.pk, w.worker_code)"
    )
    pk, code = out.split()
    goto(page, "/")
    after, href = card_values(page)["Hợp đồng sắp hết hạn"]
    shot(page, "kb10-1-dashboard")
    check(
        "KB10: hợp đồng hết hạn sau 20 ngày làm thẻ “Hợp đồng sắp hết hạn” tăng 1",
        after == before + 1,
        f"{before}->{after}",
    )
    page.click("a.pa-stat:has-text('Hợp đồng sắp hết hạn')")
    page.wait_for_load_state("networkidle")
    check(
        "KB10: số dòng danh sách bằng số trên thẻ",
        total(page) == after,
        f"{total(page)} vs {after}",
    )
    shot(page, "kb10-2-danh-sach-loc")
    goto(page, f"{href}&q={code}")  # danh sách có nhiều trang: tìm đúng mã để thấy công nhân đó
    check(
        "KB10: danh sách đã lọc có công nhân vừa thêm hợp đồng",
        code in page.content() and total(page) == 1,
    )
    ctx.close()


# --- Kịch bản 11: bấm thẻ Thiếu giấy tờ (và mọi thẻ) -> số dòng bằng số trên thẻ -----------------
def scenario_11(browser):
    for username in ("hr", "viewer", "admin"):
        ctx, page = new_page(browser, SIZE)
        login(page, username)
        goto(page, "/")
        cards = card_values(page)
        check(f"KB11 ({username}): có đủ 9 thẻ", len(cards) == 9, str(list(cards)))
        if username == "hr":
            shot(page, "kb11-1-dashboard-9-the")
            check(
                "KB11: thẻ Hoàn thiện lớn hơn 0 trên dữ liệu mẫu có tài liệu",
                cards["Hoàn thiện"][0] > 0,
            )
            check("KB11: thẻ Thiếu giấy tờ lớn hơn 0", cards["Thiếu giấy tờ"][0] > 0)
            page.click("a.pa-stat:has-text('Thiếu giấy tờ')")
            page.wait_for_load_state("networkidle")
            check(
                "KB11: bấm thẻ Thiếu giấy tờ mở danh sách đã lọc sẵn",
                "thieu_giay_to=1" in page.url and "chua-luu-tru" in page.url,
                page.url,
            )
            check(
                "KB11: số dòng bằng số trên thẻ Thiếu giấy tờ",
                total(page) == cards["Thiếu giấy tờ"][0],
                f"{total(page)} vs {cards['Thiếu giấy tờ'][0]}",
            )
            shot(page, "kb11-2-thieu-giay-to")
        for label, (value, href) in cards.items():
            goto(page, href)
            check(
                f"KB11 ({username}): thẻ {label} = số dòng danh sách đích",
                total(page) == value,
                f"{total(page)} vs {value}",
            )
        ctx.close()


# --- Kịch bản 12: tìm "nguyen van an" không dấu -------------------------------------------------
def scenario_12(browser):
    db(
        "from apps.workers.models import Worker;from apps.accounts.models import User;"
        "u=User.objects.get(username='hr');"
        f"Worker.objects.create(worker_code='HS-NT7-{RUN}',full_name='Nguyễn Văn An',"
        f"phone='0988{RUN:06d}',created_by=u);print('ok')"
    )
    ctx, page = new_page(browser, SIZE)
    login(page, "hr")
    goto(page, "/")
    started = time.perf_counter()
    box = page.locator("input[name=q]:visible").first  # ô thứ hai nằm trong menu hẹp (ẩn)
    box.fill("nguyen van an")
    box.press("Enter")
    page.wait_for_load_state("networkidle")
    elapsed = time.perf_counter() - started
    check(
        "KB12: tìm “nguyen van an” (không dấu) ra hồ sơ “Nguyễn Văn An”",
        "Nguyễn Văn An" in page.content(),
    )
    check(f"KB12: tìm kiếm dưới {LIMIT:.0f} giây ({elapsed:.2f}s)", elapsed < LIMIT)
    shot(page, "kb12-tim-khong-dau")
    ctx.close()


# --- Kịch bản 13: xuất Excel danh sách đang lọc ------------------------------------------------
def scenario_13(browser):
    base = "/ho-so/?trang_thai_lam_viec=PROBATION%2CACTIVE"
    ctx, page = new_page(browser, SIZE)
    login(page, "hr")
    status, seconds = timed_goto(page, base)
    check(
        f"KB13: mở danh sách đang lọc dưới {LIMIT:.0f} giây ({seconds:.2f}s)",
        status == 200 and seconds < LIMIT,
    )
    on_screen = total(page)
    first_names = [
        page.locator("tbody tr").nth(i).locator("td").nth(2).inner_text().strip() for i in range(3)
    ]
    before = pw.audit_count("EXPORT")
    with page.expect_download() as download:
        page.click("a:has-text('Xuất Excel')")
    rows = xlsx_rows(download.value, "ds-hr.xlsx")
    check(
        "KB13: số dòng file Excel bằng số dòng trên màn hình",
        len(rows) - 1 == on_screen,
        f"{len(rows) - 1} vs {on_screen}",
    )
    check(
        "KB13: nội dung 3 dòng đầu khớp màn hình (cùng thứ tự)",
        [r[2] for r in rows[1:4]] == first_names,
    )
    check("KB13: HR nhận số CCCD đã che", all("•" in (r[12] or "") for r in rows[1:]))
    check(
        "KB13: HR không có nút xuất kèm số CCCD đầy đủ",
        page.locator("text=Xuất kèm số CCCD").count() == 0,
    )
    check("KB13: xuất Excel ghi nhật ký EXPORT", pw.audit_count("EXPORT") == before + 1)
    ctx.close()

    ctx, page = new_page(browser, SIZE)
    login(page, "quanly")
    goto(page, base)
    page.click("button:has-text('Xuất kèm số CCCD')")
    page.wait_for_timeout(600)
    shot(page, "kb13-hop-xac-nhan-cccd")
    with page.expect_download() as download:
        page.click("#modal-export-full [data-pa-submit]")
    rows = xlsx_rows(download.value, "ds-ql.xlsx")
    full = [r[12] for r in rows[1:] if r[12]]
    check(
        "KB13: Quản lý chọn xuất kèm số CCCD thì file có số đầy đủ",
        bool(full) and all(re.fullmatch(r"\d{12}", v) for v in full),
    )
    note = db(
        "from apps.audit.models import AuditLog as A;"
        "print(A.objects.filter(action='EXPORT').order_by('-id').first().note)"
    )
    check("KB13: nhật ký ghi rõ có số CCCD đầy đủ", "có số CCCD đầy đủ" in note, note)
    ctx.close()

    ctx, page = new_page(browser, SIZE)
    login(page, "viewer")
    goto(page, base)
    check("KB13: Viewer không có nút Xuất Excel", page.locator("text=Xuất Excel").count() == 0)
    check(
        "KB13: Viewer gọi thẳng URL xuất bị từ chối (403)", goto(page, "/ho-so/xuat-excel/") == 403
    )
    goto(page, "/bao-cao/")
    check(
        "KB13: Viewer không có nút In/Xuất ở báo cáo", page.locator("text=Xuất Excel").count() == 0
    )
    check(
        "KB13: Viewer gọi thẳng URL in báo cáo bị từ chối (403)", goto(page, "/bao-cao/in/") == 403
    )
    ctx.close()


# --- Kịch bản 16: nhập file Excel có 3 dòng lỗi ---------------------------------------------------
def build_import(path, rows):
    book = Workbook()
    sheet = book.active
    sheet.title = "Hồ sơ"
    sheet.append(HEADERS)
    for row in rows:
        sheet.append([row.get(c.key) for c in COLUMNS])
    book.save(path)


def import_row(i, **over):
    row = {
        "full_name": f"Trần Thị Nhập {RUN}-{i}",
        "phone": f"06{RUN:04d}{i:04d}",
        "date_of_birth": "15/03/1995",
        "gender": "Nữ",
        "id_doc_type": "CCCD gắn chip (mẫu 2021)",
        "id_number": f"995{RUN:04d}{i:05d}",
        "issue_date": "20/06/2023",
        "contact_name": "Người Thân",
        "contact_relationship": "Chị",
        "contact_phone": "0912345678",
    }
    row.update(over)
    return row


def upload(page, path):
    page.set_input_files("input[type=file]", str(path))
    page.click("button:has-text('Nhập hồ sơ')")
    page.wait_for_load_state("networkidle")


def scenario_16(browser):
    ctx, page = new_page(browser, SIZE)
    login(page, "hr")
    goto(page, "/ho-so/them/")
    page.click("a.pa-stat:has-text('Từ file Excel')")
    page.wait_for_load_state("networkidle")
    check("KB16: thẻ “Từ file Excel” mở trang nhập", "/ho-so/nhap-excel/" in page.url)
    with page.expect_download() as download:
        page.click("a:has-text('Tải file Excel mẫu')")
    sample = TMP / "mau.xlsx"
    download.value.save_as(str(sample))
    book = load_workbook(sample)
    check(
        "KB16: file mẫu có 3 sheet và 34 cột",
        book.sheetnames == ["Hồ sơ", "Hướng dẫn", "Danh mục"] and len(book["Hồ sơ"][1]) == 34,
    )
    before = int(db("from apps.workers.models import Worker;print(Worker.objects.count())"))
    rows = [import_row(i) for i in range(10)]
    rows[2]["phone"] = "12345"  # dòng 4
    rows[5]["id_number"] = "12345678"  # dòng 7
    rows[8]["date_of_birth"] = "01/01/2020"  # dòng 10: dưới 15 tuổi
    build_import(TMP / "kb16.xlsx", rows)
    upload(page, TMP / "kb16.xlsx")
    body = page.inner_text("body")
    shot(page, "kb16-ket-qua-nhap")
    check(
        "KB16: tóm tắt đúng “nhập thành công 7 hồ sơ, 3 dòng lỗi”",
        "Đã đọc 10 dòng. Nhập thành công 7 hồ sơ. 3 dòng lỗi." in body,
        body[:300],
    )
    check(
        "KB16: báo rõ dòng 4, 7, 10 và lý do",
        all(
            x in body
            for x in (
                "Số điện thoại phải gồm 10 chữ số",
                "Số CCCD phải gồm 12 chữ số",
                "Người dưới 15 tuổi",
            )
        ),
    )
    errors = page.locator("tbody tr").all_inner_texts()
    check(
        "KB16: bảng lỗi có đúng 3 dòng 4, 7, 10",
        [e.split()[0] for e in errors] == ["4", "7", "10"],
        str(errors),
    )
    after = int(db("from apps.workers.models import Worker;print(Worker.objects.count())"))
    check("KB16: dòng đúng được nhập (7 hồ sơ mới ở trạng thái Nháp)", after - before == 7)
    drafts = db(
        "from apps.workers.models import Worker;"
        f"print(Worker.objects.filter(phone__startswith='06{RUN:04d}',verification_status='DRAFT',created_by__username='hr').count())"
    )
    check("KB16: hồ sơ nhập là Nháp, người tạo là người nhập", drafts == "7")
    check("KB16: có lời nhắc cần tài khoản khác duyệt", "cần một tài khoản khác duyệt" in body)
    imp = pw.audit_count("IMPORT")
    check("KB16: ghi nhật ký IMPORT", imp >= 1)

    # Phần B: HR bị chặn, Quản lý nhập được (mã NV cũ, công ty khách, ngày bắt đầu đợt).
    info = db(
        "from apps.core.models import Position,Section,ClientCompany;"
        "s=Section.objects.filter(is_active=True).first();p=Position.objects.filter(is_active=True).first();"
        "c=ClientCompany.objects.filter(is_active=True).first();"
        "print('|'.join([p.name,s.name,s.department.name,str(c)]))"
    )
    position, section, department, company = info.split("|")
    work = {
        "employee_code": f"NT7-{RUN}",
        "department": department,
        "section": section,
        "position": position,
        "start_date": "01/02/2023",
        "work_status": "Đang làm việc",
        "client_company": company,
        "assignment_start": "01/03/2023",
    }
    build_import(TMP / "kb16b.xlsx", [import_row(50, **work)])
    goto(page, "/ho-so/nhap-excel/")
    upload(page, TMP / "kb16b.xlsx")
    body = page.inner_text("body")
    check(
        "KB16 (v1.1): HR nhập dòng có thông tin làm việc bị báo lỗi dòng đó",
        "Chỉ Admin hoặc Quản lý nhân sự được nhập thông tin làm việc." in body,
    )
    ctx.close()

    ctx, page = new_page(browser, SIZE)
    login(page, "quanly")
    goto(page, "/ho-so/nhap-excel/")
    build_import(TMP / "kb16c.xlsx", [import_row(51, **work)])
    upload(page, TMP / "kb16c.xlsx")
    body = page.inner_text("body")
    check(
        "KB16 (v1.1): Quản lý nhập dòng có phần B thành công",
        "Nhập thành công 1 hồ sơ. 0 dòng lỗi." in body,
        body[:300],
    )
    shot(page, "kb16-quan-ly-phan-b")
    result = db(
        "from apps.workers.models import Worker;"
        f"w=Worker.objects.get(employee_code='NT7-{RUN}');"
        "a=w.work_assignments.get();"
        "print(w.verification_status, a.start_date.isoformat(), a.client_company.name, "
        "a.end_date is None, a.salary_history.count())"
    )
    check(
        "KB16 (v1.1): hồ sơ Nháp có mã NV cũ, đợt làm việc mở từ 01/03/2023, không có lương",
        result.startswith("DRAFT 2023-03-01") and result.endswith("True 0"),
        result,
    )
    ctx.close()


# --- Ẩn danh hóa từ danh sách chờ hủy sinh biên bản đúng (câu 2) ---------------------------------
def scenario_cho_huy(browser):
    # Dữ liệu thử: lùi ngày chuyển Lưu trữ 4 năm của 3 hồ sơ có căn cứ tính từ ngày Lưu trữ (bảng
    # StatusChange chỉ-thêm nên dùng SQL thô, chỉ trên CSDL thử nghiệm) và chưa quá hạn.
    ids = db(
        "from django.db import connection;from apps.workers.models import Worker;"
        "from apps.workers import retention as r;"
        "done={w.pk for w,_ in r.expired_entries()};"
        "ws=[w for w in Worker.objects.filter(verification_status='ARCHIVED',"
        "employee_code__isnull=True,anonymized_at__isnull=True).order_by('-pk') "
        "if w.pk not in done and "
        "r.retention_info(w).basis in ('REJECTED','ABANDONED','CANDIDATE_OTHER')][:3];"
        "ids=[w.pk for w in ws];"
        "c=connection.cursor();"
        "c.execute(\"UPDATE workers_statuschange SET changed_at=changed_at-interval '4 years' "
        "WHERE worker_id = ANY(%s) AND to_status='ARCHIVED'\",[ids]);print(','.join(map(str,ids)))"
    )
    pks = [int(x) for x in ids.split(",")]
    typed = db(
        "from apps.workers.models import Worker, StatusChange;"
        f"print(StatusChange.objects.filter(worker_id__in={pks},reason_by_user=True).count())"
    )
    ctx, page = new_page(browser, SIZE)
    login(page, "admin")
    goto(page, "/cai-dat/cho-huy/")
    shot(page, "cho-huy-1-danh-sach")
    codes = [
        page.locator("tbody tr").nth(i).locator("td a").first.inner_text()
        for i in range(page.locator("tbody tr").count())
    ]
    waiting_before = total(page)
    pick = db(
        "from apps.workers.models import Worker;"
        f"print(','.join(Worker.objects.filter(pk__in={pks}).order_by('pk').values_list('worker_code',flat=True)))"
    ).split(",")
    check(
        "Chờ hủy: danh sách có các hồ sơ quá hạn lưu trữ",
        all(c in codes for c in pick),
        f"{pick} / {codes}",
    )
    for code in pick[:2]:
        page.locator("tr", has_text=code).locator("input[name=workers]").check()
    page.click("button:has-text('Hủy hồ sơ đã chọn')")
    page.wait_for_timeout(600)
    shot(page, "cho-huy-2-hop-xac-nhan")
    page.click("#modal-huy [data-pa-submit]")
    page.wait_for_load_state("networkidle")
    body = page.inner_text("body")
    shot(page, "cho-huy-3-bien-ban")
    check(
        "Chờ hủy: sau khi xác nhận sang trang biên bản",
        re.search(r"Biên bản hủy BBH-\d{4}-\d{3}", body) is not None,
        body[:200],
    )
    check(
        "Chờ hủy: biên bản liệt kê đúng 2 hồ sơ đã chọn, loại Hết hạn lưu trữ",
        all(c in body for c in pick[:2])
        and "Hết hạn lưu trữ" in body
        and pick[2] not in body.split("Hồ sơ đã hủy")[-1],
    )
    done = db(
        "from apps.workers.models import Worker, AnonymizationItem as I;"
        "from apps.audit.models import AuditLog as A, AuditPersonalValue as P;"
        f"ws=list(Worker.objects.filter(worker_code__in={pick[:2]}));"
        "print(sum(w.anonymized_at is not None for w in ws), "
        "I.objects.filter(worker__in=ws).count(), "
        "A.objects.filter(action='ANONYMIZE',worker__in=ws).count(), "
        "P.objects.filter(worker__in=ws).count())"
    )
    check(
        "Chờ hủy: 2 hồ sơ đã ẩn danh, 2 dòng biên bản, 2 dòng nhật ký ANONYMIZE, "
        "không còn giá trị cá nhân trong nhật ký",
        done == "2 2 2 0",
        done,
    )
    reasons = db(
        "from apps.workers.models import StatusChange as S;"
        f"qs=S.objects.filter(worker__worker_code__in={pick[:2]},reason_by_user=True);"
        "print(qs.count(), qs.exclude(reason='(đã ẩn danh)').count())"
    )
    check(
        "Chờ hủy: mọi lý do do người gõ ở dòng thời gian trạng thái là “(đã ẩn danh)”",
        reasons.endswith(" 0"),
        f"{reasons} (trước: {typed} lý do người gõ của 3 hồ sơ)",
    )
    goto(page, "/cai-dat/cho-huy/")
    check(
        "Chờ hủy: hồ sơ đã hủy rời khỏi danh sách chờ hủy",
        total(page) == waiting_before - 2 or "Không có hồ sơ nào" in page.content(),
    )
    before_print = pw.audit_count("PRINT")
    goto(page, "/cai-dat/bien-ban-huy/")
    shot(page, "bien-ban-1-danh-sach")
    page.locator("tbody tr").first.locator("td a").first.click()
    page.wait_for_load_state("networkidle")
    page.click("a:has-text('In biên bản')")
    page.wait_for_load_state("networkidle")
    shot(page, "bien-ban-2-in")
    check("Biên bản: mở bản in ghi nhật ký PRINT", pw.audit_count("PRINT") == before_print + 1)
    ctx.close()


# --- Khối 12 tháng và báo cáo công ty khách khớp danh sách đích -----------------------------------
def scenario_v11(browser):
    ctx, page = new_page(browser, SIZE)
    login(page, "viewer")
    goto(page, "/")
    heading = page.locator("h3.pa-card-title", has_text="Đợt làm việc sắp đủ").inner_text()
    count = int(re.search(r"\((\d+)\)", heading).group(1))
    check(
        "v1.1: Dashboard có khối “Đợt làm việc sắp đủ 12 tháng”",
        count >= 0 and "12 tháng" in heading,
        heading,
    )
    goto(page, "/ho-so/?dot_sap_du_han=1")
    check(
        "v1.1: số trong khối bằng số dòng của /ho-so/?dot_sap_du_han=1",
        total(page) == count,
        f"{total(page)} vs {count}",
    )
    check(
        "v1.1: không có thẻ thứ 10 (vẫn 9 thẻ)", len(card_values(page)) == 0
    )  # trang danh sách không có thẻ
    goto(page, "/")
    check("v1.1: Dashboard vẫn đúng 9 thẻ", len(card_values(page)) == 9)

    for code in ("cong-ty-khach", "phong-ban", "chuc-danh", "trinh-do"):
        goto(page, f"/bao-cao/?loai={code}")
        links = [
            (a.inner_text().strip(), a.get_attribute("href")) for a in page.locator("tbody a").all()
        ]
        if code == "cong-ty-khach":
            shot(page, "v11-bao-cao-cong-ty-khach")
        check(f"Báo cáo {code}: có số liệu bấm được", len(links) > 0)
        mismatch = []
        for text, href in links:
            goto(page, href)
            if total(page) != int(text):
                mismatch.append((text, href, total(page)))
        check(
            f"Báo cáo {code}: mỗi số bằng số dòng danh sách đích ({len(links)} liên kết)",
            not mismatch,
            str(mismatch[:3]),
        )
        goto(page, f"/bao-cao/?loai={code}")
        if code == "phong-ban":
            check(
                "Báo cáo phòng ban có nhóm “Chưa có bộ phận”", "Chưa có bộ phận" in page.content()
            )
    ctx.close()


# --- Phân quyền các trang mới -------------------------------------------------------------------
def scenario_quyen(browser):
    matrix = {
        "admin": {
            "/nhat-ky/": 200,
            "/cai-dat/cho-huy/": 200,
            "/cai-dat/bien-ban-huy/": 200,
            "/bao-cao/": 200,
            "/ho-so/nhap-excel/": 200,
        },
        "quanly": {
            "/nhat-ky/": 200,
            "/cai-dat/cho-huy/": 403,
            "/cai-dat/bien-ban-huy/": 403,
            "/bao-cao/": 200,
            "/ho-so/nhap-excel/": 200,
        },
        "hr": {
            "/nhat-ky/": 403,
            "/cai-dat/cho-huy/": 403,
            "/cai-dat/bien-ban-huy/": 403,
            "/bao-cao/": 200,
            "/ho-so/nhap-excel/": 200,
        },
        "viewer": {
            "/nhat-ky/": 403,
            "/cai-dat/cho-huy/": 403,
            "/cai-dat/bien-ban-huy/": 403,
            "/bao-cao/": 200,
            "/ho-so/nhap-excel/": 403,
        },
    }
    for username, pages in matrix.items():
        ctx, page = new_page(browser, SIZE)
        login(page, username)
        for path, expected in pages.items():
            status = goto(page, path)
            check(f"Quyền: {username} {path} → {expected}", status == expected, str(status))
        if username == "viewer":
            goto(page, "/")
            check(
                "Quyền: Viewer không thấy khối “Chờ duyệt” ở việc cần làm",
                "Chờ duyệt (" not in page.content(),
            )
        ctx.close()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        scenario_10(browser)
        scenario_11(browser)
        scenario_12(browser)
        scenario_13(browser)
        scenario_16(browser)
        scenario_cho_huy(browser)
        scenario_v11(browser)
        scenario_quyen(browser)
        browser.close()
    noise = [e for e in pw.console_errors if not any(n in e[1] for n in pw.EXPECTED_NOISE)]
    check("Không có lỗi console ngoài 403/404/405 mong đợi", not noise, str(noise[:5]))
    failed = [r for r in pw.results if not r[1]]
    print(f"\n{len(pw.results) - len(failed)}/{len(pw.results)} bước đạt")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
