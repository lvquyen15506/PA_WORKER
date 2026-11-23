"""Nghiệm thu kịch bản 17 (yeu-cau.md mục X): sao lưu, xóa container và volume, dựng lại, phục hồi
-> dữ liệu và tệp trở lại đầy đủ, giải mã được. Chạy bằng chính các tệp .bat giao cho khách, trên
compose KHÔNG có tệp dev, bản Demo (DEMO_MODE=1).
    py -3.12 scripts/nghiem_thu_sao_luu.py
Cần: web đang chạy ở http://localhost:8000 (bản cài từ docker-compose.yml), 4 tài khoản admin,
quanly, hr, viewer dùng chung mật khẩu PA_TEST_PASSWORD. Ảnh vào docs/screenshots/phase-8/sao-luu/.
Trường hợp âm: file sao lưu bị sửa 1 byte và khóa sai đều bị từ chối, dữ liệu đang có giữ nguyên.
"""

import json
import subprocess
import sys
import time

import pw_phase5 as pw
from playwright.sync_api import sync_playwright
from pw_phase5 import check, compose, db, goto, login, new_page

OUT = pw.ROOT / "docs" / "screenshots" / "phase-8" / "sao-luu"
BACKUPS = pw.ROOT / "backups"
SIZE = pw.SIZES["1366x768"]
OTHER_KEY = "S1NLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0s="  # khóa Fernet hợp lệ nhưng sai

SNAPSHOT = """
import json, hashlib, pathlib
from django.db import connection
from django.conf import settings
cur = connection.cursor()
cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")
tables = [r[0] for r in cur.fetchall() if r[0] != 'django_session']
counts = {}
for t in tables:
    cur.execute('SELECT count(*) FROM "%s"' % t)
    counts[t] = cur.fetchone()[0]
root = pathlib.Path(settings.PRIVATE_MEDIA_ROOT)
files = {}
for p in root.rglob('*'):
    rel = p.relative_to(root).as_posix()
    if p.is_file() and not rel.startswith('.restore'):
        files[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps({'counts': counts, 'files': files}))
"""

PREPARE = """
import json
from apps.accounts.models import User
from apps.documents.models import WorkerDocument
from apps.employment.models import SalaryHistory
from apps.workers import services
from apps.workers.models import IdentityDocument, Worker
hr = User.objects.get(username='hr')
for s in SalaryHistory.objects.select_related('worker').order_by('pk'):
    w = s.worker
    doc = WorkerDocument.objects.filter(worker=w).exclude(stored_file='').order_by('pk').first()
    ident = IdentityDocument.objects.filter(worker=w).first()
    editable = w.verification_status in ('DRAFT', 'NEEDS_INFO', 'VERIFIED')
    if doc and ident and ident.id_number_enc and editable:
        break
new_name = w.full_name.split(' KB17')[0] + ' KB17'
services.update_worker(hr, w, {'full_name': new_name})
w.refresh_from_db()
print(json.dumps({'pk': w.pk, 'code': w.worker_code, 'name': w.full_name, 'doc': doc.pk,
    'id_number': ident.id_number_enc, 'salary_pk': s.pk, 'salary': s.monthly_salary_enc}))
"""

AFTER = """
import json
from apps.employment.models import SalaryHistory
from apps.workers.models import IdentityDocument, Worker
from apps.audit.models import AuditLog, AuditPersonalValue
w = Worker.objects.get(pk=%d)
print(json.dumps({'name': w.full_name,
    'id_number': IdentityDocument.objects.get(worker=w).id_number_enc,
    'salary': SalaryHistory.objects.get(pk=%d).monthly_salary_enc,
    'personal_values': AuditPersonalValue.objects.filter(worker=w).count(),
    'restore_logs': AuditLog.objects.filter(action='RESTORE').count()}))
"""


