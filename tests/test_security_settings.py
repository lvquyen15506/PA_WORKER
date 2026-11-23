"""Cấu hình bảo mật khi chạy thật (docs/ra-soat-bao-mat.md mục 6, 7, 10, 11)."""

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client, RequestFactory
from django.views import defaults

from apps.core.log_format import MASK, RedactingFormatter
from tests.factories import login_client as login
from tests.factories import make_user

ROOT = Path(__file__).resolve().parent.parent


# --- Mục 7: trang lỗi tiếng Việt, không lộ thông tin gỡ lỗi ---------------------------------
@pytest.mark.django_db
def test_trang_404_tieng_viet():
    response = Client().get("/khong-co-trang-nay/")
    body = response.content.decode()
    assert response.status_code == 404
    assert "Không tìm thấy trang" in body and f"v{settings.APP_VERSION}" in body
    assert "Not Found" not in body and "Traceback" not in body


@pytest.mark.django_db
def test_trang_404_khi_da_dang_nhap():
    body = login(make_user("HR_STAFF")).get("/ho-so/999999999/").content.decode()
    assert "Không tìm thấy trang" in body


def test_trang_500_tieng_viet_khong_can_context():
    response = defaults.server_error(RequestFactory().get("/"))
    body = response.content.decode()
    assert response.status_code == 500
    assert "Hệ thống gặp lỗi" in body and f"v{settings.APP_VERSION}" in body
    assert "Server Error" not in body


def test_trang_400_khi_sai_host_huong_dan_allowed_hosts():
    response = Client().get("/dang-nhap/", HTTP_HOST="may-la.example")
    body = response.content.decode()
    assert response.status_code == 400
    assert "Yêu cầu không hợp lệ" in body and "ALLOWED_HOSTS" in body


# --- Mục 11: giới hạn kích thước request ------------------------------------------------------
@pytest.mark.django_db
def test_request_qua_lon_bi_tu_choi_413():
    client = login(make_user("HR_STAFF"))
    response = client.post(
        "/nhap-cccd/",
        data=b"x",
        content_type="application/octet-stream",
        CONTENT_LENGTH=str(settings.MAX_REQUEST_BYTES + 1),
    )
    assert response.status_code == 413
    assert "Tệp quá lớn" in response.content.decode()


@pytest.mark.django_db
def test_request_vua_gioi_han_khong_bi_chan():
    client = login(make_user("HR_STAFF"))
    response = client.post(
        "/nhap-cccd/",
        data=b"x",
        content_type="application/octet-stream",
        CONTENT_LENGTH="1",
    )
    assert response.status_code != 413


def test_gioi_han_request_du_cho_ba_tep_10mb():
    assert settings.MAX_REQUEST_BYTES > 3 * settings.MAX_UPLOAD_BYTES


# --- Mục 6: log ra stdout, che dãy số dài ------------------------------------------------------
def test_dinh_dang_log_che_so_cccd_va_sdt():
    formatter = RedactingFormatter("%(message)s")
    record = logging.LogRecord(
        "apps.x",
        logging.ERROR,
        __file__,
        1,
        "Trùng %s, SĐT %s, pk=%s",
        ("999123456789", "0912345678", 42),
        None,
    )
    out = formatter.format(record)
    assert "999123456789" not in out and "0912345678" not in out
    assert out.count(MASK) == 2 and "pk=42" in out


def test_dinh_dang_log_che_ca_traceback():
    formatter = RedactingFormatter("%(message)s")
    try:
        raise ValueError("Key (id_number_hash)=(999000111222) already exists")
    except ValueError:
        record = logging.LogRecord(
            "django.request", logging.ERROR, __file__, 1, "Lỗi", (), sys.exc_info()
        )
    assert "999000111222" not in formatter.format(record)


def test_loi_500_duoc_ghi_ra_console():
    handlers = logging.getLogger("django.request").handlers or logging.getLogger("django").handlers
    assert any(isinstance(h.formatter, RedactingFormatter) for h in handlers)
    assert logging.getLogger("django").getEffectiveLevel() <= logging.ERROR
    assert logging.getLogger("apps").getEffectiveLevel() <= logging.INFO


def test_gunicorn_khong_bat_access_log():
    for name in ("Dockerfile", "docker-compose.yml", "docker-compose.dev.yml"):
        assert "access-log" not in (ROOT / name).read_text(encoding="utf-8")


# --- Mục 10: HTTPS tùy chọn ------------------------------------------------------------------
def _check_deploy(https):
    env = {**os.environ, "DEBUG": "0", "HTTPS": https}
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.stdout + result.stderr


def test_check_deploy_https_tat_chi_con_canh_bao_https():
    out = _check_deploy("0")
    found = {code for code in ("W004", "W008", "W012", "W016") if f"security.{code}" in out}
    assert found == {"W004", "W008", "W012", "W016"}
    assert "identified 4 issues" in out


def test_check_deploy_https_bat_khong_con_canh_bao():
    out = _check_deploy("1")
    assert "no issues" in out, out


def test_cookie_va_header_mac_dinh():
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"
    assert settings.X_FRAME_OPTIONS == "DENY"
    assert settings.SECURE_REFERRER_POLICY == "same-origin"
    assert "*" not in settings.ALLOWED_HOSTS


# --- Mục 12: CSP cho mọi trang, không có script/style nội tuyến -----------------------------
@pytest.mark.django_db
def test_moi_trang_co_csp_khong_cho_script_noi_tuyen():
    from apps.core.middleware import CONTENT_SECURITY_POLICY

    for response in (
        Client().get("/dang-nhap/"),
        login(make_user("HR_STAFF")).get("/"),
        Client().get("/khong-co-trang-nay/"),
    ):
        csp = response["Content-Security-Policy"]
        assert csp == CONTENT_SECURITY_POLICY
        assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
        assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp


@pytest.mark.django_db
def test_xem_tai_lieu_giu_csp_sandbox():
    from tests.factories import make_document, make_worker

    hr = make_user("HR_STAFF")
    doc = make_document(make_worker(created_by=hr))
    response = login(hr).get(f"/tai-lieu/{doc.pk}/xem/")
    assert response.status_code == 200
    assert response["Content-Security-Policy"] == "sandbox"


def test_template_khong_co_script_va_su_kien_noi_tuyen():
    import re

    script_inline = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>", re.I)
    handler = re.compile(r"\son[a-z]+\s*=", re.I)
    found = []
    for path in (ROOT / "templates").rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        for pattern in (script_inline, handler):
            for m in pattern.finditer(text):
                # json_script sinh thẻ <script type="application/json"> (dữ liệu, không chạy)
                if "application/json" in m.group(0):
                    continue
                found.append(f"{path.relative_to(ROOT)}: {m.group(0)}")
        if "javascript:" in text:
            found.append(f"{path.relative_to(ROOT)}: javascript:")
    assert found == []


def test_htmx_tat_style_tu_chen_va_eval():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert '"includeIndicatorStyles": false' in base and '"allowEval": false' in base
