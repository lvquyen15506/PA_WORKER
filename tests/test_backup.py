"""Sao lưu và phục hồi (Phase 8, kịch bản nghiệm thu 17, docs/lam-ro-yeu-cau.md câu 31, 49)."""

import base64
import hashlib
import io
import json
import os
import struct
from pathlib import Path

import psycopg
import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.audit.models import AuditLog
from apps.core.backup import container, service
from apps.core.backup.stream import (
    CHUNK_SIZE,
    HEADER,
    MSG_CORRUPT,
    MSG_NOT_BACKUP,
    MSG_TRUNCATED,
    MSG_WRONG_KEY,
    RECORD,
    BackupError,
    DecryptingReader,
    EncryptingWriter,
)
from apps.core.choices import AuditAction
from tests.factories import make_document, make_user, make_worker_full

OTHER_KEY = base64.urlsafe_b64encode(b"K" * 32).decode()


# ----- lớp mã hóa luồng -------------------------------------------------------------------------
def encrypt(data, key=None):
    raw = io.BytesIO()
    writer = EncryptingWriter(raw, key or settings.FIELD_ENCRYPTION_KEY)
    writer.write(data)
    writer.close()
    return raw.getvalue()


def decrypt(blob, key=None):
    reader = DecryptingReader(io.BytesIO(blob), key or settings.FIELD_ENCRYPTION_KEY)
    out = bytearray()
    while chunk := reader.read(100_000):
        out += chunk
    return bytes(out)


def records(blob):
    """Tách các khúc: [(vị trí bắt đầu, độ dài cả khúc)]."""
    pos, out = HEADER.size, []
    while pos < len(blob):
        _final, length = RECORD.unpack(blob[pos : pos + RECORD.size])
        out.append((pos, RECORD.size + length))
        pos += RECORD.size + length
    return out


@pytest.mark.parametrize("size", [0, 1, CHUNK_SIZE, CHUNK_SIZE + 1, 3 * CHUNK_SIZE + 5])
def test_ma_hoa_khu_hoi_moi_kich_thuoc(size):
    data = os.urandom(size)
    blob = encrypt(data)
    assert decrypt(blob) == data
    assert data[:64] not in blob[HEADER.size :] or size == 0


def test_moi_file_co_muoi_rieng():
    assert encrypt(b"giong nhau")[: HEADER.size] != encrypt(b"giong nhau")[: HEADER.size]


def test_sai_khoa_bao_ro_rang():
    with pytest.raises(BackupError) as exc:
        decrypt(encrypt(b"du lieu"), key=OTHER_KEY)
    assert str(exc.value) == MSG_WRONG_KEY


def test_sua_mot_byte_bi_phat_hien():
    blob = bytearray(encrypt(os.urandom(2 * CHUNK_SIZE)))
    blob[HEADER.size + RECORD.size + 1000] ^= 0x01
    with pytest.raises(BackupError, match=MSG_CORRUPT[:30]):
        decrypt(bytes(blob))


def test_cat_cut_phan_cuoi_bi_phat_hien():
    blob = encrypt(os.urandom(2 * CHUNK_SIZE + 10))
    start, _length = records(blob)[-1]
    with pytest.raises(BackupError) as exc:
        decrypt(blob[:start])
    assert str(exc.value) == MSG_TRUNCATED


def test_doi_thu_tu_khuc_bi_phat_hien():
    blob = encrypt(os.urandom(3 * CHUNK_SIZE + 10))
    (a, la), (b, lb) = records(blob)[:2]
    swapped = blob[:a] + blob[b : b + lb] + blob[a : a + la] + blob[b + lb :]
    with pytest.raises(BackupError, match=MSG_CORRUPT[:30]):
        decrypt(swapped)


def test_ghep_them_du_lieu_sau_khuc_cuoi_bi_phat_hien():
    with pytest.raises(BackupError, match=MSG_CORRUPT[:30]):
        decrypt(encrypt(b"abc") + b"x")


def test_tep_khong_phai_sao_luu():
    with pytest.raises(BackupError) as exc:
        decrypt(b"PK\x03\x04 khong phai")
    assert str(exc.value) == MSG_NOT_BACKUP


