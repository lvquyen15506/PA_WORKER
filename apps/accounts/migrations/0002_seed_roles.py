from django.db import migrations

ROLES = [
    ("ADMIN", "Admin"),
    ("HR_MANAGER", "Quản lý nhân sự"),
    ("HR_STAFF", "Nhân viên HR"),
    ("VIEWER", "Viewer"),
]


def seed_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for code, name in ROLES:
        Role.objects.update_or_create(code=code, defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(seed_roles, migrations.RunPython.noop)]
