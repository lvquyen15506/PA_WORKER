"""Nghiệm thu tổng Phase 8: đủ 17 kịch bản (yeu-cau.md mục X) và kịch bản v1.1 trên BẢN CÀI SẠCH
(docker-compose.yml, không có tệp dev), cài theo hướng dẫn bằng PA Worker.bat (bản Demo), cộng kiểm
thử giao diện Phase 3–8 và thử riêng bản Thật. Gọi lại các script nghiệm thu đã có (không viết lại).
    py -3.12 scripts/nghiem_thu_tong.py [--giu-cache]
--giu-cache: không xóa image gốc và bộ nhớ đệm build (chạy lại nhanh; KHÔNG dùng để đo kịch bản 1).

Các bước:
1. "Máy mới": docker compose down -v; xóa image dự án, image gốc, bộ nhớ đệm build; chuyển .env và
   thư mục backups cũ sang thư mục tạm (máy mới không có). Bấm giờ PA Worker.bat -Mode demo.
2. Kịch bản 1, 15: scripts/nghiem_thu_1_15_phase3.py với mật khẩu tạm đọc từ màn hình cài đặt
   (chỉ truyền qua biến môi trường cho tiến trình con, không in, không ghi tệp).
3. Kịch bản 2, 5, 6, 7, 14 (phase4); 3, 4, 5 (phase5); 8, 9, 10, v1.1 (phase6); 10, 11, 12, 13, 16
   (phase7); 17 (nghiem_thu_sao_luu).
4. Kiểm thử giao diện Phase 3–8 (hồi quy sau khi đổi người dùng chạy container, CSP, settings).
5. Bản Thật trong thư mục riêng (tên dự án pa_ban_that, cổng 8002): Admin đầu tiên, buộc đổi mật
   khẩu, seed_demo bị chặn, trang 404 tiếng Việt, truy cập bằng IP LAN.
Kết quả: docs/screenshots/phase-8/nghiem-thu/ket-qua.json và nhật ký từng script trong logs/.
"""

import datetime
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots" / "phase-8" / "nghiem-thu"
LOGS = OUT / "logs"
PY = sys.executable
PASSWORD_LINE = re.compile(r"^\s+(admin|quanly|hr|viewer)\s+(\S+)\s*$")
TEMP_PASSWORD = re.compile(r"Mật khẩu tạm \(chỉ hiện một lần\): (\S+)")

SCRIPTS = [
    ("kb-2-5-6-7-14", "nghiem_thu_phase4.py", "Kịch bản 2, 5, 6, 7, 14"),
    ("kb-3-4-5", "nghiem_thu_phase5.py", "Kịch bản 3, 4, 5"),
    ("kb-8-9-10-v11", "nghiem_thu_phase6.py", "Kịch bản 8, 9, 10 và kịch bản v1.1"),
    ("kb-10-11-12-13-16", "nghiem_thu_phase7.py", "Kịch bản 10, 11, 12, 13, 16"),
    ("kb-17", "nghiem_thu_sao_luu.py", "Kịch bản 17"),
]
UI_SCRIPTS = [f"kiem_thu_giao_dien_phase{n}.py" for n in (3, 4, 5, 6, 7, 8)]

report = {"ngay": datetime.date.today().strftime("%d/%m/%Y"), "buoc": []}


def say(text):
    print(text, flush=True)


def run(cmd, *, env=None, cwd=ROOT, log_name=None, redact=False):
    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    secs = time.perf_counter() - started
    out = proc.stdout + proc.stderr
    if log_name:
        text = out
        if redact:  # không ghi mật khẩu tạm ra tệp
            text = "\n".join(
                "  (mật khẩu tạm đã che)" if PASSWORD_LINE.match(line) else line
                for line in text.splitlines()
            )
            text = TEMP_PASSWORD.sub("Mật khẩu tạm (chỉ hiện một lần): ********", text)
        LOGS.mkdir(parents=True, exist_ok=True)
        (LOGS / f"{log_name}.txt").write_text(text, encoding="utf-8")
    return proc.returncode, out, secs


def counts(out):
    """(đạt, tổng) từ dòng kết luận của script nghiệm thu."""
    m = re.search(r"Tổng: (\d+) bước, đạt (\d+)", out)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.search(r"(\d+)/(\d+) bước đạt", out)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def record(key, title, code, out, secs, **extra):
    ok, total = counts(out)
    item = {
        "ma": key,
        "ten": title,
        "dat": code == 0,
        "so_buoc_dat": ok,
        "tong_buoc": total,
        "giay": round(secs),
        **extra,
    }
    failed = [line for line in out.splitlines() if line.startswith("LỖI")]
    if failed:
        item["loi"] = failed[:10]
    report["buoc"].append(item)
    say(f"{'ĐẠT ' if code == 0 else 'LỖI '} {title}: {ok}/{total} bước, {secs:.0f} giây")
    for line in failed[:10]:
        say("     " + line)


