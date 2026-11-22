"""Service tài liệu: tải lên, thay thế (giữ bản cũ), xác minh; quyền theo ma trận 4.4."""

import datetime
from pathlib import Path

import pytest
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.models import AuditLog
from apps.core.choices import VerificationStatus as VS
from apps.core.models import DocumentType
from apps.documents import services
from apps.documents.models import WorkerDocument
from apps.documents.services import DocumentError
from apps.employment.models import Contract
from apps.workers.models import Worker
from tests import samples
from tests.factories import make_document, make_user, make_worker_in_status

pytestmark = pytest.mark.django_db
ROLES = ["ADMIN", "HR_MANAGER", "HR_STAFF", "VIEWER"]


def dtype(code="CCCD_FRONT"):
    return DocumentType.objects.get(system_code=code)


def disk(doc):
    return Path(settings.PRIVATE_MEDIA_ROOT) / doc.stored_file.name


def upload(worker, role="HR_STAFF", kind="PDF", code="CCCD_FRONT", **kw):
    return services.upload_document(
        make_user(role), worker, dtype(code), samples.upload(kind, **kw.pop("file", {})), **kw
    )


# ===== Tải lên ===========================================================================
@pytest.mark.parametrize("kind", ["JPG", "PNG", "PDF", "DOC", "DOCX"])
def test_tai_len_luu_tep_ngau_nhien_ngoai_thu_muc_cong_khai(kind):
    worker = make_worker_in_status(VS.DRAFT)
    user = make_user("HR_STAFF")
    uploaded = samples.upload(kind, name=f"Hồ sơ Nguyễn Thị Ánh{samples.EXT[kind]}")
    doc = services.upload_document(user, worker, dtype(), uploaded, note=" Bản chụp rõ ")
    path = disk(doc)
    assert path.exists() and path.read_bytes() == samples.BY_KIND[kind]
    root = Path(settings.PRIVATE_MEDIA_ROOT)
    assert root in path.parents and path.parent == root / "documents" / str(worker.pk)
    # Tên trên đĩa là chuỗi ngẫu nhiên + đuôi theo định dạng thật; không có tên gốc.
    assert path.stem != "tai-lieu" and len(path.stem) == 32 and path.suffix == samples.EXT[kind]
    assert "Nguyễn" not in path.name and "Ánh" not in str(path)
    assert doc.original_name == f"Hồ sơ Nguyễn Thị Ánh{samples.EXT[kind]}"
    assert doc.size_bytes == len(samples.BY_KIND[kind]) and doc.mime_type
    assert (doc.version, doc.is_current, doc.replaces, doc.uploaded_by) == (1, True, None, user)
    assert (doc.verification_status, doc.verified_by, doc.note) == (
        "UNVERIFIED",
        None,
        "Bản chụp rõ",
    )


def test_hai_lan_tai_len_cung_ten_cho_hai_tep_khac_nhau():
    worker = make_worker_in_status(VS.DRAFT)
    a, b = upload(worker), upload(worker)
    assert disk(a) != disk(b) and disk(a).exists() and disk(b).exists()


def test_tai_len_ghi_nhat_ky_khong_co_ten_tep_va_cap_nhat_ho_so():
    worker = make_worker_in_status(VS.DRAFT)
    before = Worker.objects.get(pk=worker.pk).updated_at
    doc = upload(worker, file={"name": "TênGốcRiêng.pdf"})
    entry = AuditLog.objects.filter(action="UPLOAD_FILE").get()
    assert entry.object_repr == str(doc) == f"{worker.worker_code} – {doc.document_type} v1"
    assert entry.worker_id == worker.pk and entry.user is not None
    assert "TênGốcRiêng" not in f"{entry.object_repr} {entry.note} {entry.changes}"
    assert Worker.objects.get(pk=worker.pk).updated_at > before


