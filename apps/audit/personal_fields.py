"""Danh sách trường cá nhân (PERSONAL_FIELDS), khai báo MỘT chỗ (docs/thiet-ke/models.md mục 3.2).

Giá trị các trường này không bao giờ ghi rõ vào AuditLog.changes: chỉ ghi "(xem giá trị chi tiết)",
giá trị trước/sau nằm ở AuditPersonalValue (mã hóa). Khóa là "app_label.ModelName"; giá trị là
tên trường của model (IdentityDocument dùng đúng tên cột model, kể cả hậu tố _enc).

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
    },
    "workers.IdentityDocument": {
        "id_number_enc",
        "old_id_number_enc",
        "issue_date",
        "issue_place",
        "expiry_date",
        "hometown",
        "birth_registration_place",
        "permanent_address_enc",
    },
    "workers.EmergencyContact": {"full_name", "relationship", "phone"},
    "recruitment.Application": {"expected_salary", "interview_notes", "reject_reason"},
    "recruitment.Education": {"school_name", "major", "note"},
    "recruitment.Certificate": {"name", "issuer", "note"},
    "recruitment.WorkExperience": {"company_name", "job_title", "description"},
    "employment.Employment": {"resign_note"},
    "employment.Contract": {"note"},
}


def is_personal(model_label, field_name):
    return field_name in PERSONAL_FIELDS.get(model_label, ())
