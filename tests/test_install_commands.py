"""Bản cài cho khách (Phase 8 bước 3, docs/lam-ro-yeu-cau.md câu 49): seed_demo chỉ chạy ở bản
Demo, tạo Admin đầu tiên, đặt lại mật khẩu Admin khi quên, make_env.py."""

import importlib.util
import io
from pathlib import Path

import pytest
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.core.choices import AuditAction
from apps.workers.models import Worker
from tests.factories import login_client, make_user

ROOT = Path(__file__).resolve().parent.parent


def run(name, *args):
    out = io.StringIO()
    call_command(name, *args, stdout=out)
    return out.getvalue()


# --- seed_demo chỉ chạy ở bản Demo --------------------------------------------------------------
@pytest.mark.django_db
def test_seed_demo_bi_chan_o_ban_that(settings):
    settings.DEMO_MODE = False
    with pytest.raises(CommandError, match="bản cài Thật"):
        run("seed_demo", "--count", "3")
    assert not User.objects.filter(username__in=["admin", "quanly", "hr", "viewer"]).exists()
    assert Worker.objects.count() == 0


@pytest.mark.django_db
def test_seed_demo_chay_o_ban_demo(settings):
    settings.DEMO_MODE = True
    run("seed_demo", "--count", "3")
    assert User.objects.filter(username="admin").exists()


def test_settings_doc_demo_mode_tu_env():
    text = (ROOT / "config" / "settings.py").read_text(encoding="utf-8")
    assert 'DEMO_MODE = _env("DEMO_MODE", "0") == "1"' in text  # mặc định là bản Thật


# --- create_first_admin -----------------------------------------------------------------------
@pytest.mark.django_db
def test_tao_admin_dau_tien():
    out = run("create_first_admin")
    user = User.objects.get(username="admin")
    assert user.role.code == "ADMIN" and user.must_change_password and user.is_active
    assert "Mật khẩu tạm (chỉ hiện một lần):" in out
    temp = out.split("Mật khẩu tạm (chỉ hiện một lần): ")[1].split()[0]
    assert user.check_password(temp)
    entry = AuditLog.objects.get(action=AuditAction.CREATE, object_id=str(user.pk))
    assert entry.user is None  # Hệ thống


@pytest.mark.django_db
def test_tao_admin_dau_tien_ten_tuy_chon():
    run("create_first_admin", "--username", "quantri", "--full-name", "Người quản trị")
    assert User.objects.get(username="quantri").full_name == "Người quản trị"


@pytest.mark.django_db
def test_tao_admin_dau_tien_bi_chan_khi_da_co_admin():
    make_user("ADMIN", username="admin_cu")
    with pytest.raises(CommandError, match="đã có tài khoản Admin"):
        run("create_first_admin", "--username", "admin2")
    assert not User.objects.filter(username="admin2").exists()


@pytest.mark.django_db
def test_tao_admin_dau_tien_khi_chi_co_admin_bi_khoa_van_duoc():
    make_user("ADMIN", username="admin_cu", is_active=False)
    run("create_first_admin", "--username", "admin_moi")
    assert User.objects.filter(username="admin_moi", role__code="ADMIN").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("username", ["co dau cach", "ab", "x" * 31])
def test_tao_admin_dau_tien_ten_sai(username):
    with pytest.raises(CommandError):
        run("create_first_admin", "--username", username)
    assert not User.objects.exists()


# --- reset_admin_password ---------------------------------------------------------------------
@pytest.mark.django_db
def test_dat_lai_mat_khau_admin_duy_nhat_mo_khoa_va_huy_phien():
    admin = make_user("ADMIN", username="admin")
    login_client(admin)  # có phiên đăng nhập
    User.objects.filter(pk=admin.pk).update(is_active=False, failed_login_count=5)
    out = run("reset_admin_password")
    admin.refresh_from_db()
    temp = out.split("Mật khẩu tạm (chỉ hiện một lần): ")[1].split()[0]
    assert admin.check_password(temp) and admin.must_change_password
    assert admin.is_active and admin.failed_login_count == 0 and admin.locked_until is None
    assert not any(
        s.get_decoded().get("_auth_user_id") == str(admin.pk) for s in Session.objects.all()
    )
    actions = set(
        AuditLog.objects.filter(object_id=str(admin.pk), user=None).values_list("action", flat=True)
    )
    assert {AuditAction.PASSWORD_RESET, AuditAction.ACCOUNT_UNLOCK} <= actions


