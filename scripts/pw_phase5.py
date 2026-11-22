"""Hàm dùng chung cho hai script kiểm thử giao diện Phase 5 (Playwright, Python 3.12 64-bit).

Cần web ở http://localhost:8000 và 4 tài khoản admin, quanly, hr, viewer dùng chung một mật khẩu
trong biến môi trường PA_TEST_PASSWORD. Ảnh CCCD giả sinh mới mỗi lần chạy bằng lệnh
`manage.py make_fake_cccd --offset N` (số CCCD giả luôn bắt đầu 999, không trùng lần chạy trước).
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = os.environ.get("PA_BASE_URL", "http://localhost:8000")
PASSWORD = os.environ["PA_TEST_PASSWORD"]
SIZES = {"1366x768": (1366, 768), "390x844": (390, 844)}
CARD_DIR = ROOT / "scripts" / "_the_gia"
EXPECTED_NOISE = ("status of 403", "status of 404", "status of 405")

results, console_errors = [], []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("ĐẠT  " if ok else "LỖI  ") + name + (f" – {detail}" if detail and not ok else ""))


def new_page(browser, size):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, locale="vi-VN")
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


def shot(out, page, size_name, name, modal=False):
    out.mkdir(parents=True, exist_ok=True)
    if modal:
        page.wait_for_timeout(600)
    page.screenshot(path=str(out / f"{name}-{size_name}.png"), full_page=not modal)


def no_h_scroll(page):
    return page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )


def compose(*args, check_code=True):
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=check_code,
    )


def gen_cards(offset=None):
    """Sinh bộ thẻ giả mới (số CCCD không trùng lần trước) rồi chép ra scripts/_the_gia/.
    Trả danh sách thẻ trong truth.json."""
    offset = offset if offset is not None else (int(time.time()) % 800_000_000) + 1000
    if CARD_DIR.exists():
        shutil.rmtree(CARD_DIR)
    compose(
        "exec", "-T", "web", "python", "manage.py", "make_fake_cccd",
        "--out", "/tmp/the_gia", "--cv", "/tmp/the_gia/cv", "--offset", str(offset),
    )  # fmt: skip
    CARD_DIR.mkdir(parents=True)
    compose("cp", "web:/tmp/the_gia/.", str(CARD_DIR))
    return json.loads((CARD_DIR / "truth.json").read_text(encoding="utf-8"))["cards"]


def db(code):
    """Chạy đoạn Python trong manage.py shell của container web, trả stdout (đã cắt trắng)."""
    run = compose("exec", "-T", "web", "python", "manage.py", "shell", "-c", code)
    lines = [line for line in run.stdout.splitlines() if line.strip()]
    return lines[-1].strip() if lines else ""  # bỏ dòng "N objects imported automatically"


def count_by_id(id_number):
    code = (
        "from apps.core.crypto import compute_id_hash;"
        "from apps.workers.models import IdentityDocument;"
        f"print(IdentityDocument.objects.filter(id_number_hash=compute_id_hash('{id_number}')).count())"
    )
    return int(db(code))


def count_sessions():
    return int(
        db("from apps.intake.models import IntakeSession;print(IntakeSession.objects.count())")
    )


def audit_count(action):
    code = (
        "from apps.audit.models import AuditLog;"
        f"print(AuditLog.objects.filter(action='{action}').count())"
    )
    return int(db(code))


def finish():
    real = [(u, m) for u, m in console_errors if not any(n in m for n in EXPECTED_NOISE)]
    check("Không có lỗi console ngoài 403/404 mong đợi", not real, str(real[:5]))
    failed = [r for r in results if not r[1]]
    print(f"\nTổng: {len(results)} bước, đạt {len(results) - len(failed)}, lỗi {len(failed)}")
    return 1 if failed else 0
