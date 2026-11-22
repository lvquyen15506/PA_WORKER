"""Dữ liệu nạp sẵn bằng data migration (Phase 2 bước 3a)."""

import pytest

from apps.accounts.models import Role
from apps.core.models import (
    DEFAULT_QR_FIELD_ORDER,
    DocumentType,
    EducationLevel,
    QrFormat,
    RequiredDocumentGroup,
    SystemSetting,
)

pytestmark = pytest.mark.django_db


def test_bon_vai_tro():
    assert dict(Role.objects.values_list("code", "name")) == {
        "ADMIN": "Admin",
        "HR_MANAGER": "Quản lý nhân sự",
        "HR_STAFF": "Nhân viên HR",
        "VIEWER": "Viewer",
    }


def test_nhom_tai_lieu_bat_buoc():
    assert list(RequiredDocumentGroup.objects.values_list("name", flat=True)) == [
        "CCCD mặt trước",
        "CCCD mặt sau",
        "Ảnh chân dung",
        "CV hoặc Đơn xin việc",
    ]


def test_loai_tai_lieu_va_system_code():
    assert DocumentType.objects.count() == 11
    codes = dict(DocumentType.objects.exclude(system_code=None).values_list("system_code", "name"))
    assert codes == {
        "CCCD_FRONT": "CCCD mặt trước",
        "CCCD_BACK": "CCCD mặt sau",
        "PORTRAIT": "Ảnh chân dung",
        "CV": "CV",
        "APPLICATION_LETTER": "Đơn xin việc",
        "CONTRACT": "Hợp đồng",
        "CONSENT": "Văn bản đồng ý xử lý dữ liệu",
    }
    # CV và Đơn xin việc chung một nhóm (câu 4)
    cv = DocumentType.objects.get(system_code="CV").required_group
    assert cv == DocumentType.objects.get(system_code="APPLICATION_LETTER").required_group
    assert cv.name == "CV hoặc Đơn xin việc"
    assert DocumentType.objects.get(system_code="CONTRACT").required_group is None
    assert DocumentType.objects.get(system_code="PORTRAIT").required_group.name == "Ảnh chân dung"


def test_trinh_do_hoc_van_co_cap_bac():
    levels = list(EducationLevel.objects.values_list("name", "rank"))
    assert len(levels) == 8
    assert levels[0] == ("Chưa qua đào tạo", 1)
    assert levels[-1] == ("Sau đại học", 8)
    assert dict(levels)["THPT"] == 4


def test_qr_format_mac_dinh_theo_cau_20():
    formats = {q.id_doc_type: q for q in QrFormat.objects.all()}
    assert set(formats) == {"CCCD_2021", "CAN_CUOC_2024"}  # mẫu 2016 không có QR
    for q in formats.values():
        assert q.separator == "|"
        assert q.field_order == DEFAULT_QR_FIELD_ORDER
        assert q.date_format == "ddmmyyyy"
        assert q.is_active


def test_cai_dat_he_thong_mot_dong_gia_tri_mac_dinh():
    assert SystemSetting.objects.count() == 1
    s = SystemSetting.load()
    assert s.pk == 1
    assert (s.worker_code_prefix, s.worker_code_use_year, s.worker_code_digits) == ("HS", True, 5)
    assert (s.employee_code_prefix, s.employee_code_use_year, s.employee_code_digits) == (
        "CN",
        False,
        5,
    )
    assert s.expiry_warning_days == 30
    assert s.ocr_confidence_threshold == 80
    assert s.failed_retention_months == 12
    assert s.resigned_retention_years == 10
    assert s.auto_archive_resigned_days == 30
    assert s.auto_archive_failed_days == 30
    assert s.stale_draft_months == 6
    assert s.intake_ttl_hours == 24
    assert s.external_ocr_enabled is False
    assert s.key_check_enc is None and s.key_check_hash is None
