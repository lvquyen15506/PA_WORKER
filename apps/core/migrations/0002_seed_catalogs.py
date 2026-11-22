"""Nạp danh mục mặc định (models.md mục 3.3). Admin sửa được sau; không ghi đè nếu đã có."""

from django.db import migrations

GROUPS = [
    "CCCD mặt trước",
    "CCCD mặt sau",
    "Ảnh chân dung",
    "CV hoặc Đơn xin việc",
]

# (tên loại, system_code, tên nhóm bắt buộc)
DOCUMENT_TYPES = [
    ("CCCD mặt trước", "CCCD_FRONT", "CCCD mặt trước"),
    ("CCCD mặt sau", "CCCD_BACK", "CCCD mặt sau"),
    ("Ảnh chân dung", "PORTRAIT", "Ảnh chân dung"),
    ("CV", "CV", "CV hoặc Đơn xin việc"),
    ("Đơn xin việc", "APPLICATION_LETTER", "CV hoặc Đơn xin việc"),
    ("Bằng cấp", None, None),
    ("Chứng chỉ", None, None),
    ("Hợp đồng", "CONTRACT", None),
    ("Quyết định tiếp nhận", None, None),
    ("Văn bản đồng ý xử lý dữ liệu", "CONSENT", None),
    ("Khác", None, None),
]

EDUCATION_LEVELS = [
    ("Chưa qua đào tạo", 1),
    ("Tiểu học", 2),
    ("THCS", 3),
    ("THPT", 4),
    ("Trung cấp", 5),
    ("Cao đẳng", 6),
    ("Đại học", 7),
    ("Sau đại học", 8),
]

QR_FORMATS = ["CCCD_2021", "CAN_CUOC_2024"]


def seed(apps, schema_editor):
    Group = apps.get_model("core", "RequiredDocumentGroup")
    DocType = apps.get_model("core", "DocumentType")
    Level = apps.get_model("core", "EducationLevel")
    Qr = apps.get_model("core", "QrFormat")
    Setting = apps.get_model("core", "SystemSetting")

    groups = {}
    for order, name in enumerate(GROUPS, start=1):
        groups[name], _ = Group.objects.get_or_create(name=name, defaults={"sort_order": order})
    for order, (name, code, group) in enumerate(DOCUMENT_TYPES, start=1):
        DocType.objects.get_or_create(
            name=name,
            defaults={
                "system_code": code,
                "required_group": groups[group] if group else None,
                "sort_order": order,
            },
        )
    for name, rank in EDUCATION_LEVELS:
        Level.objects.get_or_create(name=name, defaults={"rank": rank})
    for doc_type in QR_FORMATS:
        # Cấu hình ban đầu theo câu 20 (giả định); giá trị mặc định lấy từ model.
        Qr.objects.get_or_create(id_doc_type=doc_type)
    Setting.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
