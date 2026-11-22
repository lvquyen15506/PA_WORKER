"""Phiên nhận diện CCCD/CV: bản ghi tạm (docs/thiet-ke/models.md mục 3.6)."""

import json
import os
import uuid

from django.db import models, transaction

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

    def get_result(self):
        """Kết quả nhận diện đã giải mã (dict); phiên chưa có kết quả thì {}."""
        return json.loads(self.result_enc) if self.result_enc else {}

    def set_result(self, result):
        self.result_enc = json.dumps(result, ensure_ascii=False)

    def _delete_files(self, names):
        folder = None
        for name in names:
            path = private_storage.path(name)
            folder = os.path.dirname(path)
            private_storage.delete(name)
        if folder and os.path.isdir(folder) and not os.listdir(folder):
            os.rmdir(folder)

    def close(self, *, after_commit=False):
        """Xóa tệp của phiên rồi xóa dòng phiên (lưu hồ sơ, hủy, hoặc hết hạn).

        `after_commit=True` (lưu hồ sơ): xóa dòng ngay trong giao dịch nhưng chỉ xóa tệp SAU KHI
        giao dịch thành công, để lưu hồ sơ lỗi thì phiên và ảnh còn nguyên."""
        names = [f.name for f in (self.front_image, self.back_image, self.cv_file) if f]
        self.delete()
        if after_commit:
            transaction.on_commit(lambda: self._delete_files(names))
        else:
            self._delete_files(names)