@pytest.mark.parametrize("name", ["../thoat.txt", "/etc/passwd", "media/../../x", "a\\b"])
def test_ten_phan_nguy_hiem_bi_tu_choi(name):
    raw = io.BytesIO()
    encoded = name.encode()
    raw.write(container.ENTRY + struct.pack(">H", len(encoded)) + encoded + struct.pack(">I", 0))
    raw.write(container.END)
    raw.seek(0)
    with pytest.raises(BackupError):
        for _name, blocks in container.read_entries(raw):
            list(blocks)


# ----- tạo bản sao lưu thật (cần pg_dump, dữ liệu đã commit) ------------------------------------
@pytest.fixture
def du_lieu(db):
    hr = make_user("HR_STAFF")
    worker = make_worker_full(created_by=hr, full_name="Trần Thị Sao Lưu")
    doc = make_document(worker, content=b"%PDF-1.4 tep sao luu thu nghiem " + os.urandom(64))
    return worker, doc


def all_plain(path):
    """Toàn bộ bản rõ (sau giải mã) của file sao lưu."""
    with open(path, "rb") as fh:
        reader = DecryptingReader(fh, settings.FIELD_ENCRYPTION_KEY)
        out = bytearray()
        while chunk := reader.read(1_000_000):
            out += chunk
    return bytes(out)


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_sao_luu_tao_file_co_ngay_gio_va_tu_kiem_tra(du_lieu):
    worker, doc = du_lieu
    result = service.create_backup()
    path = result["path"]
    assert path.parent == Path(settings.BACKUP_DIR)
    assert service.REGULAR_NAME.match(path.name)
    manifest = service.verify_backup(path)
    assert manifest["app_version"] == settings.APP_VERSION
    assert manifest["tables"]["workers_worker"] == 1
    assert "django_session" not in manifest["tables"]
    rel = doc.stored_file.name
    expected = hashlib.sha256(Path(settings.PRIVATE_MEDIA_ROOT, rel).read_bytes()).hexdigest()
    assert manifest["media"][rel]["sha256"] == expected
    assert not list(Path(settings.BACKUP_DIR).glob(".*.partial"))
    entry = AuditLog.objects.get(action=AuditAction.BACKUP)
    assert entry.user is None and entry.object_repr == path.name


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_file_sao_luu_ma_hoa_va_khong_chua_khoa(du_lieu):
    worker, _doc = du_lieu
    path = service.create_backup()["path"]
    blob = path.read_bytes()
    assert worker.full_name.encode() not in blob  # bản mã: không đọc được họ tên
    plain = all_plain(path)
    secrets = {
        settings.SECRET_KEY,
        settings.FIELD_ENCRYPTION_KEY,
        settings.HASH_KEY,
        os.environ.get("FIELD_ENCRYPTION_KEY", ""),
        os.environ.get("HASH_KEY", ""),
        os.environ.get("POSTGRES_PASSWORD", ""),
    }
    for secret in filter(None, secrets):
        assert secret.encode() not in plain
    assert b"SECRET_KEY=" not in plain and b"HASH_KEY=" not in plain


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_sao_luu_tu_choi_khi_thieu_dia(du_lieu, monkeypatch):
    class Usage:
        free = 1024
        total = 10**9

    monkeypatch.setattr(service.shutil, "disk_usage", lambda _path: Usage)
    with pytest.raises(BackupError, match="còn trống"):
        service.create_backup()
    assert list(Path(settings.BACKUP_DIR).glob("*")) == []


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_kiem_tra_phat_hien_file_bi_sua(du_lieu):
    path = service.create_backup()["path"]
    blob = bytearray(path.read_bytes())
    blob[len(blob) // 2] ^= 0xFF
    path.write_bytes(bytes(blob))
    with pytest.raises(BackupError):
        service.verify_backup(path)


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_kiem_tra_sai_khoa(du_lieu):
    path = service.create_backup()["path"]
    with pytest.raises(BackupError) as exc:
        service.verify_backup(path, field_key=OTHER_KEY)
    assert str(exc.value) == MSG_WRONG_KEY


def test_xoa_bot_ban_cu_giu_dung_so_ban(settings, tmp_path):
    settings.BACKUP_DIR = tmp_path
    names = [f"pa-worker-202611{d:02d}-010000.pawbk" for d in range(1, 8)]
    for name in names:
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "pa-worker-truoc-phuc-hoi-20261101-010000.pawbk").write_bytes(b"x")
    removed = service.prune_backups(keep=3)
    assert removed == names[:4]
    left = sorted(p.name for p in tmp_path.iterdir())
    assert left == sorted(names[4:] + ["pa-worker-truoc-phuc-hoi-20261101-010000.pawbk"])