@pytest.mark.parametrize(
    ("status", "role", "allowed"),
    [
        (s, r, (s in (VS.DRAFT, VS.NEEDS_INFO, VS.VERIFIED)) and r != "VIEWER")
        for s in VS
        for r in ROLES
    ],
)
def test_ma_tran_them_tai_lieu(status, role, allowed):
    worker = make_worker_in_status(status)
    if allowed:
        assert upload(worker, role).worker_id == worker.pk
    else:
        with pytest.raises(PermissionDenied):
            upload(worker, role)
        assert not WorkerDocument.objects.filter(worker=worker).exists()
        assert not list((Path(settings.PRIVATE_MEDIA_ROOT)).rglob("*.pdf"))  # không để tệp mồ côi


def test_hr_them_duoc_tai_lieu_khi_da_xac_minh_va_trang_thai_ho_so_khong_doi():
    worker = make_worker_in_status(VS.VERIFIED)
    upload(worker, "HR_STAFF")
    assert Worker.objects.get(pk=worker.pk).verification_status == VS.VERIFIED


def test_ho_so_da_an_danh_khong_them_duoc():
    from django.utils import timezone

    worker = make_worker_in_status(VS.DRAFT)
    Worker.objects.filter(pk=worker.pk).update(anonymized_at=timezone.now())
    with pytest.raises(PermissionDenied):
        upload(worker, "ADMIN")


@pytest.mark.parametrize("content", [samples.EXE, b"", b"hello"])
def test_tep_khong_hop_le_bi_tu_choi_khong_de_lai_dong_hay_tep(content):
    worker = make_worker_in_status(VS.DRAFT)
    with pytest.raises(DocumentError):
        services.upload_document(
            make_user("HR_STAFF"), worker, dtype(), SimpleUploadedFile("a.pdf", content)
        )
    assert not WorkerDocument.objects.exists()
    assert not [p for p in Path(settings.PRIVATE_MEDIA_ROOT).rglob("*") if p.is_file()]


def test_loai_tai_lieu_ngung_su_dung_bi_tu_choi():
    worker = make_worker_in_status(VS.DRAFT)
    inactive = dtype("CV")
    DocumentType.objects.filter(pk=inactive.pk).update(is_active=False)
    inactive.refresh_from_db()
    with pytest.raises(DocumentError, match="đang sử dụng"):
        services.upload_document(make_user("HR_STAFF"), worker, inactive, samples.upload())
    with pytest.raises(DocumentError):
        services.upload_document(make_user("HR_STAFF"), worker, None, samples.upload())


def test_loi_co_so_du_lieu_giua_chung_xoa_tep_vua_luu(monkeypatch):
    worker = make_worker_in_status(VS.DRAFT)

    def boom(*args, **kwargs):
        raise RuntimeError("hỏng nhật ký")

    monkeypatch.setattr(services, "log", boom)
    with pytest.raises(RuntimeError):
        upload(worker)
    assert not WorkerDocument.objects.filter(worker=worker).exists()
    assert not [p for p in Path(settings.PRIVATE_MEDIA_ROOT).rglob("*") if p.is_file()]


# ===== Thay thế (giữ bản cũ) ===============================================================
def test_thay_the_giu_ban_cu_va_tao_ban_moi_hien_hanh():
    worker = make_worker_in_status(VS.DRAFT)
    v1 = upload(worker, kind="PDF")
    services.set_verification(make_user("HR_MANAGER"), v1, "MATCHED")
    user = make_user("HR_STAFF")
    v2 = services.replace_document(user, v1, samples.upload("JPG"), note="Ảnh rõ hơn")
    v1.refresh_from_db()
    assert (v1.is_current, v2.is_current) == (False, True)
    assert (v2.version, v2.replaces, v1.replaced_by, v2.document_type) == (
        2,
        v1,
        v2,
        v1.document_type,
    )
    assert disk(v1).exists() and disk(v2).exists() and disk(v1) != disk(v2)  # bản cũ không bị xóa
    assert disk(v1).read_bytes() == samples.PDF
    # Bản mới bắt đầu lại từ Chưa xác minh; bản cũ giữ nguyên trạng thái của nó.
    assert (v2.verification_status, v2.verified_by) == ("UNVERIFIED", None)
    assert v1.verification_status == "MATCHED"
    assert [d.version for d in services.version_chain(v2)] == [1, 2]
    assert [d.version for d in services.version_chain(v1)] == [1, 2]


