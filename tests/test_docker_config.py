"""Cấu hình Docker cho bản bàn giao (docs/ra-soat-bao-mat.md mục 1, 4, 5, 8, 9 và mục 5 Trivy)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_khong_con_tep_override_tu_dong():
    # "docker compose up" tự đọc docker-compose.override.yml; tệp dev phải có tên khác.
    assert not (ROOT / "docker-compose.override.yml").exists()
    assert (ROOT / "docker-compose.dev.yml").exists()


def test_compose_co_ten_du_an_co_dinh():
    assert re.search(r"^name: pa_worker$", read("docker-compose.yml"), re.M)


def test_compose_xoay_vong_log_moi_service():
    compose = read("docker-compose.yml")
    assert 'max-size: "10m"' in compose and 'max-file: "5"' in compose
    assert compose.count("logging: *logging") == 3


def test_db_khong_mo_cong():
    compose = read("docker-compose.yml")
    db_block = compose.split("  db:")[1].split("\n  web:")[0]
    assert "ports" not in db_block.replace('không có "ports"', "")


def test_web_chay_bang_nguoi_dung_app_va_gthread():
    dockerfile = read("Dockerfile")
    assert re.search(r"^USER app$", dockerfile, re.M)
    assert '"--worker-class", "gthread"' in dockerfile
    assert '"--worker-class",\n        "gthread"' in read("docker-compose.dev.yml")


def test_image_goc_ghim_digest():
    assert re.search(r"^FROM python:3\.12-slim@sha256:[0-9a-f]{64}$", read("Dockerfile"), re.M)
    db = read("docker/db.Dockerfile")
    assert re.search(r"^FROM postgres:16\.\d+@sha256:[0-9a-f]{64}$", db, re.M)


def test_db_chay_bang_postgres_khong_co_gosu():
    db = read("docker/db.Dockerfile")
    assert re.search(r"^USER postgres$", db, re.M)
    assert "rm /usr/local/bin/gosu" in db


def test_khong_dua_sao_luu_va_bi_mat_vao_image():
    ignored = read(".dockerignore").split()
    for name in (".env", "backups", "private_media"):
        assert name in ignored
