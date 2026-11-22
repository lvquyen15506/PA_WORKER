"""Kho tệp riêng: ngoài thư mục public, tên ngẫu nhiên, không có URL.

Tệp chỉ được trả về qua view có kiểm tra quyền (Phase 4).
"""

import os
import re
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateStorage(FileSystemStorage):
    @property
    def base_location(self):
        return str(settings.PRIVATE_MEDIA_ROOT)

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None

    def url(self, name):
        raise ValueError("Tệp riêng không có URL công khai; chỉ tải qua view kiểm tra quyền.")

    def save(self, name, content, max_length=None):
        """Giữ thư mục con, thay tên bằng uuid4().hex; đuôi lấy từ tên truyền vào
        (nơi gọi đặt đuôi theo định dạng thật của tệp)."""
        directory, original = os.path.split(str(name))
        ext = os.path.splitext(original)[1].lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,5}", ext):
            ext = ""
        return super().save(os.path.join(directory, uuid.uuid4().hex + ext), content, max_length)


private_storage = PrivateStorage()