def test_thay_the_nhieu_lan_tao_chuoi_phien_ban():
    worker = make_worker_in_status(VS.DRAFT)
    user = make_user("HR_STAFF")
    v1 = upload(worker)
    v2 = services.replace_document(user, v1, samples.upload("PNG"))
    v3 = services.replace_document(user, v2, samples.upload("JPG"))
    assert [d.version for d in services.version_chain(v1)] == [1, 2, 3]
    assert [d.is_current for d in services.version_chain(v3)] == [False, False, True]
    assert all(disk(d).exists() for d in (v1, v2, v3))


def test_chi_thay_the_duoc_ban_hien_hanh():
    worker = make_worker_in_status(VS.DRAFT)
    user = make_user("HR_STAFF")
    v1 = upload(worker)
    services.replace_document(user, v1, samples.upload())
    v1.refresh_from_db()
    with pytest.raises(DocumentError, match="hiện hành"):
        services.replace_document(user, v1, samples.upload())
    assert WorkerDocument.objects.filter(worker=worker).count() == 2


@pytest.mark.parametrize(
    ("status", "role", "allowed"),
    [
        (VS.DRAFT, "HR_STAFF", True),
        (VS.NEEDS_INFO, "HR_STAFF", True),
        (VS.VERIFIED, "HR_STAFF", False),  # HR không thay thế khi Đã xác minh (câu 10)
        (VS.VERIFIED, "HR_MANAGER", True),
        (VS.VERIFIED, "ADMIN", True),
        (VS.DRAFT, "VIEWER", False),
        (VS.PENDING, "ADMIN", False),
        (VS.PENDING, "HR_MANAGER", False),
        (VS.REJECTED, "ADMIN", False),
        (VS.ARCHIVED, "ADMIN", False),
    ],
)
def test_ma_tran_thay_the(status, role, allowed):
    worker = make_worker_in_status(status)
    original = make_document(worker, "CCCD_FRONT")
    user = make_user(role)
    if allowed:
        assert services.replace_document(user, original, samples.upload()).version == 2
    else:
        with pytest.raises(PermissionDenied):
            services.replace_document(user, original, samples.upload())
        original.refresh_from_db()
        assert original.is_current and WorkerDocument.objects.filter(worker=worker).count() == 1


def test_thay_the_tep_khong_hop_le_khong_dung_gi_den_ban_cu():
    worker = make_worker_in_status(VS.DRAFT)
    v1 = upload(worker)
    with pytest.raises(DocumentError):
        services.replace_document(
            make_user("HR_STAFF"), v1, SimpleUploadedFile("a.pdf", samples.EXE)
        )
    v1.refresh_from_db()
    assert v1.is_current and WorkerDocument.objects.count() == 1 and disk(v1).exists()


def test_loi_giua_chung_khi_thay_the_hoan_tac_ban_cu_va_xoa_tep_moi(monkeypatch):
    worker = make_worker_in_status(VS.DRAFT)
    v1 = upload(worker)
    files_before = {p for p in Path(settings.PRIVATE_MEDIA_ROOT).rglob("*") if p.is_file()}

    def boom(*args, **kwargs):
        raise RuntimeError("hỏng nhật ký")

    monkeypatch.setattr(services, "log", boom)
    with pytest.raises(RuntimeError):
        services.replace_document(make_user("HR_STAFF"), v1, samples.upload("JPG"))
    v1.refresh_from_db()
    assert v1.is_current and WorkerDocument.objects.count() == 1
    assert {p for p in Path(settings.PRIVATE_MEDIA_ROOT).rglob("*") if p.is_file()} == files_before


def test_thay_the_ghi_nhat_ky_replace_file_khong_co_ten_tep():
    worker = make_worker_in_status(VS.DRAFT)
    v1 = upload(worker)
    services.replace_document(make_user("HR_STAFF"), v1, samples.upload(name="BảnMớiRiêng.pdf"))
    entry = AuditLog.objects.filter(action="REPLACE_FILE").get()
    assert entry.note == "Thay thế bản v1" and entry.object_repr.endswith("v2")
    assert "BảnMớiRiêng" not in f"{entry.object_repr} {entry.note}"


