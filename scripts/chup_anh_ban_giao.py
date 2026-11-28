"""Chụp ~25 ảnh minh họa cho 3 tài liệu bàn giao Word, trên bản Demo (dữ liệu giả,
số CCCD 999…), khoanh khung đỏ đúng chỗ cần bấm bằng Pillow. Lưu vào
docs/ban-giao/anh/. Chạy:
    PA_TEST_PASSWORD=<mat-khau> py -3.12 scripts/chup_anh_ban_giao.py

Yêu cầu: web bản Demo đang chạy ở http://localhost:8000, đã seed_demo (500 hồ sơ
giả). Script tự tạo thêm vài hồ sơ/đối tượng giả (hồ sơ Chờ duyệt, hồ sơ Đã xác
minh có lần ứng tuyển Đạt, đợt làm việc + công ty khách + vị trí) để chụp được
mọi màn hình. Khung đỏ vẽ ngay trên ảnh (Pillow) từ tọa độ phần tử cần bấm của
Playwright; ảnh "Sao lưu (cửa sổ Sao luu.bat)" là mô phỏng cửa sổ cmd vẽ bằng
Pillow vì không có Windows cmd thật trong môi trường này.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pw_phase5 as pw
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
from pw_phase5 import CARD_DIR, compose, gen_cards, login, new_page

ROOT = pw.ROOT
BASE = pw.BASE
OUT = ROOT / "docs" / "ban-giao" / "anh"
OUT.mkdir(parents=True, exist_ok=True)

ok, fail = [], []


def cap(page, name, frame_selector=None, note="", full=True):
    """Chụp cả trang (full=False: chỉ khung nhìn, dùng cho hộp thoại), vẽ khung đỏ quanh phần
    tử cần bấm (nếu có), lưu OUT/name.png."""
    page.wait_for_load_state("networkidle")
    shot_path = OUT / f"{name}.png"
    if full:
        page.evaluate("window.scrollTo(0, 0)")
    else:
        page.wait_for_timeout(600)  # chờ hiệu ứng mở hộp thoại
    page.screenshot(path=str(shot_path), full_page=full)
    if frame_selector:
        _khung_do(shot_path, page, frame_selector, full)
    ok.append(name)
    print(f"[OK] {name}.png" + (f"  ({note})" if note else ""))


def _khung_do(shot_path: Path, page, selector, full=True):
    try:
        el = page.locator(selector).first
        # Tọa độ theo tài liệu (ảnh cả trang) = khung nhìn + vị trí cuộn; không cuộn trang.
        rect = el.evaluate(
            "e => { const r = e.getBoundingClientRect();"
            " return {x: r.x + window.scrollX, y: r.y + window.scrollY,"
            " width: r.width, height: r.height}; }"
        )
        box = rect if full else el.bounding_box()
        if not box or not box["width"]:
            print(f"    (phần tử {selector!r} không hiển thị, không vẽ khung)")
            return
        img = Image.open(shot_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        x, y, w, h = box["x"], box["y"], box["width"], box["height"]
        x, y, w, h = x - 4, y - 4, w + 8, h + 8  # chừa lề để khung không đè chữ
        for t in range(5):  # khung đỏ dày 5 px
            draw.rectangle([x - t, y - t, x + w + t, y + h + t], outline="red")
        img.save(shot_path, "PNG")
    except Exception as e:  # khung đỏ là điểm nhấn, lỗi khung không làm hỏng ảnh
        print(f"    (không vẽ được khung đỏ {selector!r}: {e})")


# ---- chuẩn bị dữ liệu giả -------------------------------------------------
def prep():
    """Đặt lại mật khẩu 4 tài khoản (không in), tạo hồ sơ/đối tượng giả. In JSON."""
    # Chỉ chọn trong dữ liệu seed_demo có sẵn (đều là dữ liệu giả, CCCD 999…), không tạo bằng tay.
    code = r"""
import json, os
from django.contrib.auth import get_user_model
from apps.workers.models import Worker
from apps.recruitment.models import Application
from apps.employment.models import WorkAssignment
from apps.employment.services import can_onboard
U = get_user_model()
pw = os.environ['PW']
for u in U.objects.filter(username__in=['admin', 'quanly', 'hr', 'viewer']):
    u.set_password(pw); u.must_change_password = False
    u.is_active = True; u.locked_until = None; u.failed_login_count = 0; u.save()
