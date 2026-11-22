"""Trigger PostgreSQL: AuditLog chặn UPDATE và DELETE; AuditPersonalValue chặn UPDATE.

Chỉ chạy trên PostgreSQL (SQLite dự phòng dựa vào chặn ở tầng model). Lưu ý: trigger
DELETE không chặn TRUNCATE. AuditPersonalValue vẫn xóa được (ẩn danh hóa hồ sơ).
"""

from django.db import migrations

CREATE = """
CREATE OR REPLACE FUNCTION audit_block_modify() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Nhật ký chỉ được thêm, không được sửa hoặc xóa (%).', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_auditlog_append_only
    BEFORE UPDATE OR DELETE ON audit_auditlog
    FOR EACH ROW EXECUTE FUNCTION audit_block_modify();

CREATE TRIGGER audit_auditpersonalvalue_no_update
    BEFORE UPDATE ON audit_auditpersonalvalue
    FOR EACH ROW EXECUTE FUNCTION audit_block_modify();
"""

DROP = """
DROP TRIGGER IF EXISTS audit_auditpersonalvalue_no_update ON audit_auditpersonalvalue;
DROP TRIGGER IF EXISTS audit_auditlog_append_only ON audit_auditlog;
DROP FUNCTION IF EXISTS audit_block_modify();
"""


def create_triggers(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CREATE, params=None)  # params=None: không diễn giải dấu % trong SQL


def drop_triggers(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(DROP, params=None)


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]
    operations = [migrations.RunPython(create_triggers, drop_triggers)]
