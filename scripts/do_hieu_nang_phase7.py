"""Đo hiệu năng Phase 7 qua HTTP (như người dùng thật): mở danh sách, lọc, tìm kiếm, Dashboard, báo
cáo, xuất Excel, nhật ký, chờ hủy. Ghi bảng vào docs/hieu-nang.md.

Cần web ở http://localhost:8000 đã có `seed_demo` (500 hồ sơ) và tài khoản `admin` với mật khẩu
trong biến môi trường PA_TEST_PASSWORD. Yêu cầu (yeu-cau.md VII): với 500 hồ sơ, mở danh sách, lọc,
tìm kiếm dưới 2 giây.

    py -3.12 scripts/do_hieu_nang_phase7.py            # đo trang, ghi docs/hieu-nang.md
    py -3.12 scripts/do_hieu_nang_phase7.py --nhap     # thêm đo nhập Excel 1.000 dòng (TẠO 1.000
                                                       # hồ sơ thật: chỉ chạy cuối đợt nghiệm thu)
"""

import http.cookiejar
import io
import json
import os
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = os.environ.get("PA_BASE_URL", "http://localhost:8000")
PASSWORD = os.environ["PA_TEST_PASSWORD"]
RUNS = 5
LIMIT = 2.0  # giây
OUT = ROOT / "docs" / "hieu-nang.md"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def fetch(path, data=None, headers=None):
    request = urllib.request.Request(BASE + path, data=data, headers=headers or {})
    started = time.perf_counter()
    with opener.open(request, timeout=300) as response:
        body = response.read()
    return time.perf_counter() - started, response.status, body


def csrf():
    return next(c.value for c in jar if c.name == "csrftoken")


def login(username="admin"):
    fetch("/dang-nhap/")
    form = urllib.parse.urlencode(
        {"username": username, "password": PASSWORD, "csrfmiddlewaretoken": csrf()}
    ).encode()
    fetch("/dang-nhap/", form, {"Referer": BASE + "/dang-nhap/"})


def option_values(html, select_name):
    block = re.search(rf'<select[^>]*name="{select_name}".*?</select>', html, flags=re.S)
    return re.findall(r'value="(\d+)"', block.group(0)) if block else []


def measure(label, path):
    fetch(path)  # làm nóng (kết nối, bộ nhớ đệm), không tính
    times = []
    for _ in range(RUNS):
        seconds, status, body = fetch(path)
        assert status == 200, (path, status)
        # Không được là trang đăng nhập (phiên hết hạn sẽ chuyển hướng về đó với mã 200).
        assert b'name="password"' not in body, f"bị chuyển về trang đăng nhập: {path}"
        times.append(seconds)
    return label, path, statistics.median(times), max(times)


def multipart(name, filename, content):
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="csrfmiddlewaretoken"\r\n\r\n{csrf()}\r\n'.encode(),
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            "Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n"
        ).encode()
        + content
        + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def build_import_file(rows, with_work):
    from openpyxl import Workbook

    sys.path.insert(0, str(ROOT))
    from apps.reports.excel_columns import COLUMNS, HEADERS  # chỉ lấy hằng số, không cần Django

    book = Workbook()
    sheet = book.active
    sheet.title = "Hồ sơ"
    sheet.append(HEADERS)
    stamp = int(time.time()) % 100000
    for i in range(rows):
        row = {
            "full_name": f"Nguyễn Văn Đo {i}",
            "phone": f"07{(stamp * 1000 + i) % 100000000:08d}",
            "date_of_birth": "15/03/1995",
            "gender": "Nam",
            "id_doc_type": "CCCD gắn chip (mẫu 2021)",
            "id_number": f"996{(stamp * 1000 + i) % 1000000000:09d}",
            "issue_date": "20/06/2023",
            "contact_name": "Người Thân",
            "contact_relationship": "Anh",
            "contact_phone": "0912345678",
        }
        if with_work:
            row.update(
                {
                    "employee_code": f"DO{stamp}-{i}",
                    "position": "Công nhân",
                    "start_date": "01/02/2023",
                    "work_status": "Đang làm việc",
                }
            )
        sheet.append([row.get(c.key) for c in COLUMNS])
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def measure_import(rows, with_work):
    content = build_import_file(rows, with_work)
    login()  # phiên mới để lấy CSRF mới
    fetch("/ho-so/nhap-excel/")
    body, content_type = multipart("file", "nhap.xlsx", content)
    seconds, status, html = fetch(
        "/ho-so/nhap-excel/", body, {"Content-Type": content_type, "Referer": BASE + "/ho-so/nhap-excel/"}
    )
    text = html.decode("utf-8", "replace")
    match = re.search(r"Đã đọc (\d+) dòng\. Nhập thành công (\d+) hồ sơ\. (\d+) dòng lỗi", text)
    return seconds, status, match.groups() if match else None


