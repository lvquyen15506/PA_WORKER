"""Hàm dựng dữ liệu giả cho test. Mọi số CCCD giả bắt đầu bằng 999, tên là tên hư cấu."""

import itertools

from apps.accounts.models import Role, User
from apps.workers.models import Worker

_seq = itertools.count(1)


PASSWORD = "Mk123456a"  # mật khẩu giả dùng trong test


def make_user(role="HR_STAFF", username=None, password=PASSWORD, must_change=False, **kwargs):
    n = next(_seq)
    user = User(
        username=username or f"user{n}",
        full_name=f"Người Dùng Giả {n}",
        role=Role.objects.get(code=role),
        must_change_password=must_change,
        **kwargs,
    )
    user.set_password(password)
    user.save()
    return user


def make_worker(created_by=None, **kwargs):
    n = next(_seq)
    defaults = {
        "worker_code": f"HS-TEST-{n:05d}",
        "full_name": f"Nguyễn Văn Giả {n}",
        "phone": f"09{n:08d}"[:10],
        "created_by": created_by or make_user(),
    }
    defaults.update(kwargs)
    return Worker.objects.create(**defaults)


def fake_id(n=None):
    """Số CCCD giả: 999 + 9 chữ số."""
    return f"999{(n if n is not None else next(_seq)):09d}"
