"""Entrypoint và lệnh khởi động không được tự chạy seed_demo.

seed_demo in mật khẩu tạm ra console; nếu chạy lúc khởi động container thì mật khẩu
sẽ nằm trong `docker compose logs`. Chỉ chạy tay bằng
`docker compose exec web python manage.py seed_demo`.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_entrypoint_khong_chua_seed_demo():
    assert "seed_demo" not in (ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")


def test_dockerfile_va_compose_khong_goi_seed_demo():
    for name in ("Dockerfile", "docker-compose.yml"):
        assert "seed_demo" not in (ROOT / name).read_text(encoding="utf-8"), name
