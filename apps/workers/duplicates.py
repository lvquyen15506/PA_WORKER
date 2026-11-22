"""Kiểm tra trùng hồ sơ (models.md mục 4.5, lam-ro-yeu-cau.md câu 5).

- find_by_id_number: trùng số định danh (so giá trị băm) -> LỖI, kèm hồ sơ cũ để "Mở hồ sơ cũ".
- find_similar: trùng SĐT, hoặc họ tên không dấu + ngày sinh -> CẢNH BÁO, không chặn; chỉ dùng khi
  chưa có số định danh.
Hồ sơ đã ẩn danh hóa không tham gia (dữ liệu đã xóa).
"""

from collections import namedtuple

from apps.core.crypto import compute_id_hash
from apps.core.text import compute_name_search

from .models import IdentityDocument, Worker

SimilarMatch = namedtuple("SimilarMatch", ["worker", "by_phone", "by_name_dob"])

MAX_SIMILAR = 10


def find_by_id_number(id_number, exclude_worker=None):
    """Hồ sơ đang giữ số định danh này, hoặc None. `exclude_worker`: bỏ qua chính hồ sơ đang sửa."""
    digest = compute_id_hash(id_number)
    if not digest:
        return None
    query = IdentityDocument.objects.filter(id_number_hash=digest).select_related("worker")
    if exclude_worker is not None:
        query = query.exclude(worker=exclude_worker)
    identity = query.first()
    return identity.worker if identity else None


def find_similar(*, phone="", full_name="", date_of_birth=None, exclude_worker=None):
    """Danh sách SimilarMatch: hồ sơ trùng SĐT và/hoặc trùng họ tên không dấu + ngày sinh."""
    phone = (phone or "").strip()
    name_search = compute_name_search(full_name)
    matches = {}

    def add(worker, **flags):
        entry = matches.get(worker.pk, SimilarMatch(worker, False, False))
        matches[worker.pk] = entry._replace(**flags)

    base = Worker.objects.filter(anonymized_at__isnull=True)
    if exclude_worker is not None:
        base = base.exclude(pk=exclude_worker.pk)
    if phone:
        for worker in base.filter(phone=phone)[:MAX_SIMILAR]:
            add(worker, by_phone=True)
    if name_search and date_of_birth:
        for worker in base.filter(name_search=name_search, date_of_birth=date_of_birth)[
            :MAX_SIMILAR
        ]:
            add(worker, by_name_dob=True)
    return sorted(matches.values(), key=lambda m: m.worker.worker_code)[:MAX_SIMILAR]
