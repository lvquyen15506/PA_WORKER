"""Phiên nhận diện CCCD/CV: bản ghi tạm (docs/thiet-ke/models.md mục 3.6)."""

import os
import uuid

from django.db import models

from apps.core.crypto import EncryptedTextField
from apps.core.storage import private_storage


def intake_upload_to(instance, filename):
    return f"intake/{instance.pk}/{filename}"


class IntakeSession(models.Model):
    """Được phép xóa cứng (không bảng nào trỏ tới). Không có trường trạng thái: còn dòng
    nghĩa là phiên đang mở."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    # created_at + SystemSetting.intake_ttl_hours (do service đặt)
    expires_at = models.DateTimeField()
    front_image = models.FileField(
        storage=private_storage, upload_to=intake_upload_to, null=True, blank=True
    )
    back_image = models.FileField(
        storage=private_storage, upload_to=intake_upload_to, null=True, blank=True
    )
    cv_file = models.FileField(
        storage=private_storage, upload_to=intake_upload_to, null=True, blank=True
    )
    # JSON mã hóa: kết quả kiểm tra ảnh, chuỗi QR, giá trị từng trường kèm nguồn, văn bản CV.
    result_enc = EncryptedTextField(null=True, blank=True)

    def __str__(self):
        return f"Phiên nhận diện {self.pk}"

    def close(self):
        """Xóa tệp của phiên rồi xóa dòng phiên (lưu hồ sơ, hủy, hoặc hết hạn)."""
        folder = None
        for field in (self.front_image, self.back_image, self.cv_file):
            if field:
                folder = os.path.dirname(field.path)
                field.delete(save=False)
        if folder and os.path.isdir(folder) and not os.listdir(folder):
            os.rmdir(folder)
        self.delete()
