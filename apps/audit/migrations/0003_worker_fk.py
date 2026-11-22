"""Thêm trường worker cho AuditLog và AuditPersonalValue (sau khi có model Worker).

AuditPersonalValue.worker bắt buộc: thêm dạng cho phép rỗng rồi đổi thành bắt buộc. Bảng
chưa có dòng nào ở thời điểm này nên không cần giá trị mặc định (và không UPDATE, nên
không chạm trigger chặn UPDATE).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0002_postgres_triggers"),
        ("workers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditlog",
            name="worker",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="workers.worker",
                verbose_name="Hồ sơ",
            ),
        ),
        migrations.AddField(
            model_name="auditpersonalvalue",
            name="worker",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="workers.worker",
            ),
        ),
        migrations.AlterField(
            model_name="auditpersonalvalue",
            name="worker",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="workers.worker",
            ),
        ),
    ]