out = {}
out['w_pend'] = Worker.objects.filter(verification_status='PENDING').order_by('pk').first().pk
out['w_draft'] = Worker.objects.filter(verification_status='DRAFT').order_by('pk').first().pk
# lần ứng tuyển Đạt, hồ sơ Đã xác minh, chưa tiếp nhận (chưa có mã NV)
apps_ = Application.objects.filter(status='PASSED', worker__employee_code__isnull=True)
app = next((a for a in apps_.select_related('worker').order_by('pk')
            if can_onboard(a, a.worker)), None)
if app is None:  # seed không có sẵn: thêm lần ứng tuyển Đạt qua service (ghi nhật ký như thường)
    import datetime
    from apps.core.models import ApplicationSource, Position
    from apps.recruitment.services import add_application
    wr = Worker.objects.filter(verification_status='VERIFIED', employee_code__isnull=True,
                               anonymized_at__isnull=True).order_by('pk').first()
    app = add_application(U.objects.get(username='quanly'), wr,
                          position=Position.objects.filter(is_active=True).first(),
                          source=ApplicationSource.objects.filter(is_active=True).first(),
                          applied_date=datetime.date.today(), status='PASSED')
out['app_pass'] = app.pk
out['w_ready'] = app.worker_id
asg = WorkAssignment.objects.filter(end_date__isnull=True).order_by('pk').first()
out['asg'] = asg.pk
out['w_ver'] = asg.worker_id
print(json.dumps(out))
"""
    # đặt mật khẩu qua biến môi trường (-e PW) để không lộ vào dòng lệnh
    env = {**os.environ, "PW": pw.PASSWORD}
    run = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "-e",
            "PW",
            "web",
            "python",
            "manage.py",
            "shell",
            "-c",
            code,
        ],  # fmt: skip
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    lines = [line for line in run.stdout.splitlines() if line.strip()]
    if lines:
        try:
            return json.loads(lines[-1])
        except json.JSONDecodeError:
            pass
    print("LỖI chuẩn bị dữ liệu:\n" + (run.stdout + run.stderr)[-2000:])
    raise SystemExit(1)


def make_sample_xlsx(dest: Path, run_id: str):
    """File .xlsx 1 dòng đúng + 2 dòng sai (chạy trong container, docker-cp ra host)."""
    code = r"""
import json, os
import openpyxl
wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'Hồ sơ'
from apps.reports.excel_columns import COLUMNS, BY_KEY
ws.append([c.header for c in COLUMNS])
import datetime
today = datetime.date.today().strftime('%d/%m/%Y')
def row(**kw):
    r = [None]*len(COLUMNS)
    for i, c in enumerate(COLUMNS):
        r[i] = kw.get(c.key)
    return r
rid = os.environ.get('RID','X')
ws.append(row(full_name=f'Giả Excel {rid}', phone='090'+rid.zfill(7), date_of_birth='01/01/1990',
              gender='Nam', nationality='Việt Nam', current_address='Khu trọ Mẫu',
              contact_name='Người Thân Giả', contact_relationship='Anh',
              contact_phone='0988777666'))
