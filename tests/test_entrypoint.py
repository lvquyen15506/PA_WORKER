"""Entrypoint và lệnh khởi động không được tự chạy dữ liệu mẫu.

Lệnh nạp dữ liệu mẫu in mật khẩu tạm ra console; nếu chạy lúc khởi động container thì
mật khẩu sẽ nằm trong `docker compose logs`. Chỉ chạy tay bằng
`docker compose exec web python manage.py seed_demo`.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _lenh(path):
    """Các dòng không phải chú thích."""
    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_entrypoint_khong_chua_seed_demo():
    assert "seed_demo" not in (ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")


def test_dockerfile_va_compose_khong_goi_seed_demo():
    for name in ("Dockerfile", "docker-compose.yml", "docker-compose.dev.yml"):
        assert "seed_demo" not in (ROOT / name).read_text(encoding="utf-8"), name


def test_entrypoint_kiem_tra_khoa_truoc_migrate():
    lenh = _lenh(ROOT / "docker" / "entrypoint.sh")
    thu_tu = [i for i, line in enumerate(lenh) if "check_keys --format" in line]
    migrate = [i for i, line in enumerate(lenh) if "manage.py migrate" in line]
    assert thu_tu and migrate and thu_tu[0] < migrate[0]
