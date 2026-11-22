"""Thêm loại tài liệu "Bản cam kết" (v1.1, câu 45). Không system_code, không thuộc nhóm bắt
buộc. Migration riêng vì nơi đã cài đã chạy 0002_seed_catalogs; không ghi đè nếu đã có."""

from django.db import migrations
from django.db.models import Max

NAME = "Bản cam kết"


def seed(apps, schema_editor):
    DocType = apps.get_model("core", "DocumentType")
    if DocType.objects.filter(name=NAME).exists():
        return
    # Đặt ngay trước "Khác" nếu có, để danh sách chọn vẫn để "Khác" ở cuối.
    other = DocType.objects.filter(name="Khác").first()
    if other is not None:
        order = other.sort_order
        DocType.objects.filter(pk=other.pk).update(sort_order=order + 1)
    else:
        order = (DocType.objects.aggregate(m=Max("sort_order"))["m"] or 0) + 1
    DocType.objects.create(name=NAME, system_code=None, required_group=None, sort_order=order)


def unseed(apps, schema_editor):
    DocType = apps.get_model("core", "DocumentType")
    WorkerDocument = apps.get_model("documents", "WorkerDocument")
    used = WorkerDocument.objects.filter(document_type__name=NAME).exists()
    if not used:  # đã có tài liệu loại này thì giữ (không xóa bản ghi có liên kết)
        DocType.objects.filter(name=NAME, system_code__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_systemsetting_assignment_limit_months_clientcompany"),
        ("documents", "0002_initial"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