def run_bat(name, *args):
    started = time.perf_counter()
    proc = subprocess.run(
        ["cmd", "/c", str(pw.ROOT / name), *args, "-NoPause"],
        cwd=pw.ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr, time.perf_counter() - started


def snapshot():
    return json.loads(db(SNAPSHOT))


def newest_backup():
    files = sorted(BACKUPS.glob("pa-worker-2*.pawbk"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.loads(db(PREPARE))
    check("Chuẩn bị: sửa họ tên một hồ sơ có lương và tài liệu", data["name"].endswith("KB17"))
    before = snapshot()
    check(
        "Chuẩn bị: có dữ liệu và tệp",
        before["counts"]["workers_worker"] >= 500 and len(before["files"]) > 1000,
        f"{before['counts']['workers_worker']} hồ sơ, {len(before['files'])} tệp",
    )

    # 1. Sao lưu bằng Sao luu.bat
    code, out, secs = run_bat("Sao luu.bat")
    backup = newest_backup()
    check("Sao luu.bat chạy thành công", code == 0 and "Đã sao lưu" in out, out[-500:])
    check("File sao lưu có ngày giờ trong tên", backup and backup.name.startswith("pa-worker-20"))
    check("Sao lưu nhắc cất khóa riêng", "không chứa khóa" in out)
    print(f"   sao lưu {backup.name}: {backup.stat().st_size / 1e6:.1f} MB, {secs:.0f} giây")

    # 2. Trường hợp âm: file bị sửa một byte -> kiểm tra báo hỏng
    broken = BACKUPS / ("hong-" + backup.name)
    blob = bytearray(backup.read_bytes())
    blob[len(blob) // 2] ^= 0xFF
    broken.write_bytes(bytes(blob))
    run = compose(
        "exec", "-T", "web", "python", "manage.py", "verify_backup", broken.name, check_code=False
    )
    check(
        "File bị sửa 1 byte: bị từ chối", run.returncode != 0 and "hỏng" in run.stdout + run.stderr
    )
    broken.unlink()

    # 3. Trường hợp âm: khóa sai -> phục hồi bị từ chối, dữ liệu đang có giữ nguyên
    reference = snapshot()  # sau khi sao lưu (đã có thêm dòng nhật ký Sao lưu)
    compose("stop", "web", "scheduler")
    run = compose(
        "run", "--rm", "--no-deps", "-e", f"FIELD_ENCRYPTION_KEY={OTHER_KEY}", "web",
        "python", "manage.py", "restore", backup.name, "--yes",
        check_code=False,
    )  # fmt: skip
    check(
        "Khóa sai: phục hồi bị từ chối với thông báo tiếng Việt",
        run.returncode != 0 and "không khớp với file sao lưu" in run.stdout + run.stderr,
    )
    compose("up", "-d")
    wait_web()
    check("Khóa sai: dữ liệu đang có giữ nguyên", snapshot() == reference)

    # 4. Xóa container và volume, dựng lại bản sạch
    compose("down", "-v")
    volumes = subprocess.run(
        ["docker", "volume", "ls", "--format", "{{.Name}}"], capture_output=True, text=True
    ).stdout.split()
    check(
        "docker compose down -v: xóa volume CSDL và tệp",
        not {"pa_worker_pgdata", "pa_worker_media"} & set(volumes),
    )
    compose("up", "-d", "--build")
    wait_web()
    fresh = snapshot()
    check(
        "Dựng lại: bản cài sạch không có hồ sơ, không có tệp",
        fresh["counts"]["workers_worker"] == 0 and not fresh["files"],
    )

    # 5. Phục hồi bằng Phuc hoi.bat
    code, out, secs = run_bat("Phuc hoi.bat", "-File", backup.name, "-Yes")
    check("Phuc hoi.bat chạy thành công", code == 0 and "Đã phục hồi" in out, out[-800:])
    print(f"   phục hồi: {secs:.0f} giây")
    after = snapshot()
    diff = {
        t: (before["counts"].get(t), n)
        for t, n in after["counts"].items()
        if t != "audit_auditlog" and before["counts"].get(t) != n
    }
    check("Số dòng mọi bảng khớp trước khi sao lưu", not diff, str(diff))
    # Nhật ký thêm đúng: BACKUP (ghi sau khi chụp snapshot) không nằm trong bản sao lưu; RESTORE +1.
    check(
        "Nhật ký: thêm đúng 1 dòng Phục hồi",
        after["counts"]["audit_auditlog"] == before["counts"]["audit_auditlog"] + 1,
    )
    check(
        "Mọi tệp khớp sha256",
        after["files"] == before["files"],
        f"{len(after['files'])}/{len(before['files'])}",
    )
    restored = json.loads(db(AFTER % (data["pk"], data["salary_pk"])))
    check("Giải mã được số CCCD sau phục hồi", restored["id_number"] == data["id_number"])
    check("Giải mã được lương sau phục hồi", restored["salary"] == data["salary"])
    check("Họ tên đã sửa trước khi sao lưu còn nguyên", restored["name"] == data["name"])
    check("Giá trị trước/sau trong nhật ký còn nguyên", restored["personal_values"] > 0)
    keys = compose("exec", "-T", "web", "python", "manage.py", "check_keys", check_code=False)
    check("check_keys: khóa khớp dữ liệu phục hồi", keys.returncode == 0 and "khớp" in keys.stdout)

    # 6. Trên giao diện: đăng nhập, mở hồ sơ, hiện số đầy đủ, xem tài liệu
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx, page = new_page(browser, SIZE)
        login(page, "hr")
        goto(page, f"/ho-so/{data['pk']}/")
        check("Giao diện: hồ sơ hiện họ tên đã sửa", data["name"] in page.content())
        page.click("button:has-text('Hiện số đầy đủ')")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        check("Giao diện: Hiện số đầy đủ đúng số CCCD", data["id_number"] in page.content())
        pw.shot(OUT, page, "1366x768", "01-ho-so-sau-phuc-hoi")
        status = goto(page, f"/ho-so/{data['pk']}/?tab=lam-viec")
        check("Giao diện: tab Quá trình làm việc mở được", status == 200)
        pw.shot(OUT, page, "1366x768", "02-lam-viec-sau-phuc-hoi")
        response = page.goto(f"{pw.BASE}/tai-lieu/{data['doc']}/xem/")
        check("Giao diện: xem được tài liệu sau phục hồi", response and response.status == 200)
        ctx.close()
        ctx, page = new_page(browser, SIZE)
        login(page, "admin")
        goto(page, "/nhat-ky/?hanh_dong=RESTORE")
        check("Nhật ký thao tác có dòng Phục hồi", "Phục hồi" in page.content())
        pw.shot(OUT, page, "1366x768", "03-nhat-ky-phuc-hoi")
        ctx.close()
        browser.close()
    return pw.finish()


def wait_web(timeout=600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = compose("ps", "--format", "{{.Service}} {{.Status}}", check_code=False)
        if any(line.startswith("web ") and "(healthy)" in line for line in run.stdout.splitlines()):
            return
        time.sleep(5)
    raise RuntimeError("web không sẵn sàng")


if __name__ == "__main__":
    sys.exit(main())