@pytest.mark.django_db
def test_dat_lai_mat_khau_nhieu_admin_phai_ghi_ten():
    make_user("ADMIN", username="admin1")
    make_user("ADMIN", username="admin2")
    with pytest.raises(CommandError, match="admin1, admin2"):
        run("reset_admin_password")
    out = run("reset_admin_password", "admin2")
    assert "admin2" in out


@pytest.mark.django_db
def test_dat_lai_mat_khau_khong_dung_cho_tai_khoan_thuong():
    make_user("ADMIN", username="admin")
    hr = make_user("HR_STAFF", username="hr1")
    with pytest.raises(CommandError, match="chỉ dùng cho Admin"):
        run("reset_admin_password", "hr1")
    hr.refresh_from_db()
    assert not hr.must_change_password


@pytest.mark.django_db
def test_dat_lai_mat_khau_khi_chua_co_admin():
    with pytest.raises(CommandError, match="create_first_admin"):
        run("reset_admin_password")


# --- make_env.py ------------------------------------------------------------------------------
@pytest.fixture
def make_env(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("make_env", ROOT / "scripts" / "make_env.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ENV_PATH", tmp_path / ".env")
    return module


def env_dict(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))


@pytest.mark.parametrize(("mode", "flag"), [("demo", "1"), ("that", "0")])
def test_make_env_tao_env_theo_che_do(make_env, mode, flag):
    assert make_env.main(["--mode", mode]) == 0
    values = env_dict(make_env.ENV_PATH)
    assert values["DEMO_MODE"] == flag and values["DEBUG"] == "0"
    for key in ("SECRET_KEY", "POSTGRES_PASSWORD", "FIELD_ENCRYPTION_KEY", "HASH_KEY"):
        assert len(values[key]) >= 32


def test_make_env_khong_ghi_de_va_khong_in_khoa(make_env, capsys):
    make_env.main(["--mode", "that"])
    before = make_env.ENV_PATH.read_bytes()
    capsys.readouterr()
    make_env.main(["--mode", "demo"])
    assert make_env.ENV_PATH.read_bytes() == before
    out = capsys.readouterr().out
    for value in env_dict(make_env.ENV_PATH).values():
        if len(value) >= 32:
            assert value not in out


def test_make_env_them_ip_chi_doi_dong_allowed_hosts(make_env):
    make_env.main(["--mode", "that"])
    before = make_env.ENV_PATH.read_text(encoding="utf-8").splitlines()
    assert make_env.main(["--allowed-hosts", "192.168.1.20"]) == 0
    make_env.main(["--allowed-hosts", "192.168.1.20,may-chu"])  # thêm lần nữa không lặp
    after = make_env.ENV_PATH.read_text(encoding="utf-8").splitlines()
    changed = [(a, b) for a, b in zip(before, after, strict=True) if a != b]
    assert changed == [
        (
            "ALLOWED_HOSTS=localhost,127.0.0.1",
            "ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.20,may-chu",
        )
    ]
    assert not (make_env.ENV_PATH.parent / ".env.tmp").exists()


@pytest.mark.parametrize("host", ["*", "192.168.1.20 ; rm", "a/b"])
def test_make_env_tu_choi_host_sai(make_env, host):
    make_env.main(["--mode", "that"])
    before = make_env.ENV_PATH.read_bytes()
    assert make_env.main(["--allowed-hosts", host]) == 1
    assert make_env.ENV_PATH.read_bytes() == before


def test_make_env_sua_ip_khi_chua_co_env(make_env):
    assert make_env.main(["--allowed-hosts", "192.168.1.20"]) == 1
    assert not make_env.ENV_PATH.exists()
