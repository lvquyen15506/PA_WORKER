"""Nhãn tiếng Việt của tab Lịch sử thay đổi."""

import pytest

from apps.workers.history_labels import field_label, value_label


@pytest.mark.parametrize(
    ("field", "object_type", "expected"),
    [
        ("full_name", "workers.Worker", "Họ và tên"),
        ("date_of_birth", "workers.Worker", "Ngày sinh"),
        ("verification_status", "workers.Worker", "Trạng thái hồ sơ"),
        ("verification_status", "documents.WorkerDocument", "Trạng thái xác minh tài liệu"),
        ("identity.id_number", "workers.IdentityDocument", "Số CCCD"),
        ("identity.permanent_address", "workers.IdentityDocument", "Nơi thường trú"),
        ("identity.id_doc_type", "workers.IdentityDocument", "Loại giấy tờ"),
        (
            "emergency_contacts[706].phone",
            "workers.EmergencyContact",
            "Người liên hệ khẩn cấp – số điện thoại",
        ),
        (
            "emergency_contacts[7].full_name",
            "workers.EmergencyContact",
            "Người liên hệ khẩn cấp – họ và tên",
        ),
        (
            "applications[3].expected_salary",
            "recruitment.Application",
            "Ứng tuyển – mức lương mong muốn",
        ),
        (
            "khong_biet",
            "workers.Worker",
            "khong_biet",
        ),  # không biết thì giữ nguyên, không mất thông tin
    ],
)
def test_nhan_truong(field, object_type, expected):
    assert field_label(field, object_type) == expected


@pytest.mark.parametrize(
    ("field", "object_type", "value", "expected"),
    [
        ("verification_status", "workers.Worker", "PENDING", "Chờ duyệt"),
        ("verification_status", "workers.Worker", "VERIFIED", "Đã xác minh"),
        ("verification_status", "documents.WorkerDocument", "MATCHED", "Đã đối chiếu bản gốc"),
        ("verification_status", "documents.WorkerDocument", "INVALID", "Không hợp lệ"),
        ("gender", "workers.Worker", "FEMALE", "Nữ"),
        (
            "identity.id_doc_type",
            "workers.IdentityDocument",
            "CAN_CUOC_2024",
            "Thẻ Căn cước (từ 01/7/2024)",
        ),
        ("date_of_birth", "workers.Worker", "1995-05-20", "20/05/1995"),
        ("identity.issue_date", "workers.IdentityDocument", "2021-01-02", "02/01/2021"),
        ("full_name", "workers.Worker", "Nguyễn Văn An", "Nguyễn Văn An"),
        ("verification_status", "workers.Worker", "LA", "LA"),  # mã lạ giữ nguyên
        ("full_name", "workers.Worker", None, None),
        ("full_name", "workers.Worker", "", None),
    ],
)
def test_nhan_gia_tri(field, object_type, value, expected):
    assert value_label(field, object_type, value) == expected
