"""Quét mã nguồn: chỉ apps/workers/workflow.py được ghi Worker.verification_status.

Đây là lưới an toàn cho quy tắc "workflow.transition() là đường duy nhất đổi trạng thái xác minh"
(CLAUDE.md, models.md mục 4.1). Quét cây cú pháp (AST) của apps/, config/, scripts/, tests/.

Ngoại lệ đã được duyệt (22/11/2026): seed_demo.py, vì là dữ liệu lịch sử giả lập (ngày quá khứ).
WorkerDocument cũng có trường verification_status (bộ trạng thái tài liệu, bộ thứ tư) nên các
lệnh ghi trên đối tượng/queryset của tài liệu không bị tính (nhận biết bằng chữ "doc" trong tên).
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ["apps", "config", "scripts", "tests"]
FIELD = "verification_status"

ALLOWED_FILES = {
    "apps/workers/workflow.py",
    "apps/core/management/commands/seed_demo.py",
    "tests/test_verification_status_scan.py",  # chứa đoạn mã mẫu vi phạm dạng chuỗi
}
WRITE_CALLS = {"create", "update", "update_or_create", "get_or_create", "Worker"}
SQL_PATTERN = re.compile(r"update\s+workers_worker\b[^;]*verification_status", re.I | re.S)


def _is_document(node):
    return "doc" in ast.unparse(node).lower()


def _call_name(func):
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _dict_has_field(node):
    return isinstance(node, ast.Dict) and any(
        isinstance(k, ast.Constant) and k.value == FIELD for k in node.keys
    )


def _seq_has_field(node):
    return isinstance(node, (ast.List, ast.Tuple, ast.Set)) and any(
        isinstance(e, ast.Constant) and e.value == FIELD for e in node.elts
    )


def find_violations(source):
    """Trả danh sách (số dòng, mô tả) các chỗ có thể ghi verification_status của hồ sơ."""
    found = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        # 1. worker.verification_status = ... (kể cả +=, chú thích kiểu, gán nhiều đích)
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        for target in targets:
            for t in ast.walk(target):
                if isinstance(t, ast.Attribute) and t.attr == FIELD and not _is_document(t.value):
                    found.append((node.lineno, "gán thuộc tính verification_status"))

        # 2. Meta của ModelForm: fields chứa verification_status hoặc "__all__"
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "fields" for t in stmt.targets)
                    and (
                        _seq_has_field(stmt.value)
                        or (isinstance(stmt.value, ast.Constant) and stmt.value.value == "__all__")
                    )
                ):
                    found.append((stmt.lineno, "ModelForm cho phép sửa verification_status"))

        # 3. SQL thô
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and SQL_PATTERN.search(node.value)
        ):
            found.append((node.lineno, "SQL UPDATE verification_status"))

        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        document = _is_document(node.func)

        # 4. setattr(x, "verification_status", ...)
        if (
            name == "setattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == FIELD
            and not _is_document(node.args[0])
        ):
            found.append((node.lineno, "setattr verification_status"))

        # 5. từ khóa verification_status=, defaults={...}, **{...} trong lệnh ghi
        if name in WRITE_CALLS and not document:
            for kw in node.keywords:
                if kw.arg == FIELD:
                    found.append((node.lineno, f"{name}(verification_status=...)"))
                if kw.arg == "defaults" and _dict_has_field(kw.value):
                    found.append((node.lineno, f"{name}(defaults={{verification_status}})"))
                if kw.arg is None and _dict_has_field(kw.value):
                    found.append((node.lineno, f"{name}(**{{verification_status}})"))

        # 6. bulk_update(objs, ["verification_status"]) và save(update_fields=[...])
        if not document:
            if name == "bulk_update" and any(_seq_has_field(a) for a in node.args[1:2]):
                found.append((node.lineno, "bulk_update verification_status"))
            for kw in node.keywords:
                if kw.arg in ("update_fields", "fields") and _seq_has_field(kw.value):
                    found.append((node.lineno, f"{kw.arg}=[verification_status]"))
    return found


def _project_files():
    for directory in SCAN_DIRS:
        for path in (ROOT / directory).rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if "migrations" in path.parts or rel in ALLOWED_FILES:
                continue
            yield rel, path


def test_khong_noi_nao_ngoai_workflow_ghi_verification_status():
    files = list(_project_files())
    assert len(files) > 50, "quét quá ít file; đường dẫn gốc có thể sai"
    violations = []
    for rel, path in files:
        for lineno, why in find_violations(path.read_text(encoding="utf-8")):
            violations.append(f"{rel}:{lineno}: {why}")
    assert not violations, "Chỉ workflow.transition() được đổi verification_status:\n" + "\n".join(
        violations
    )


def test_workflow_la_noi_duy_nhat_co_ghi_that():
    # Chứng minh bộ quét "nhìn thấy" cách ghi của workflow (nếu không, test trên có thể rỗng).
    path = ROOT / "apps/workers/workflow.py"
    assert find_violations(path.read_text(encoding="utf-8"))


# ----- Tự kiểm bộ quét: mẫu vi phạm phải bị bắt, mẫu hợp lệ không bị bắt --------------------
VIOLATING = {
    "gán thuộc tính": "worker.verification_status = 'X'",
    "gán tăng": "worker.verification_status += 'X'",
    "update": "Worker.objects.filter(pk=1).update(verification_status='X')",
    "create": "Worker.objects.create(full_name='a', verification_status='X')",
    "khởi tạo": "w = Worker(verification_status='X')",
    "bulk_create": "Worker.objects.bulk_create([Worker(verification_status='X')])",
    "setattr": "setattr(worker, 'verification_status', 'X')",
    "defaults": "Worker.objects.update_or_create(pk=1, defaults={'verification_status': 'X'})",
    "get_or_create": "Worker.objects.get_or_create(pk=1, verification_status='X')",
    "** dict": "Worker.objects.filter(pk=1).update(**{'verification_status': 'X'})",
    "bulk_update": "Worker.objects.bulk_update(ws, ['verification_status'])",
    "update_fields": "worker.save(update_fields=['verification_status'])",
    "SQL": "cursor.execute('UPDATE workers_worker SET verification_status = %s')",
    "SQL nhiều dòng": (
        "cur.execute('''UPDATE workers_worker\n SET updated_at = now(),\n"
        " verification_status = 1''')"
    ),
    "ModelForm danh sách": (
        "class F:\n    class Meta:\n        fields = ['full_name', 'verification_status']"
    ),
    "ModelForm __all__": "class F:\n    class Meta:\n        fields = '__all__'",
    "gán trong hàm": "def f(w):\n    w.verification_status = 'X'\n    w.save()",
}
LEGIT = {
    "lọc": "Worker.objects.filter(verification_status='ARCHIVED')",
    "so sánh": "ok = worker.verification_status == 'X'",
    "đọc": "status = worker.verification_status",
    "sắp xếp": "qs.order_by('verification_status')",
    "values_list": "Worker.objects.values_list('verification_status', flat=True)",
    "nhật ký": "log('UPDATE', changes={'verification_status': ('A', 'B')})",
    "tài liệu create": "WorkerDocument.objects.create(verification_status='MATCHED')",
    "tài liệu update": "WorkerDocument.objects.filter(pk=1).update(verification_status='INVALID')",
    "tài liệu gán": "document.verification_status = 'MATCHED'",
    "tài liệu save": "doc.save(update_fields=['verification_status', 'verified_by'])",
    "form an toàn": "class F:\n    class Meta:\n        fields = ['full_name', 'phone']",
}


@pytest.mark.parametrize("source", list(VIOLATING.values()), ids=list(VIOLATING))
def test_bo_quet_bat_duoc_mau_vi_pham(source):
    assert find_violations(source)


@pytest.mark.parametrize("source", list(LEGIT.values()), ids=list(LEGIT))
def test_bo_quet_khong_bao_nham_mau_hop_le(source):
    assert find_violations(source) == []
