"""Form hồ sơ công nhân (docs/thiet-ke/trang.md mục 5.4). Quy tắc kiểm tra nằm ở
apps.workers.validation (dùng chung với service); form chỉ chuyển lỗi xuống từng ô."""

from django import forms

from apps.audit.personal_fields import attr_name
from apps.core.choices import Gender, IdDocType

from .validation import (
    DRAFT,
    IDENTITY_FIELDS,
    SUBMISSION,
    SUBMISSION_REQUIRED,
    WORKER_FIELDS,
    validate_contacts,
    validate_worker_data,
)

DATE_FORMAT = "%d/%m/%Y"
MSG_DATE = "Nhập ngày đúng định dạng dd/mm/yyyy."


def _date_field(label):
    return forms.DateField(
        label=label,
        required=False,
        input_formats=[DATE_FORMAT],
        widget=forms.DateInput(format=DATE_FORMAT, attrs={"placeholder": "dd/mm/yyyy"}),
        error_messages={"invalid": MSG_DATE},
    )


class WorkerForm(forms.Form):
    """Thông tin cá nhân và giấy tờ. Nháp chỉ bắt buộc họ tên + SĐT (câu 5); `level=SUBMISSION`
    (sửa hồ sơ Đã xác minh) bắt buộc thêm các trường của mục 4.3."""

    full_name = forms.CharField(
        label="Họ và tên", max_length=100, error_messages={"required": "Nhập họ và tên."}
    )
    phone = forms.CharField(
        label="Số điện thoại", max_length=20, error_messages={"required": "Nhập số điện thoại."}
    )
    date_of_birth = _date_field("Ngày sinh")
    gender = forms.ChoiceField(
        label="Giới tính", required=False, choices=[("", "— Chọn —"), *Gender.choices]
    )
    nationality = forms.CharField(label="Quốc tịch", max_length=50, required=False)
    email = forms.CharField(label="Email", max_length=254, required=False)
    current_address = forms.CharField(label="Nơi ở hiện tại", max_length=255, required=False)
    id_doc_type = forms.ChoiceField(
        label="Loại giấy tờ", required=False, choices=[("", "— Chọn —"), *IdDocType.choices]
    )
    id_number = forms.CharField(label="Số CCCD", max_length=30, required=False)
    old_id_number = forms.CharField(label="Số CMND cũ", max_length=30, required=False)
    issue_date = _date_field("Ngày cấp")
    issue_place = forms.CharField(label="Nơi cấp", max_length=255, required=False)
    expiry_date = _date_field("Có giá trị đến")
    hometown = forms.CharField(label="Quê quán", max_length=255, required=False)
    birth_registration_place = forms.CharField(
        label="Nơi đăng ký khai sinh", max_length=255, required=False
    )
    permanent_address = forms.CharField(label="Nơi thường trú", max_length=255, required=False)
    skills = forms.CharField(
        label="Kỹ năng", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    note = forms.CharField(
        label="Ghi chú", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, instance=None, level=DRAFT, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.level = level
        self.result = None
        if instance is not None and not self.is_bound:
            self.initial = {**worker_initial(instance), **self.initial}
        elif instance is None:
            self.initial.setdefault("nationality", "Việt Nam")
        if level == SUBMISSION:
            for name in SUBMISSION_REQUIRED:
                self.fields[name].required = True
                self.fields[name].error_messages["required"] = SUBMISSION_REQUIRED[name]

    def clean(self):
        cleaned = super().clean()
        self.result = validate_worker_data(
            {k: v for k, v in cleaned.items() if k in WORKER_FIELDS + IDENTITY_FIELDS},
            instance=self.instance,
            level=self.level,
        )
        for name, message in self.result.errors.items():
            if name not in self.errors:
                self.add_error(name, message)
        return cleaned

    @property
    def warnings(self):
        """Cảnh báo không chặn lưu (dưới 18 tuổi, có thể trùng hồ sơ)."""
        return self.result.warnings if self.result else []

    @property
    def duplicate(self):
        """Hồ sơ đang giữ số CCCD trùng, để hiện nút "Mở hồ sơ cũ"."""
        return self.result.duplicate if self.result else None

    def service_data(self):
        """Dữ liệu đã kiểm tra, đúng khóa mà apps.workers.services nhận."""
        return {k: v for k, v in self.cleaned_data.items() if k in WORKER_FIELDS + IDENTITY_FIELDS}


class EmergencyContactForm(forms.Form):
    """Một dòng người liên hệ khẩn cấp: để trống cả dòng là bỏ qua; có dữ liệu thì đủ 3 trường."""

    id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    delete = forms.BooleanField(required=False, label="Xóa dòng này")
    full_name = forms.CharField(label="Họ tên người liên hệ", max_length=100, required=False)
    relationship = forms.CharField(label="Mối quan hệ", max_length=50, required=False)
    phone = forms.CharField(label="Số điện thoại", max_length=20, required=False)

    def clean(self):
        cleaned = super().clean()
        for name, message in validate_contacts([cleaned]).get(0, {}).items():
            self.add_error(name, message)
        return cleaned


ContactFormSet = forms.formset_factory(EmergencyContactForm, extra=1, max_num=10)


def contact_rows(formset):
    """Các dòng liên hệ hợp lệ của formset dưới dạng dict cho services (bỏ dòng trống)."""
    rows = []
    for form in formset.forms:
        data = getattr(form, "cleaned_data", None) or {}
        if data:
            rows.append(
                {
                    "id": data.get("id"),
                    "delete": data.get("delete", False),
                    "full_name": data.get("full_name", ""),
                    "relationship": data.get("relationship", ""),
                    "phone": data.get("phone", ""),
                }
            )
    return rows


def contact_initial(worker):
    return [
        {"id": c.pk, "full_name": c.full_name, "relationship": c.relationship, "phone": c.phone}
        for c in worker.emergency_contacts.all()
    ]


def worker_initial(worker):
    """Giá trị ban đầu của form sửa; số định danh, CMND cũ, thường trú được giải mã ở đây, nên chỉ
    gọi cho người có quyền sửa (Viewer không bao giờ vào form)."""
    data = {name: getattr(worker, name) for name in WORKER_FIELDS}
    identity = getattr(worker, "identity", None)
    if identity is not None:
        for name in IDENTITY_FIELDS:
            data[name] = getattr(identity, attr_name("workers.IdentityDocument", name))
    return data