def test_hop_dong_tro_ban_cu_van_hien_thi_ban_hien_hanh_cau_32():
    worker = make_worker_in_status(VS.DRAFT)
    user = make_user("HR_STAFF")
    v1 = upload(worker, code="CONTRACT")
    contract = Contract.objects.create(
        worker=worker,
        contract_no="HD-001",
        contract_type="FIXED_TERM",
        signed_date=datetime.date(2026, 1, 1),
        effective_date=datetime.date(2026, 1, 1),
        expiry_date=datetime.date(2027, 1, 1),
        document=v1,
        created_by=user,
    )
    v2 = services.replace_document(user, v1, samples.upload("JPG"))
    v3 = services.replace_document(user, v2, samples.upload("PNG"))
    contract = Contract.objects.get(pk=contract.pk)
    assert contract.document_id == v1.pk and contract.current_document == v3


# ===== Xác minh tài liệu (câu 34) ===========================================================
@pytest.mark.parametrize(
    ("status", "role", "allowed"),
    [
        (
            s,
            r,
            (s in (VS.DRAFT, VS.NEEDS_INFO, VS.PENDING, VS.VERIFIED))
            and r in ("ADMIN", "HR_MANAGER"),
        )
        for s in VS
        for r in ROLES
    ],
)
def test_ma_tran_xac_minh(status, role, allowed):
    worker = make_worker_in_status(status)
    doc = make_document(worker, "CCCD_FRONT")
    user = make_user(role)
    if allowed:
        result = services.set_verification(user, doc, "MATCHED", note="Đã đối chiếu bản gốc")
        assert result.verification_status == "MATCHED" and result.verified_by == user
    else:
        with pytest.raises(PermissionDenied):
            services.set_verification(user, doc, "MATCHED")
        doc.refresh_from_db()
        assert doc.verification_status == "UNVERIFIED"


def test_xac_minh_ghi_nguoi_thoi_gian_nhat_ky_va_doi_lai_xoa_nguoi_xac_minh():
    worker = make_worker_in_status(VS.PENDING)  # Chờ duyệt vẫn đổi được (câu 34)
    doc = make_document(worker, "CCCD_FRONT")
    manager = make_user("HR_MANAGER")
    services.set_verification(manager, doc, "INVALID", note="Ảnh mờ")
    doc.refresh_from_db()
    assert (doc.verification_status, doc.verified_by, doc.note) == ("INVALID", manager, "Ảnh mờ")
    assert doc.verified_at is not None
    entry = AuditLog.objects.filter(action="UPDATE", object_type="documents.WorkerDocument").get()
    assert entry.changes == {"verification_status": ["UNVERIFIED", "INVALID"]}
    assert entry.object_repr == str(doc)
    services.set_verification(manager, doc, "UNVERIFIED")
    doc.refresh_from_db()
    assert (doc.verified_by, doc.verified_at) == (None, None)


def test_xac_minh_chi_ban_hien_hanh_va_gia_tri_hop_le():
    worker = make_worker_in_status(VS.DRAFT)
    manager = make_user("HR_MANAGER")
    v1 = upload(worker)
    services.replace_document(make_user("HR_STAFF"), v1, samples.upload())
    v1.refresh_from_db()
    with pytest.raises(DocumentError, match="hiện hành"):
        services.set_verification(manager, v1, "MATCHED")
    with pytest.raises(ValueError):
        services.set_verification(manager, v1, "NOT_A_STATUS")


def test_khong_tai_lieu_hop_le_khong_tinh_la_du_nhom_sau_khi_danh_dau_khong_hop_le():
    worker = make_worker_in_status(VS.DRAFT)
    doc = make_document(worker, "PORTRAIT")
    assert "Ảnh chân dung" not in [g.name for g in services.missing_groups(worker)]
    services.set_verification(make_user("ADMIN"), doc, "INVALID")
    assert "Ảnh chân dung" in [g.name for g in services.missing_groups(worker)]