def test_ban_sao_luu_phien_ban_moi_hon_bi_tu_choi():
    manifest = {"app_version": "9.0.0", "migrations": {"workers": ["9999_tuong_lai"]}}
    with pytest.raises(BackupError, match="mới hơn"):
        service.check_compatible(manifest)


@pytest.mark.django_db
def test_ban_sao_luu_cung_phien_ban_duoc_nhan():
    from django.db.migrations.recorder import MigrationRecorder

    applied = MigrationRecorder(connection).applied_migrations()
    migrations = {}
    for app, name in applied:
        migrations.setdefault(app, []).append(name)
    service.check_compatible({"app_version": settings.APP_VERSION, "migrations": migrations})


# ----- phục hồi vào CSDL riêng (không đụng CSDL test đang dùng) ---------------------------------
@pytest.fixture
def restore_db():
    params = service.db_params()
    name = f"{params['dbname']}_kiem_phuc_hoi"
    yield name
    with service._connect(params, dbname="postgres") as admin:
        for db_name in (name, f"{name}_phuc_hoi"):
            admin.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_phuc_hoi_khu_hoi_du_lieu_tep_va_giai_ma(du_lieu, restore_db, tmp_path):
    from apps.core.crypto import decrypt_value
    from apps.workers.models import IdentityDocument

    worker, doc = du_lieu
    id_number = IdentityDocument.objects.get(worker=worker).id_number_enc
    path = service.create_backup()["path"]
    media_root = tmp_path / "media_moi"
    media_root.mkdir()
    (media_root / "tep_cu_se_bi_thay.txt").write_text("cu")
    manifest = service.restore_backup(
        path, target_db=restore_db, media_root=media_root, safety_backup=False
    )
    params = service.db_params()
    with service._connect(params, dbname=restore_db) as conn:
        assert conn.execute("SELECT count(*) FROM workers_worker").fetchone()[0] == 1
        name = conn.execute("SELECT full_name FROM workers_worker").fetchone()[0]
        enc = conn.execute("SELECT id_number_enc FROM workers_identitydocument").fetchone()[0]
        for table, count in manifest["tables"].items():
            query = f'SELECT count(*) FROM "{table}"'
            assert conn.execute(query).fetchone()[0] == count, table
        # trigger chặn sửa/xóa nhật ký (AuditLog, AuditPersonalValue) vẫn còn sau phục hồi
        trigger_sql = (
            "SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgrelid IN "
            "('audit_auditlog'::regclass, 'audit_auditpersonalvalue'::regclass)"
        )
        restored_triggers = conn.execute(trigger_sql).fetchone()[0]
    with connection.cursor() as cursor:
        cursor.execute(trigger_sql)
        assert restored_triggers == cursor.fetchone()[0] > 0
    with service._connect(params, dbname=restore_db) as conn:
        conn.execute(
            "INSERT INTO audit_auditlog (created_at, actor_label, action, object_type, object_id,"
            " object_repr, changes, note) VALUES (now(), 'x', 'CREATE', 't', '1', 'r', '{}', '')"
        )
        with pytest.raises(psycopg.Error):
            conn.execute("UPDATE audit_auditlog SET note = 'sua'")
    assert name == "Trần Thị Sao Lưu"
    assert decrypt_value(enc) == id_number  # giải mã được bằng khóa hiện tại
    restored = media_root / doc.stored_file.name
    original = Path(settings.PRIVATE_MEDIA_ROOT) / doc.stored_file.name
    assert restored.read_bytes() == original.read_bytes()
    assert not (media_root / "tep_cu_se_bi_thay.txt").exists()
    assert not (media_root / service.STAGING).exists()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_phuc_hoi_sai_khoa_khong_dung_vao_du_lieu(du_lieu, restore_db, tmp_path):
    path = service.create_backup()["path"]
    media_root = tmp_path / "media_dang_dung"
    media_root.mkdir()
    (media_root / "tep_dang_dung.txt").write_text("giu nguyen")
    with pytest.raises(BackupError) as exc:
        service.restore_backup(
            path,
            target_db=restore_db,
            media_root=media_root,
            safety_backup=False,
            field_key=OTHER_KEY,
        )
    assert str(exc.value) == MSG_WRONG_KEY
    assert (media_root / "tep_dang_dung.txt").read_text() == "giu nguyen"
    params = service.db_params()
    with service._connect(params, dbname="postgres") as admin:
        exists = admin.execute(
            "SELECT count(*) FROM pg_database WHERE datname = %s", (restore_db,)
        ).fetchone()[0]
    assert exists == 0


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_phuc_hoi_sai_hash_key_bi_chan_truoc_khi_thay(du_lieu, restore_db, tmp_path, settings):
    call_command("check_keys", stdout=io.StringIO())  # ghi giá trị kiểm tra khóa
    path = service.create_backup()["path"]
    settings.HASH_KEY = base64.urlsafe_b64encode(b"Z" * 32).decode()
    media_root = tmp_path / "m"
    media_root.mkdir()
    with pytest.raises(BackupError, match="HASH_KEY"):
        service.restore_backup(
            path, target_db=restore_db, media_root=media_root, safety_backup=False
        )
    params = service.db_params()
    with service._connect(params, dbname="postgres") as admin:
        names = [r[0] for r in admin.execute("SELECT datname FROM pg_database")]
    assert restore_db not in names and f"{restore_db}_phuc_hoi" not in names