ws.append(row(phone='12'))  # dòng sai: thiếu họ tên + SĐT sai
ws.append(row(full_name='X'*200, phone='abc'))  # dòng sai: họ tên quá dài + SĐT sai
wb.save('/tmp/pa_sample.xlsx')
print('done')
"""
    env = {**os.environ, "RID": run_id}
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "-e",
            "RID",
            "web",
            "python",
            "manage.py",
            "shell",
            "-c",
            code,
        ],  # fmt: skip
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    compose("cp", "web:/tmp/pa_sample.xlsx", str(dest))


def sao_luu_console():
    """Ảnh mô phỏng cửa sổ cmd chạy Sao luu.bat (không có Windows thật trong môi trường này)."""
    lines = [
        ("==== PA Worker – sao lưu ====", "cyan"),
        ("-> Kiểm tra Docker và PA Worker…", "white"),
        ("OK: PA Worker đang chạy.", "green"),
        ("Đang sao lưu…", "white"),
        ("Đã sao lưu: pa-worker-20261124-173000.pawbk", "green"),
        ("Dung lượng 3,6 MB, 1509 tệp hồ sơ; đã tự kiểm tra: đọc lại được.", "white"),
        ("File sao lưu nằm trong thư mục: C:\\PA Worker\\backups", "white"),
        ("Hãy chép file mới nhất ra USB hoặc ổ đĩa ngoài.", "yellow"),
    ]
    W, H = 900, 360
    img = Image.new("RGB", (W, H), "black")
    draw = ImageDraw.Draw(img)
    font = None
    for name in ("consola.ttf", "segoeui.ttf", "DejaVuSans.ttf"):  # font có dấu tiếng Việt
        try:
            font = ImageFont.truetype(name, 15)
            break
        except OSError:
            continue
    font = font or ImageFont.load_default()
    y = 18
    for text, color in lines:
        cmap = {
            "cyan": (0, 200, 230),
            "green": (80, 220, 120),
            "yellow": (230, 220, 60),
            "white": (230, 230, 230),
        }
        draw.text((24, y), text, font=font, fill=cmap[color])
        y += 32
    # khung đỏ quanh dòng tên file sao lưu (chỗ quan trọng)
    for t in range(4):
        draw.rectangle([18 - t, 140 - t, 700 + t, 170 + t], outline="red")  # dòng thứ 5
    img.save(OUT / "sao-luu-cua-so.png", "PNG")
    ok.append("sao-luu-cua-so")
    print("[OK] sao-luu-cua-so.png (mô phỏng cửa sổ cmd)")


def main():
    cards = gen_cards()
    good = next((c for c in cards if c["quality"] == "good"), cards[0])
    p = prep()
    run_id = str(abs(hash(os.environ.get("PA_TEST_PASSWORD", "x"))) % 9999).zfill(2)
    sample_xlsx = Path(tempfile.mkdtemp()) / "sample.xlsx"
    make_sample_xlsx(sample_xlsx, run_id)

    with sync_playwright() as pl:
        browser = pl.chromium.launch(headless=True)

        # ===== cài đặt: đăng nhập, đổi mật khẩu =====
        ctx, page = new_page(browser, (1366, 768))
        page.goto(f"{BASE}/dang-nhap/")
        page.fill("input[name=username]", "admin")
        cap(page, "dang-nhap", "form", "trang đăng nhập")
        login(page, "admin")
        # lần đầu đăng nhập hệ thống tự chuyển tới trang này; ở đây mở thẳng URL
        page.goto(f"{BASE}/doi-mat-khau/")
        cap(page, "doi-mat-khau", "main form", "trang Đổi mật khẩu lần đầu")
        ctx.close()
        ctx, page = new_page(browser, (1366, 768))

        # ===== sử dụng: dashboard, tìm, lọc =====
        login(page, "hr")
        page.goto(f"{BASE}/")
        page.wait_for_load_state("networkidle")
        cap(page, "dashboard", ".pa-stat", "Tổng quan (Dashboard)")
        page.fill(".pa-topbar__search input[name=q]", "nguyen van")
        cap(page, "tinh-nhan", ".pa-topbar__search", "ô tìm nhanh")
        page.goto(f"{BASE}/ho-so/?reset=1")
        page.wait_for_load_state("networkidle")
        cap(page, "danh-sach-loc", "button:has-text('Lọc')", "thanh lọc danh sách")
        ctx.close()

        # ===== HR: nhập tay, CCCD, tải tài liệu, gửi duyệt =====
        ctx, page = new_page(browser, (1366, 768))
        login(page, "hr")
        page.goto(f"{BASE}/ho-so/them/nhap-tay/")
        cap(page, "them-nhap-tay", "button:has-text('Lưu hồ sơ')", "form nhập tay")

        # nhập từ CCCD: tải ảnh thật, đến màn đối chiếu
        page.goto(f"{BASE}/nhap-cccd/")
        page.set_input_files("input[name=front_image]", str(CARD_DIR / good["files"]["front"]))
        page.set_input_files("input[name=back_image]", str(CARD_DIR / good["files"]["back"]))
        cap(page, "nhap-cccd-tai-anh", "main form", "chọn ảnh mặt trước, mặt sau")
        page.click("button:has-text('Nhận diện')")
        page.wait_for_load_state("networkidle")
        cap(page, "doi-chieu-cccd", "img[class*=img-fluid]", "màn đối chiếu CCCD")
        # tích các ô Đã kiểm tra để bật nút Lưu hồ sơ
        boxes = page.locator("input[data-pa-checked]")
        n = min(boxes.count(), 6)
        for i in range(n):
            boxes.nth(i).check()
        cap(page, "doi-chieu-da-kiem-tra", "button[data-pa-gate]", "đã tích Đã kiểm tra")
        # hủy phiên để không tạo hồ sơ thừa
        try:
            page.click("button:has-text('Hủy phiên')")
            page.wait_for_selector("#cancel-session.show", timeout=5000)
            page.click("#cancel-session button[data-pa-submit]")
        except Exception:
            pass

        # tải tài liệu
        page.goto(f"{BASE}/ho-so/{p['w_draft']}/tai-lieu/them/")
        cap(page, "tao-tai-lieu", "button:has-text('Tải tài liệu lên')", "tải tài liệu lên")

        # gửi duyệt: nút chỉ có ở hồ sơ Nháp / Cần bổ sung
        page.goto(f"{BASE}/ho-so/{p['w_draft']}/")
        cap(
            page,
            "gui-duyet",
            ".pa-page-header__actions button:has-text('Gửi duyệt')",
            "nút Gửi duyệt",
        )
        ctx.close()

        # ===== QL: duyệt, trả lại =====
        ctx, page = new_page(browser, (1366, 768))
        login(page, "quanly")
        page.goto(f"{BASE}/duyet-ho-so/")
        cap(page, "duyet-ho-so", ".pa-table tbody tr", "hàng đợi duyệt hồ sơ")
        page.goto(f"{BASE}/ho-so/{p['w_pend']}/")
        cap(
            page,
            "nut-duyet",
            ".pa-page-header__actions button:has-text('Duyệt hồ sơ')",
            "nút Duyệt hồ sơ",
        )
        # mở hộp Trả lại
        page.click(".pa-page-header__actions button:has-text('Trả lại')")
        page.wait_for_selector("#return-modal.show", timeout=5000)
        cap(
            page,
            "tra-lai-ho-so",
            "#return-modal textarea",
            "hộp Trả lại (lý do)",
            full=False,
        )
        page.keyboard.press("Escape")
        ctx.close()

        # ===== v1.1.1: thêm công ty khách (Admin, Cài đặt → Danh mục → Công ty khách) =====
        ctx, page = new_page(browser, (1366, 768))
        login(page, "admin")
        page.goto(f"{BASE}/cai-dat/danh-muc/cong-ty-khach/")
        cap(page, "cong-ty-khach-cai-dat", "select[name=loai]",
            "Cài đặt → Danh mục, chọn loại Công ty khách")  # fmt: skip
        cap(page, "cong-ty-khach-danh-sach", "a:has-text('Thêm công ty khách')",
            "danh sách công ty khách, nút Thêm")  # fmt: skip
        page.goto(f"{BASE}/cai-dat/danh-muc/cong-ty-khach/them/")
        page.fill("input[name=name]", "Công ty Mẫu Hướng Dẫn")
        page.fill("input[name=location]", "Tỉnh Mẫu")
        cap(page, "cong-ty-khach-them", "main form", "form thêm công ty khách")
        ctx.close()

        # ===== ứng tuyển -> tiếp nhận (+ gán công ty ngay), đợt + lương =====
        ctx, page = new_page(browser, (1366, 768))
        login(page, "quanly")
        page.goto(f"{BASE}/ho-so/{p['w_ready']}/?tab=lam-viec")
        cap(page, "tab-lam-viec-chua-tiep-nhan", "main .alert-info",
            "tab Quá trình làm việc khi chưa có mã NV")  # fmt: skip
        page.goto(f"{BASE}/ho-so/{p['w_ready']}/?tab=tuyen-dung")
        try:
            page.locator(".pa-table tbody tr .dropdown-toggle").first.click()
            cap(page, "ung-tuyen-tiep-nhan", ".dropdown-menu.show",
                "menu Thêm → Tiếp nhận vào làm ở tab Tuyển dụng", full=False)  # fmt: skip
        except Exception:
            cap(page, "ung-tuyen-tiep-nhan", ".pa-table", "tab Tuyển dụng & CV")
        page.goto(f"{BASE}/ung-tuyen/{p['app_pass']}/tiep-nhan/")
        cap(page, "tiep-nhan-vao-lam", "main form", "form tiếp nhận vào làm")
        cap(page, "tiep-nhan-gan-cong-ty", "section:has(select[name=assign_client_company])",
            "phần Gán công ty khách ngay")  # fmt: skip
        page.goto(f"{BASE}/ho-so/{p['w_ver']}/?tab=lam-viec")
        cap(page, "tab-lam-viec-them-dot", "a:has-text('Thêm đợt làm việc')",
            "nút Thêm đợt làm việc")  # fmt: skip
        page.goto(f"{BASE}/ho-so/{p['w_ver']}/dot-lam-viec/them/")
        cap(page, "them-dot-lam-viec", "select[name=client_company]", "form thêm đợt làm việc")
        page.goto(f"{BASE}/dot-lam-viec/{p['asg']}/luong/them/")
        cap(page, "them-luong", "main button[type=submit]", "form ghi nhận lương")
        ctx.close()

        # ===== xuất Excel, nhập Excel (kết quả), báo cáo =====
        ctx, page = new_page(browser, (1366, 768))
        login(page, "hr")
        page.goto(f"{BASE}/ho-so/?reset=1")
        cap(page, "xuat-excel", "a:has-text('Xuất Excel')", "nút Xuất Excel danh sách")
        page.goto(f"{BASE}/ho-so/nhap-excel/")
        page.set_input_files("input[type=file]", str(sample_xlsx))
        page.click("button:has-text('Nhập hồ sơ')")
        page.wait_for_load_state("networkidle")
        cap(page, "nhap-excel-ket-qua", "table", "kết quả nhập Excel (dòng lỗi)")
        page.goto(f"{BASE}/bao-cao/?loai=phong-ban")
        cap(
            page,
            "bao-cao",
            "a:has-text('Xuất Excel'), button:has-text('In báo cáo')",
            "báo cáo theo phòng ban",
        )
        ctx.close()

        # ===== Admin: khóa / mở khóa tài khoản =====
        ctx, page = new_page(browser, (1366, 768))
        login(page, "admin")
        page.goto(f"{BASE}/tai-khoan/")
        cap(page, "khoa-tai-khoan", ".pa-table tbody tr .dropdown-toggle", "nút Khóa tài khoản")
        # mở dropdown của một dòng để hiện "Mở khóa"/"Khóa"
        try:
            page.locator(".pa-table tbody tr .dropdown-toggle").first.click()
            cap(page, "mo-khoa-tai-khoan", ".dropdown-menu.show", "menu Khóa / Mở khóa", full=False)
        except Exception:
            cap(page, "mo-khoa-tai-khoan", ".pa-table tbody tr", "menu quản trị tài khoản")
        ctx.close()

        # ===== sao lưu (cửa sổ) =====
        sao_luu_console()

        # ===== thông báo khóa tạm, 403 =====
        ctx, page = new_page(browser, (1366, 768))
        # khóa tạm: nhập sai 5 lần một tài khoản mới (viewer)
        page.goto(f"{BASE}/dang-nhap/")
        for _ in range(5):
            page.fill("input[name=username]", "viewer")
            page.fill("input[name=password]", "sai-mat-khau-xxxx")
            page.click("button[type=submit]")
            page.wait_for_load_state("networkidle")
        cap(page, "thong-bao-khoa-tam", ".alert", "thông báo khóa tạm 15 phút")
        # mở khóa viewer để không ảnh hưởng bước sau (không qua giao diện cho chắc chắn)
        pw.db(
            "from apps.accounts.models import User; "
            "User.objects.filter(username='viewer').update(locked_until=None, failed_login_count=0)"
        )
        # 403: viewer truy cập trang chỉ admin
        login(page, "viewer")
        page.goto(f"{BASE}/tai-khoan/")  # viewer không có quyền
        cap(page, "403-khong-quyen", "a:has-text('Về trang tổng quan')", "trang 403 (không quyền)")
        ctx.close()
        browser.close()

    print(f"\nTổng: {len(ok)} ảnh thành công, {len(fail)} lỗi -> {OUT}")
    if fail:
        print("Lỗi:", fail)


if __name__ == "__main__":
    main()
