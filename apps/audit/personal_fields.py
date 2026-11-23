"""Danh sách trường cá nhân (PERSONAL_FIELDS), khai báo MỘT chỗ (docs/thiet-ke/models.md mục 3.2).

Giá trị các trường này không bao giờ ghi rõ vào AuditLog.changes: chỉ ghi "(xem giá trị chi tiết)",
giá trị trước/sau nằm ở AuditPersonalValue (mã hóa). Khóa là "app_label.ModelName"; giá trị là
tên LOGIC của trường như models.md mục 3.2 (IdentityDocument: id_number, old_id_number,
permanent_address; không có hậu tố _enc). Ánh xạ tên logic -> tên thuộc tính model khai báo
một chỗ ở LOGICAL_TO_ATTR. log() nhận giá trị rõ theo tên logic.

Tên lưu ở AuditPersonalValue.field_name và khóa của AuditLog.changes (field_label):
    Worker                 -> "full_name"
    IdentityDocument       -> "identity.id_number"
    Employment             -> "employment.resign_note"
    dòng con nhiều dòng    -> "emergency_contacts[<pk>].phone", "applications[<pk>].status"...

Hệ quả cho __str__: __str__ của mọi model không được chứa giá trị của các trường này, vì
__str__ dễ lọt vào object_repr, log và trang lỗi.
"""

PERSONAL_FIELDS = {
    "workers.Worker": {
        "full_name",
        "date_of_birth",
        "gender",
        "phone",
        "email",
        "current_address",
        "skills",
        "note",
        # Phase 7: lý do do người dùng gõ khi đổi trạng thái xác minh (có thể chứa tên). Trường ảo,
        # xem VIRTUAL_FIELDS: không phải cột của Worker, chỉ để ghi vào AuditPersonalValue.
        "status_reason",
    },
    "workers.IdentityDocument": {
        "id_number",
        "old_id_number",
        "issue_date",
        "issue_place",
        "expiry_date",
        "hometown",
        "birth_registration_place",
        "permanent_address",
    },
    "workers.EmergencyContact": {"full_name", "relationship", "phone"},
    "recruitment.Application": {"expected_salary", "interview_notes", "reject_reason"},
    "recruitment.Education": {"school_name", "major", "note"},
    "recruitment.Certificate": {"name", "issuer", "note"},
    "recruitment.WorkExperience": {"company_name", "job_title", "description"},
    "employment.Employment": {"resign_note"},
    "employment.Contract": {"note"},
    # v1.1 (câu 41): giá trị lương không bao giờ vào AuditLog.changes.
    "employment.WorkAssignment": {"note"},
    "employment.SalaryHistory": {"monthly_salary", "client_unit_price", "reason"},
}


# Trường cá nhân "ảo": ghi qua log() nhưng không có cột tương ứng trong model.
VIRTUAL_FIELDS = {"workers.Worker": {"status_reason"}}

# Tên logic -> tên thuộc tính của model, chỉ khi hai tên khác nhau (cột mã hóa có hậu tố _enc).
LOGICAL_TO_ATTR = {
    "workers.IdentityDocument": {
        "id_number": "id_number_enc",
        "old_id_number": "old_id_number_enc",
        "permanent_address": "permanent_address_enc",
    },
    "employment.SalaryHistory": {
        "monthly_salary": "monthly_salary_enc",
        "client_unit_price": "client_unit_price_enc",
    },
}

# Tiền tố của tên lưu trữ. "" = trường của chính hồ sơ; "x." = bản ghi 1-1; "x[<pk>]." = dòng con.
SINGLE_PREFIX = {
    "workers.IdentityDocument": "identity",
    "employment.Employment": "employment",
}
COLLECTION_PREFIX = {
    "workers.EmergencyContact": "emergency_contacts",
    "recruitment.Application": "applications",
    "recruitment.Education": "education",
    "recruitment.Certificate": "certificates",
    "recruitment.WorkExperience": "work_experiences",
    "employment.Contract": "contracts",
    "employment.WorkAssignment": "work_assignments",
    "employment.SalaryHistory": "salary_history",
}


def is_personal(model_label, field_name):
    """field_name là tên logic."""
    return field_name in PERSONAL_FIELDS.get(model_label, ())


def attr_name(model_label, logical_name):
    """Tên thuộc tính của model ứng với tên logic."""
    return LOGICAL_TO_ATTR.get(model_label, {}).get(logical_name, logical_name)


def field_label(model_label, logical_name, pk=None):
    """Tên lưu ở AuditPersonalValue.field_name và khóa của AuditLog.changes."""
    if model_label in SINGLE_PREFIX:
        return f"{SINGLE_PREFIX[model_label]}.{logical_name}"
    if model_label in COLLECTION_PREFIX:
        return f"{COLLECTION_PREFIX[model_label]}[{pk}].{logical_name}"
    return logical_name
