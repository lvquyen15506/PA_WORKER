"""Nền cho các bảng "chỉ thêm" (AuditLog, LoginHistory, StatusChange, EmploymentHistory).

Chặn sửa/xóa ở tầng model và QuerySet (cả SQLite lẫn PostgreSQL). Riêng AuditLog và
AuditPersonalValue còn có trigger PostgreSQL (apps/audit/migrations). Lưu ý: trigger
DELETE không chặn TRUNCATE (Django dùng khi dọn DB test).
"""

from django.db import models


class AppendOnlyError(Exception):
    """Cố sửa hoặc xóa bản ghi của bảng chỉ thêm."""


MSG_APPEND_ONLY = "Bảng này chỉ được thêm bản ghi, không được sửa hoặc xóa."
MSG_NO_UPDATE = "Bản ghi này không được sửa."


class AppendOnlyQuerySet(models.QuerySet):
    allow_delete = False

    def update(self, **kwargs):
        raise AppendOnlyError(MSG_NO_UPDATE)

    def bulk_update(self, objs, fields, batch_size=None):
        raise AppendOnlyError(MSG_NO_UPDATE)

    def delete(self):
        if not self.allow_delete:
            raise AppendOnlyError(MSG_APPEND_ONLY)
        return super().delete()


class NoUpdateQuerySet(AppendOnlyQuerySet):
    """Chặn sửa nhưng cho xóa (AuditPersonalValue: chỉ xóa khi ẩn danh hóa)."""

    allow_delete = True


class AppendOnlyModel(models.Model):
    append_only_allow_delete = False
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AppendOnlyError(MSG_NO_UPDATE)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not self.append_only_allow_delete:
            raise AppendOnlyError(MSG_APPEND_ONLY)
        return super().delete(*args, **kwargs)
