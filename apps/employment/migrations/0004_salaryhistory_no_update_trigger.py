"""Trigger PostgreSQL: SalaryHistory chặn UPDATE (v1.1, câu 41: lương chỉ thêm dòng mới).

Vẫn cho DELETE vì ẩn danh hóa hồ sơ xóa toàn bộ lịch sử lương (apps.workers.retention._wipe;
ngoại lệ ghi ở CLAUDE.md). Chỉ chạy trên PostgreSQL; SQLite dựa vào chặn ở tầng model.
"""

from django.db import migrations

CREATE = """
CREATE OR REPLACE FUNCTION employment_salary_block_update() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Lịch sử lương chỉ được thêm dòng mới, không được sửa (%).', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER employment_salaryhistory_no_update
    BEFORE UPDATE ON employment_salaryhistory
    FOR EACH ROW EXECUTE FUNCTION employment_salary_block_update();
"""

DROP = """
DROP TRIGGER IF EXISTS employment_salaryhistory_no_update ON employment_salaryhistory;
DROP FUNCTION IF EXISTS employment_salary_block_update();
"""


def create_trigger(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CREATE, params=None)


def drop_trigger(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(DROP, params=None)


class Migration(migrations.Migration):
    dependencies = [("employment", "0003_employmenthistory_from_manager_and_more")]
    operations = [migrations.RunPython(create_trigger, drop_trigger)]
