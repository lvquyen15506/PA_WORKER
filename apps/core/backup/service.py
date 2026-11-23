"""Tạo, kiểm tra, phục hồi bản sao lưu (Phase 8, kịch bản nghiệm thu 17).

Nội dung một file sao lưu (`pa-worker-YYYYMMDD-HHMMSS.pawbk`, giờ Việt Nam), mã hóa bằng `stream`:
- `db.dump`: `pg_dump -Fc` (không có dữ liệu phiên đăng nhập `django_session`), đẩy thẳng từ
  pg_dump vào luồng mã hóa, không ghi bản rõ ra đĩa.
- `media/...`: mọi tệp trong PRIVATE_MEDIA_ROOT (tài liệu hồ sơ, ảnh và CV của phiên nhận diện).
- `manifest.json`: phiên bản ứng dụng, migration đã áp dụng, số dòng mỗi bảng (đếm trong cùng
  snapshot với pg_dump), sha256 của bản dump và từng tệp.

KHÔNG có .env, SECRET_KEY, FIELD_ENCRYPTION_KEY, HASH_KEY trong file.

Phục hồi đọc và kiểm tra toàn bộ file TRƯỚC khi đụng vào dữ liệu đang có, phục hồi vào CSDL tạm,
so số dòng và khóa trên CSDL tạm, rồi mới thay CSDL và thư mục tệp đang dùng.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import psycopg
from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.db.migrations.loader import MigrationLoader
from django.utils import timezone
from psycopg import sql

from apps.audit.services import log
from apps.core import keys
from apps.core.choices import AuditAction

from . import container
from .stream import MSG_CORRUPT, BackupError, DecryptingReader, EncryptingWriter

logger = logging.getLogger(__name__)

FORMAT = 1
PREFIX = "pa-worker-"
SAFETY_PREFIX = "pa-worker-truoc-phuc-hoi-"
SUFFIX = ".pawbk"
REGULAR_NAME = re.compile(r"^pa-worker-\d{8}-\d{6}(-\d+)?\.pawbk$")
STAGING = ".restore-staging"
ADVISORY_KEY = 7_310_008  # khóa advisory riêng của sao lưu (khác run_daily_jobs)
EXCLUDED_TABLE_DATA = ("django_session",)
RESERVE_BYTES = 50 * 1024 * 1024

REMINDER = (
    "File sao lưu không chứa khóa mã hóa và đã được mã hóa bằng khóa FIELD_ENCRYPTION_KEY. "
    "Phục hồi cần đúng hai khóa FIELD_ENCRYPTION_KEY và HASH_KEY đã cất riêng khi cài đặt "
    "(USB hoặc giấy niêm phong); mất khóa thì không đọc lại được bản sao lưu này. "
    "Hãy chép file sao lưu ra ổ đĩa ngoài hoặc máy khác."
)


# ----- tiện ích --------------------------------------------------------------------------------
def human(size):
    """Dung lượng dễ đọc, dấu thập phân kiểu Việt Nam: 1,5 GB."""
    value = float(size)
    for unit in ("byte", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return (
                f"{int(value)} byte" if unit == "byte" else f"{value:.1f} {unit}".replace(".", ",")
            )
        value /= 1024
    return f"{value:.1f} GB"


def backup_dir():
    return Path(settings.BACKUP_DIR)


def db_params(alias="default"):
    params = connections[alias].settings_dict
    if params["ENGINE"] != "django.db.backends.postgresql":
        raise BackupError(
            "Sao lưu và phục hồi chỉ dùng được với bản chạy bằng Docker (PostgreSQL), "
            "không dùng cho bản chạy thử SQLite."
        )
    return {
        "host": params["HOST"] or "localhost",
        "port": str(params["PORT"] or 5432),
        "user": params["USER"],
        "password": params["PASSWORD"],
        "dbname": params["NAME"],
    }


def _connect(params, dbname=None, autocommit=True):
    return psycopg.connect(
        host=params["host"],
        port=params["port"],
        user=params["user"],
        password=params["password"],
        dbname=dbname or params["dbname"],
        autocommit=autocommit,
    )


def _pg_env(params):
    return {**os.environ, "PGPASSWORD": params["password"]}


def _pg_conn_args(params):
    return ["-h", params["host"], "-p", params["port"], "-U", params["user"]]


def _tail(fileobj, limit=400):
    fileobj.seek(0)
    return fileobj.read().decode("utf-8", errors="replace")[-limit:].strip()


def media_files(root):
    """(đường dẫn tương đối dạng posix, Path) của mọi tệp trong thư mục tệp riêng."""
    root = Path(root)
    if not root.exists():
        return []
    out = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel.split("/")[0].startswith(".restore") or not path.is_file():
            continue
        out.append((rel, path))
    return out


def ensure_space(dest, need):
    free = shutil.disk_usage(dest).free
    if free < need:
        raise BackupError(
            f"Ổ đĩa chứa bản sao lưu còn trống {human(free)}, cần khoảng {human(need)}. "
            "Hãy xóa bớt bản sao lưu cũ (thư mục backups) hoặc giải phóng dung lượng rồi thử lại."
        )
    return free


def _read_file_blocks(fileobj, digest):
    while True:
        block = fileobj.read(container.BLOCK_SIZE)
        if not block:
            return
        digest.update(block)
        yield block


# ----- tạo bản sao lưu -------------------------------------------------------------------------
def _snapshot_info(conn):
    """Số dòng mỗi bảng và migration đã áp dụng, đọc trong snapshot đang mở."""
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
    ]
    counts = {}
    for table in tables:
        if table in EXCLUDED_TABLE_DATA:
            continue
        query = sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
        counts[table] = conn.execute(query).fetchone()[0]
    migrations = {}
    for app, name in conn.execute("SELECT app, name FROM django_migrations ORDER BY app, name"):
        migrations.setdefault(app, []).append(name)
    return counts, migrations


def _new_path(dest, prefix):
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
    path = dest / f"{prefix}{stamp}{SUFFIX}"
    n = 2
    while path.exists():
        path = dest / f"{prefix}{stamp}-{n}{SUFFIX}"
        n += 1
    return path


def create_backup(dest=None, *, prefix=PREFIX, user=None, prune=True, keep=None, field_key=None):
    """Tạo một file sao lưu, tự kiểm tra đọc lại được, xóa bớt bản cũ. Trả dict kết quả."""
    field_key = field_key or settings.FIELD_ENCRYPTION_KEY
    dest = Path(dest or backup_dir())
    dest.mkdir(parents=True, exist_ok=True)
    params = db_params()
    media_root = Path(settings.PRIVATE_MEDIA_ROOT)
    media = media_files(media_root)

    conn = _connect(params)
    try:
        if not conn.execute("SELECT pg_try_advisory_lock(%s)", (ADVISORY_KEY,)).fetchone()[0]:
            raise BackupError("Đang có một lượt sao lưu hoặc phục hồi khác chạy; thử lại sau.")
        db_size = conn.execute("SELECT pg_database_size(current_database())").fetchone()[0]
        media_size = sum(path.stat().st_size for _, path in media)
        ensure_space(dest, int((db_size + media_size) * 1.2) + RESERVE_BYTES)

        # Snapshot xuất ra để pg_dump và số dòng trong manifest nhìn cùng một trạng thái CSDL.
        conn.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        snapshot = conn.execute("SELECT pg_export_snapshot()").fetchone()[0]
        counts, migrations = _snapshot_info(conn)

        final = _new_path(dest, prefix)
        partial = final.with_name(f".{final.name}.partial")
        try:
            media_manifest = {}
            with open(partial, "wb") as raw:
                writer = EncryptingWriter(raw, field_key)
                db_digest, db_bytes = _write_dump(writer, params, snapshot)
                for rel, path in media:
                    digest = hashlib.sha256()
                    try:
                        with open(path, "rb") as fh:
                            size = container.write_entry(
                                writer, f"media/{rel}", _read_file_blocks(fh, digest)
                            )
                    except FileNotFoundError:  # tệp bị xóa trong lúc sao lưu (phiên hết hạn)
                        continue
                    media_manifest[rel] = {"sha256": digest.hexdigest(), "bytes": size}
                manifest = {
                    "format": FORMAT,
                    "app": "PA Worker",
                    "app_version": settings.APP_VERSION,
                    "demo_mode": bool(settings.DEMO_MODE),
                    "created_at": timezone.localtime().isoformat(timespec="seconds"),
                    "migrations": migrations,
                    "tables": counts,
                    "excluded_table_data": list(EXCLUDED_TABLE_DATA),
                    "db": {"sha256": db_digest, "bytes": db_bytes},
                    "media": media_manifest,
                }
                payload = json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8")
                container.write_entry(writer, "manifest.json", [payload])
                container.write_end(writer)
                writer.close()
                raw.flush()
                os.fsync(raw.fileno())
            verify_backup(partial, field_key=field_key)  # tự kiểm tra đọc lại được
            os.replace(partial, final)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
    finally:
        conn.close()  # kết thúc snapshot, nhả khóa advisory

    size = final.stat().st_size
    removed = prune_backups(dest, keep) if prune else []
    log(
        AuditAction.BACKUP,
        user=user,
        object_type="core.Backup",
        object_id=final.name[:50],
        object_repr=final.name,
        note=f"Sao lưu {len(media_manifest)} tệp, CSDL {human(db_bytes)}, file {human(size)}",
    )
    return {
        "path": final,
        "bytes": size,
        "files": len(media_manifest),
        "removed": removed,
        "manifest": manifest,
    }


def _write_dump(writer, params, snapshot):
    command = [
        "pg_dump",
        "-Fc",
        "--no-owner",
        "--no-privileges",
        f"--snapshot={snapshot}",
        *[f"--exclude-table-data={table}" for table in EXCLUDED_TABLE_DATA],
        *_pg_conn_args(params),
        params["dbname"],
    ]
    digest = hashlib.sha256()
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err, env=_pg_env(params))
        try:
            size = container.write_entry(writer, "db.dump", _read_file_blocks(proc.stdout, digest))
        finally:
            proc.stdout.close()
            code = proc.wait()
        if code != 0:
            raise BackupError(f"Không sao lưu được CSDL (pg_dump báo lỗi): {_tail(err)}")
    return digest.hexdigest(), size


# ----- kiểm tra ---------------------------------------------------------------------------------
def verify_backup(path, *, field_key=None):
    """Đọc toàn bộ file: giải mã, kiểm tra toàn vẹn, pg_restore --list đọc được bản dump, sha256
    từng phần khớp manifest. Không thay đổi gì. Trả manifest."""
    field_key = field_key or settings.FIELD_ENCRYPTION_KEY
    seen, db_info, manifest = {}, None, None
    with open(path, "rb") as raw:
        reader = DecryptingReader(raw, field_key)
        for name, blocks in container.read_entries(reader):
            if name == "db.dump":
                db_info = _check_dump(blocks)
            elif name == "manifest.json":
                try:
                    manifest = json.loads(b"".join(blocks).decode("utf-8"))
                except (UnicodeDecodeError, ValueError) as exc:
                    raise BackupError(MSG_CORRUPT) from exc
            elif name.startswith("media/"):
                digest, size = hashlib.sha256(), 0
                for block in blocks:
                    digest.update(block)
                    size += len(block)
                seen[name[len("media/") :]] = {"sha256": digest.hexdigest(), "bytes": size}
            else:
                raise BackupError(MSG_CORRUPT)
    if manifest is None or db_info is None or manifest.get("format") != FORMAT:
        raise BackupError(MSG_CORRUPT)
    if manifest.get("db") != db_info or manifest.get("media") != seen:
        raise BackupError(MSG_CORRUPT)
    return manifest


def _check_dump(blocks):
    """Băm bản dump và cho pg_restore --list đọc thử (không cần CSDL)."""
    digest, size = hashlib.sha256(), 0
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(
            ["pg_restore", "--list"], stdin=subprocess.PIPE, stdout=out, stderr=err
        )
        alive = True
        for block in blocks:
            digest.update(block)
            size += len(block)
            if alive:
                try:
                    proc.stdin.write(block)
                except BrokenPipeError:
                    alive = False
        try:
            proc.stdin.close()
        except BrokenPipeError:
            pass
        if proc.wait() != 0:
            raise BackupError(
                f"Bản dump CSDL trong file sao lưu không đọc được (pg_restore): {_tail(err)}"
            )
        out.seek(0)
        if b"TABLE DATA" not in out.read():
            raise BackupError("Bản dump CSDL trong file sao lưu không có dữ liệu bảng.")
    return {"sha256": digest.hexdigest(), "bytes": size}


def check_compatible(manifest):
    """Bản sao lưu từ phiên bản mới hơn (có migration mà mã hiện tại không có) thì từ chối."""
    known = set(MigrationLoader(None, ignore_no_migrations=True).disk_migrations)
    unknown = [
        f"{app}.{name}"
        for app, names in manifest.get("migrations", {}).items()
        for name in names
        if (app, name) not in known
    ]
    if unknown:
        raise BackupError(
            f"Bản sao lưu được tạo từ phiên bản PA Worker {manifest.get('app_version')} mới hơn "
            f"bản đang cài ({settings.APP_VERSION}). Hãy cài phiên bản mới trước rồi phục hồi."
        )


# ----- phục hồi ---------------------------------------------------------------------------------
def _has_data():
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT EXISTS (SELECT 1 FROM accounts_user)")
            return cursor.fetchone()[0]
    except Exception:  # noqa: BLE001 – CSDL mới chưa migrate: không có gì để giữ
        return False


def _check_keys_on(conn):
    """Hai khóa hiện tại khớp giá trị kiểm tra trong CSDL vừa phục hồi (trước khi thay dữ liệu)."""
    from apps.core.crypto import decrypt_value

    row = conn.execute(
        "SELECT key_check_enc, key_check_hash FROM core_systemsetting WHERE id = 1"
    ).fetchone()
    if row is None or (row[0] is None and row[1] is None):
        return
    try:
        keys.verify_key_check(decrypt_value(row[0]), row[1])
    except keys.KeyConfigError as exc:
        raise BackupError(str(exc)) from exc


def restore_backup(
    path, *, target_db=None, media_root=None, safety_backup=True, field_key=None, stdout=None
):
    """Phục hồi CSDL và thư mục tệp từ file sao lưu. Trả manifest.

    Dừng web và scheduler trước khi chạy (Phuc hoi.bat làm việc này). Mọi kiểm tra chạy trước khi
    thay dữ liệu đang có; lỗi giữa chừng thì dữ liệu đang có giữ nguyên.
    """
    say = stdout.write if stdout else (lambda _text: None)
    field_key = field_key or settings.FIELD_ENCRYPTION_KEY
    path = Path(path)
    say("Đang kiểm tra file sao lưu…")
    manifest = verify_backup(path, field_key=field_key)
    check_compatible(manifest)
    params = db_params()
    target = target_db or params["dbname"]
    live = target == params["dbname"]
    media_root = Path(media_root or settings.PRIVATE_MEDIA_ROOT)

    if safety_backup and live and _has_data():
        say("Đang sao lưu dữ liệu hiện có trước khi phục hồi…")
        result = create_backup(prefix=SAFETY_PREFIX, prune=False, field_key=field_key)
        say(f"Đã giữ bản sao lưu dữ liệu cũ: {result['path'].name}")

    tmp_db = f"{target}_phuc_hoi"
    staging = media_root / STAGING
    connections.close_all()
    admin = _connect(params, dbname="postgres")
    try:
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(tmp_db))
        )
        admin.execute(
            sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING 'UTF8'").format(
                sql.Identifier(tmp_db), sql.Identifier(params["user"])
            )
        )
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        try:
            say("Đang phục hồi CSDL và tệp vào vùng tạm…")
            _restore_into(path, field_key, params, tmp_db, staging)
            with _connect(params, dbname=tmp_db) as conn:
                _compare_counts(conn, manifest)
                _check_keys_on(conn)
        except BaseException:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(tmp_db))
            )
            shutil.rmtree(staging, ignore_errors=True)
            raise

        say("Đang thay dữ liệu đang dùng bằng dữ liệu phục hồi…")
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(target))
        )
        admin.execute(
            sql.SQL("ALTER DATABASE {} RENAME TO {}").format(
                sql.Identifier(tmp_db), sql.Identifier(target)
            )
        )
        for child in media_root.iterdir():
            if child.name == STAGING:
                continue
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
        for child in staging.iterdir():
            child.rename(media_root / child.name)
        staging.rmdir()
    finally:
        admin.close()

    if live:
        connections.close_all()
        call_command("migrate", interactive=False, verbosity=0)  # bản sao lưu cũ hơn mã hiện tại
        log(
            AuditAction.RESTORE,
            object_type="core.Backup",
            object_id=path.name[:50],
            object_repr=path.name,
            note=(
                f"Phục hồi từ bản sao lưu tạo lúc {manifest['created_at']} "
                f"(phiên bản {manifest['app_version']}), {len(manifest['media'])} tệp"
            ),
        )
    return manifest


def _restore_into(path, field_key, params, dbname, staging):
    with open(path, "rb") as raw:
        reader = DecryptingReader(raw, field_key)
        for name, blocks in container.read_entries(reader):
            if name == "db.dump":
                _pg_restore(blocks, params, dbname)
            elif name.startswith("media/"):
                target = staging / name[len("media/") :]
                if staging.resolve() not in target.resolve().parents:
                    raise BackupError(MSG_CORRUPT)
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "wb") as fh:
                    for block in blocks:
                        fh.write(block)
            else:
                for _block in blocks:
                    pass


def _pg_restore(blocks, params, dbname):
    command = [
        "pg_restore",
        "--no-owner",
        "--no-privileges",
        "--exit-on-error",
        "--single-transaction",
        *_pg_conn_args(params),
        "-d",
        dbname,
    ]
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=out, stderr=err, env=_pg_env(params)
        )
        broken = False
        for block in blocks:
            if broken:
                continue
            try:
                proc.stdin.write(block)
            except BrokenPipeError:
                broken = True
        try:
            proc.stdin.close()
        except BrokenPipeError:
            pass
        if proc.wait() != 0 or broken:
            raise BackupError(f"Không phục hồi được CSDL (pg_restore báo lỗi): {_tail(err)}")


def _compare_counts(conn, manifest):
    wrong = []
    for table, expected in manifest["tables"].items():
        query = sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
        actual = conn.execute(query).fetchone()[0]
        if actual != expected:
            wrong.append(f"{table} ({actual}/{expected})")
    if wrong:
        raise BackupError(
            "Số dòng sau phục hồi không khớp bản sao lưu: " + ", ".join(wrong[:5]) + "."
        )


# ----- quản lý các bản sao lưu -----------------------------------------------------------------
def list_backups(dest=None):
    """Các file sao lưu (mới nhất trước)."""
    dest = Path(dest or backup_dir())
    if not dest.exists():
        return []
    files = [p for p in dest.glob(f"*{SUFFIX}") if p.name.startswith(PREFIX)]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def prune_backups(dest=None, keep=None):
    """Giữ `keep` bản sao lưu thường mới nhất (bản "trước phục hồi" không bị xóa tự động)."""
    dest = Path(dest or backup_dir())
    keep = settings.BACKUP_KEEP if keep is None else keep
    regular = sorted(p for p in dest.glob(f"*{SUFFIX}") if REGULAR_NAME.match(p.name))
    removed = []
    for old in regular[: max(len(regular) - keep, 0)]:
        old.unlink()
        removed.append(old.name)
    return removed


def latest_backup(dest=None):
    files = list_backups(dest)
    return files[0] if files else None


def auto_backup_due(dest=None, hours=None):
    """Đến lúc sao lưu tự động: chưa có bản sao lưu nào trong `hours` giờ qua."""
    hours = settings.BACKUP_INTERVAL_HOURS if hours is None else hours
    latest = latest_backup(dest)
    if latest is None:
        return True
    age = timezone.now().timestamp() - latest.stat().st_mtime
    return age >= hours * 3600


def disk_status():
    """[(nhãn, đường dẫn, còn trống, tổng)] cho thư mục tệp riêng và thư mục sao lưu."""
    out = []
    for label, path in (
        ("Thư mục tệp hồ sơ", Path(settings.PRIVATE_MEDIA_ROOT)),
        ("Thư mục sao lưu", backup_dir()),
    ):
        try:
            usage = shutil.disk_usage(path)
        except OSError:
            continue
        out.append((label, path, usage.free, usage.total))
    return out