def main():
    login()
    page = fetch("/ho-so/")[2].decode()
    company = (option_values(page, "cong_ty_khach") or ["1"])[0]
    level = (option_values(page, "trinh_do") or ["1"])[0]
    targets = [
        ("Dashboard", "/"),
        ("Danh sách hồ sơ (không lọc)", "/ho-so/"),
        ("Danh sách trang 5", "/ho-so/?trang=5"),
        ("Tìm không dấu “nguyen van an” (kịch bản 12)", "/ho-so/?q=nguyen+van+an"),
        ("Tìm theo số CCCD 12 chữ số", "/ho-so/?q=999000000123"),
        ("Tìm theo SĐT", "/ho-so/?q=0912"),
        ("Lọc chưa Lưu trữ", "/ho-so/?trang_thai_ho_so=chua-luu-tru"),
        ("Lọc Thiếu giấy tờ (kịch bản 11)", "/ho-so/?thieu_giay_to=1&trang_thai_ho_so=chua-luu-tru"),
        ("Lọc Hoàn thiện", "/ho-so/?hoan_thien=1"),
        ("Lọc đang làm việc", "/ho-so/?trang_thai_lam_viec=PROBATION%2CACTIVE"),
        ("Lọc hợp đồng sắp hết hạn (kịch bản 10)", "/ho-so/?hop_dong_sap_het_han=1"),
        ("Lọc đợt sắp đủ 12 tháng", "/ho-so/?dot_sap_du_han=1"),
        ("Lọc CCCD sắp hết hạn", "/ho-so/?cccd_sap_het_han=1"),
        ("Lọc công ty khách", f"/ho-so/?cong_ty_khach={company}"),
        ("Lọc chưa có bộ phận", "/ho-so/?bo_phan=chua-co"),
        ("Lọc trình độ", f"/ho-so/?trinh_do={level}"),
        ("Lọc trạng thái tuyển dụng", "/ho-so/?trang_thai_tuyen_dung=NEW"),
        ("Xuất Excel danh sách (kịch bản 13)", "/ho-so/xuat-excel/"),
        ("Xuất Excel danh sách đang lọc", "/ho-so/xuat-excel/?trang_thai_lam_viec=PROBATION%2CACTIVE"),
        ("Tuyển dụng", "/tuyen-dung/"),
        ("Duyệt hồ sơ", "/duyet-ho-so/"),
        ("Nhật ký", "/nhat-ky/"),
        ("Nhật ký lọc hành động", "/nhat-ky/?hanh_dong=CREATE"),
        ("Chờ hủy", "/cai-dat/cho-huy/"),
        ("Biên bản hủy", "/cai-dat/bien-ban-huy/"),
    ]
    reports = [
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
    targets += [(f"Báo cáo {code}", f"/bao-cao/?loai={code}") for code in reports]
    targets += [("Xuất Excel báo cáo phong-ban", "/bao-cao/xuat-excel/?loai=phong-ban")]
    results = []
    for label, path in targets:
        result = measure(label, path)
        results.append(result)
        flag = "ĐẠT" if result[3] < LIMIT else "CHẬM"
        print(f"{flag}  {result[2]:.2f}s (max {result[3]:.2f}s)  {label}")
    imports = []
    if "--nhap" in sys.argv:
        for rows, with_work in ((1000, False), (1000, True)):
            seconds, status, counts = measure_import(rows, with_work)
            imports.append((rows, with_work, seconds, status, counts))
            print(f"Nhập {rows} dòng (phần B: {with_work}): {seconds:.1f}s {status} {counts}")
    write_report(results, imports)
    slow = [r for r in results if r[3] >= LIMIT]
    print(f"{len(results) - len(slow)}/{len(results)} trang dưới {LIMIT} giây")
    return 1 if slow else 0


def write_report(results, imports):
    lines = [
        "# Hiệu năng – Phase 7",
        "",
        f"Đo ngày {time.strftime('%d/%m/%Y')} bằng `scripts/do_hieu_nang_phase7.py` qua HTTP (như người "
        "dùng thật) trên bản cài sạch Docker Compose (`docker compose -f docker-compose.yml`, "
        "Gunicorn 3 worker, PostgreSQL 16) với `seed_demo` 500 hồ sơ, tài khoản Admin. Mỗi trang "
        f"đo {RUNS} lần sau 1 lần làm nóng; bảng ghi trung vị và lớn nhất. Yêu cầu "
        "(`docs/yeu-cau.md` mục VII): mở danh sách, lọc, tìm kiếm **dưới 2 giây**.",
        "",
        "| Trang | Trung vị (giây) | Lớn nhất (giây) | Kết quả |",
        "| --- | --- | --- | --- |",
    ]
    for label, path, median, worst in results:
        verdict = "Đạt" if worst < LIMIT else "Chậm"
        lines.append(f"| {label} (`{path}`) | {median:.2f} | {worst:.2f} | {verdict} |")
    lines.append("")
    if imports:
        lines += [
            "## Nhập Excel",
            "",
            "Giới hạn dòng mỗi lần nhập được chốt theo kết quả đo; quá 90 giây thì phải hạ giới hạn "
            "(không tăng timeout Gunicorn, hiện 120 giây).",
            "",
            "| Số dòng | Có phần B (mã NV, đợt làm việc) | Thời gian (giây) | Kết quả đọc |",
            "| --- | --- | --- | --- |",
        ]
        for rows, with_work, seconds, status, counts in imports:
            lines.append(
                f"| {rows} | {'có' if with_work else 'không'} | {seconds:.1f} | HTTP {status}; "
                f"{json.dumps(counts, ensure_ascii=False)} |"
            )
        worst = max(item[2] for item in imports)
        lines += [
            "",
            f"**Kết luận:** lần chậm nhất {worst:.1f} giây "
            + ("(≤ 90 giây) nên giữ giới hạn 1.000 dòng." if worst <= 90 else "(> 90 giây) nên hạ giới hạn dòng."),
        ]
        lines.append("")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