def compose(*args, cwd=ROOT, env=None):
    return run(["docker", "compose", *args], cwd=cwd, env=env)


def set_test_password(password, cwd=ROOT, env=None):
    code = (
        "import os;from apps.accounts.models import User;"
        "[ (u.set_password(os.environ['PW']), setattr(u,'must_change_password',False), "
        "setattr(u,'failed_login_count',0), setattr(u,'locked_until',None), "
        "setattr(u,'is_active',True), u.save()) "
        "for u in User.objects.filter(username__in=['admin','quanly','hr','viewer'])]"
    )
    compose("exec", "-T", "-e", "PW", "web", "python", "manage.py", "shell", "-c", code,
            cwd=cwd, env={**(env or {}), "PW": password})  # fmt: skip


# ----- 1. Máy mới + cài bản Demo bằng PA Worker.bat -------------------------------------------
def fresh_install(keep_cache):
    say("== 1. Cài sạch theo hướng dẫn (PA Worker.bat, bản Demo)")
    stash = Path(tempfile.mkdtemp(prefix="pa-truoc-nghiem-thu-"))
    for name in (".env", "backups"):
        if (ROOT / name).exists():
            shutil.move(str(ROOT / name), str(stash / name))
    say(f"   đã chuyển .env và backups cũ sang {stash}")
    compose("down", "-v", "--remove-orphans")
    images = ["pa_worker-web", "pa_worker-db"]
    if not keep_cache:  # image gốc được kéo theo digest (Dockerfile, docker/db.Dockerfile)
        images += [
            "python:3.12-slim",
            "postgres:16",
            "python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b",
            "postgres@sha256:3950ad7c3148ca2175ef1b6c36c9efbf78957ae8fbe8b3a5d7c35af50500382f",
        ]
    for image in images:
        run(["docker", "image", "rm", "-f", image])
    if not keep_cache:
        run(["docker", "builder", "prune", "-af"])
    code, out, secs = run(
        ["cmd", "/c", str(ROOT / "PA Worker.bat"), "-Mode", "demo", "-AddLanIp",
         "-NoBrowser", "-NoPause"],
        log_name="01-cai-dat-pa-worker-bat",
        redact=True,
    )  # fmt: skip
    passwords = {}
    for line in out.splitlines():
        m = PASSWORD_LINE.match(line)
        if m:
            passwords[m.group(1)] = m.group(2)
    ok = code == 0 and len(passwords) == 4 and "Đã tạo 500 hồ sơ mẫu mới" in out
    report["buoc"].append(
        {
            "ma": "cai-dat",
            "ten": "Kịch bản 1 (phần cài đặt): máy mới chỉ có Docker Desktop, "
            "PA Worker.bat bản Demo",
            "dat": ok and secs < 30 * 60,
            "giay": round(secs),
            "khong_cache": not keep_cache,
            "so_tai_khoan_mau": len(passwords),
        }
    )
    say(f"{'ĐẠT ' if ok else 'LỖI '} Cài đặt: {secs / 60:.1f} phút, {len(passwords)} tài khoản mẫu")
    return passwords


# ----- 5. Bản Thật ------------------------------------------------------------------------------
def production_install(test_password):
    say("== 5. Bản Thật (thư mục riêng, tên dự án pa_ban_that, cổng 8002)")
    folder = Path(tempfile.mkdtemp(prefix="pa-ban-that-")) / "PA Worker that"
    archive = folder.parent / "ban.zip"
    run(["git", "archive", "--format=zip", "-o", str(archive), "HEAD"])
    shutil.unpack_archive(archive, folder)
    env = {"COMPOSE_PROJECT_NAME": "pa_ban_that", "PA_PORT": "8002"}
    code, out, secs = run(
        ["cmd", "/c", str(folder / "PA Worker.bat"), "-Mode", "that", "-AdminUser", "quantri",
         "-AddLanIp", "-NoBrowser", "-NoPause"],
        env=env, log_name="05-ban-that-pa-worker-bat", redact=True,
    )  # fmt: skip
    m = TEMP_PASSWORD.search(out)
    checks = {"PA Worker.bat bản Thật chạy xong, tạo Admin quantri": code == 0 and bool(m)}
    _c, seed, _s = compose(
        "exec", "-T", "web", "python", "manage.py", "seed_demo", cwd=folder, env=env
    )
    checks["seed_demo bị chặn ở bản Thật"] = "bản cài Thật" in seed
    _c, users, _s = compose(
        "exec", "-T", "web", "python", "manage.py", "shell", "-c",
        "from apps.accounts.models import User;"
        "print(list(User.objects.values_list('username','role__code','must_change_password')))",
        cwd=folder, env=env,
    )  # fmt: skip
    checks["chỉ có 1 tài khoản Admin, buộc đổi mật khẩu"] = "[('quantri', 'ADMIN', True)]" in users
    _c, demo_flag, _s = compose(
        "exec", "-T", "web", "printenv", "DEMO_MODE", "DEBUG", cwd=folder, env=env
    )
    checks["DEMO_MODE=0, DEBUG=0"] = demo_flag.split() == ["0", "0"]
    if m:
        checks.update(production_browser(m.group(1), test_password))
    compose("down", "-v", cwd=folder, env=env)
    shutil.rmtree(folder.parent, ignore_errors=True)
    for name, ok in checks.items():
        say(f"   {'ĐẠT' if ok else 'LỖI'}  {name}")
    report["buoc"].append(
        {
            "ma": "ban-that",
            "ten": "Bản Thật: Admin đầu tiên, buộc đổi mật khẩu, seed_demo bị chặn, "
            "404 tiếng Việt, IP LAN",
            "dat": code == 0 and all(checks.values()),
            "so_buoc_dat": sum(checks.values()),
            "tong_buoc": len(checks),
            "giay": round(secs),
            "chi_tiet": checks,
        }
    )