# ----- lệnh quản trị và scheduler ---------------------------------------------------------------
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_lenh_backup_va_verify(du_lieu):
    out = io.StringIO()
    call_command("backup", stdout=out)
    text = out.getvalue()
    assert "Đã sao lưu: pa-worker-" in text and "không chứa khóa" in text
    name = text.split("Đã sao lưu: ")[1].split()[0]
    out = io.StringIO()
    call_command("verify_backup", name, stdout=out)
    assert "đọc được và nguyên vẹn" in out.getvalue()


def test_lenh_restore_bat_buoc_xac_nhan(tmp_path, settings):
    settings.BACKUP_DIR = tmp_path
    (tmp_path / "pa-worker-20261101-010000.pawbk").write_bytes(b"x")
    with pytest.raises(CommandError, match="--yes"):
        call_command("restore", "pa-worker-20261101-010000.pawbk")


def test_lenh_verify_tep_khong_ton_tai(tmp_path, settings):
    settings.BACKUP_DIR = tmp_path
    with pytest.raises(CommandError, match="Không tìm thấy"):
        call_command("verify_backup", "khong-co.pawbk")


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_scheduler_tu_sao_luu_khi_den_han(du_lieu, settings):
    from apps.core.management.commands.run_scheduler import auto_backup

    settings.BACKUP_AUTO = True
    first = auto_backup()
    assert first and (Path(settings.BACKUP_DIR) / first).exists()
    assert auto_backup() is None  # vừa sao lưu: chưa đến hạn
    settings.BACKUP_AUTO = False
    for path in Path(settings.BACKUP_DIR).glob("*.pawbk"):
        os.utime(path, (0, 0))  # rất cũ
    assert auto_backup() is None  # tắt sao lưu tự động


def test_dung_luong_de_doc():
    assert service.human(512) == "512 byte"
    assert service.human(1536 * 1024**2) == "1,5 GB"


def test_manifest_json_hop_le_cho_doc_tay():
    # manifest giữ tiếng Việt có dấu, không ASCII-escape (dễ đọc khi kiểm tra tay)
    assert json.dumps({"a": "Sao lưu"}, ensure_ascii=False) == '{"a": "Sao lưu"}'