def production_browser(temp_password, new_password):
    from playwright.sync_api import sync_playwright

    base = "http://localhost:8002"
    checks = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1366, "height": 768})
        page.goto(f"{base}/dang-nhap/")
        page.fill("input[name=username]", "quantri")
        page.fill("input[name=password]", temp_password)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        checks["đăng nhập lần đầu bị chuyển tới Đổi mật khẩu"] = page.url.endswith("/doi-mat-khau/")
        page.fill("input[name=old_password]", temp_password)
        page.fill("input[name=new_password1]", new_password)
        page.fill("input[name=new_password2]", new_password)
        page.click("main button[type=submit]")
        page.wait_for_load_state("networkidle")
        checks["đổi mật khẩu xong vào Tổng quan, menu Admin 9 mục"] = (
            page.locator(".pa-nav li").count() == 9
        )
        page.screenshot(path=str(OUT / "ban-that-tong-quan.png"), full_page=True)
        response = page.goto(f"{base}/khong-co-trang-nay/")
        checks["trang 404 tiếng Việt (DEBUG=0)"] = (
            response.status == 404 and "Không tìm thấy trang" in page.content()
        )
        browser.close()
    ip = lan_ip()
    if ip:
        try:
            with urllib.request.urlopen(f"http://{ip}:8002/dang-nhap/", timeout=10) as r:
                checks[f"máy khác truy cập bằng IP LAN {ip}"] = r.status == 200
        except urllib.error.URLError:
            checks[f"máy khác truy cập bằng IP LAN {ip}"] = False
    return checks


def lan_ip():
    out = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
         f". '{ROOT / 'scripts' / 'windows' / 'common.ps1'}'; Get-LanIP"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.strip().splitlines()  # fmt: skip
    return out[-1].strip() if out else ""


def main():
    keep_cache = "--giu-cache" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    test_password = "Nt" + secrets.token_urlsafe(10).replace("-", "a").replace("_", "b") + "8"
    started = time.perf_counter()

    passwords = fresh_install(keep_cache)
    if len(passwords) != 4:
        say("Cài đặt không thành công; dừng nghiệm thu.")
        return finish(started)

    say("== 2. Kịch bản 1, 15")
    env = {f"PA_PW_{u.upper()}": pw for u, pw in passwords.items()}
    env["PA_NEW_PASSWORD"] = test_password
    code, out, secs = run([PY, "scripts/nghiem_thu_1_15_phase3.py"], env=env, log_name="kb-1-15")
    record("kb-1-15", "Kịch bản 1, 15", code, out, secs)
    set_test_password(test_password)  # các script sau dùng chung một mật khẩu

    say("== 3. Kịch bản 2–17 và v1.1")
    env = {"PA_TEST_PASSWORD": test_password}
    for key, script, title in SCRIPTS:
        code, out, secs = run([PY, f"scripts/{script}"], env=env, log_name=key)
        record(key, title, code, out, secs)
        set_test_password(test_password)

    say("== 4. Kiểm thử giao diện Phase 3–8")
    for script in UI_SCRIPTS:
        key = script.replace(".py", "")
        code, out, secs = run([PY, f"scripts/{script}"], env=env, log_name=key)
        record(key, f"Kiểm thử giao diện {key[-6:].replace('phase', 'Phase ')}", code, out, secs)
        set_test_password(test_password)

    production_install(test_password)
    return finish(started)


def finish(started):
    report["tong_giay"] = round(time.perf_counter() - started)
    report["dat_het"] = all(item["dat"] for item in report["buoc"])
    (OUT / "ket-qua.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    say(f"\nKết quả: {'ĐẠT HẾT' if report['dat_het'] else 'CÒN LỖI'} – {OUT / 'ket-qua.json'}")
    return 0 if report["dat_het"] else 1


if __name__ == "__main__":
    sys.exit(main())
