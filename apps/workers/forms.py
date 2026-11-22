"""Form hồ sơ công nhân (docs/thiet-ke/trang.md mục 5.4). Quy tắc kiểm tra nằm ở
apps.workers.validation (dùng chung với service); form chỉ chuyển lỗi xuống từng ô."""

import datetime

from django import forms

from apps.audit.personal_fields import attr_name
from apps.core.choices import ConsentMethod, Gender, IdDocType
from apps.core.models import ApplicationSource, Position

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
REASON_HINT = "Không ghi họ tên, chỉ dùng mã hồ sơ."
CHECK_FIELDS = ("full_name", "phone", "date_of_birth", "id_number")  # kiểm tra trùng khi rời ô


def _date_field(label, **kwargs):
    return forms.DateField(
        label=label,
        required=False,
        input_formats=[DATE_FORMAT],
        widget=forms.DateInput(format=DATE_FORMAT, attrs={"placeholder": "dd/mm/yyyy"}),
        error_messages={"invalid": MSG_DATE},
        **kwargs,
    )


class WorkerForm(forms.Form):
    """Thông tin cá nhân và giấy tờ. Nháp chỉ bắt buộc họ tên + SĐT (câu 5); `level=SUBMISSION`
    (sửa hồ sơ Đã xác minh) bắt buộc thêm các trường của mục 4.3.

    `check_url`: địa chỉ HTMX kiểm tra trùng khi rời ô họ tên, SĐT, ngày sinh, số CCCD."""

    full_name = forms.CharField(
        label="Họ và tên", max_length=100, error_messages={"required": "Nhập họ và tên."}
    )
    phone = forms.CharField(
        label="Số điện thoại", max_length=20, error_messages={"required": "Nhập số điện thoại."}
    )
    date_of_birth = _date_field("Ngày sinh")
    gender = forms.ChoiceField(
        label="Giới tính", required=False, choices=[("", "Chọn")] + Gender.choices
    )
    nationality = forms.CharField(label="Quốc tịch", max_length=50, required=False)
    email = forms.CharField(label="Email", max_length=254, required=False)
    current_address = forms.CharField(label="Nơi ở hiện tại", max_length=255, required=False)
    id_doc_type = forms.ChoiceField(
        label="Loại giấy tờ", required=False, choices=[("", "Chọn")] + IdDocType.choices
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

    # Các nhóm trường hiển thị trên trang (tên nhóm, danh sách trường).
    SECTIONS = [
        (
            "Thông tin cá nhân",
            [
                "full_name",
                "phone",
                "date_of_birth",
                "gender",
                "nationality",
                "email",
                "current_address",
            ],
        ),
        (
            "Giấy tờ",
            [
                "id_doc_type",
                "id_number",
                "issue_date",
                "issue_place",
                "expiry_date",
                "old_id_number",
                "hometown",
                "birth_registration_place",
                "permanent_address",
            ],
        ),
        ("Khác", ["skills", "note"]),
    ]

    def __init__(self, *args, instance=None, level=DRAFT, check_url="", **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.level = level
        self.result = None
        if instance is not None and not self.is_bound:
            self.initial = {**worker_initial(instance), **self.initial}
        elif instance is None:
            self.initial.setdefault("nationality", "Việt Nam")
        if level == SUBMISSION:
            for name, message in SUBMISSION_REQUIRED.items():
                self.fields[name].required = True
                self.fields[name].error_messages["required"] = message
        if check_url:
            for name in CHECK_FIELDS:
                self.fields[name].widget.attrs.update(
                    {
                        "hx-post": check_url,
                        "hx-trigger": "blur changed",
                        "hx-target": "#duplicate-check",
                        "hx-swap": "innerHTML",
                        "hx-include": "closest form",
                    }
                )

    def sections(self):
        """[(tên nhóm, [BoundField])] để vẽ bằng _form_section."""
        return [(title, [self[name] for name in names]) for title, names in self.SECTIONS]

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
    full_name = forms.CharField(label="Họ tên người liên hệ", max_length=100, required=False)
    relationship = forms.CharField(label="Mối quan hệ", max_length=50, required=False)
    phone = forms.CharField(label="Số điện thoại", max_length=20, required=False)
    delete = forms.BooleanField(required=False, label="Xóa người liên hệ này")

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


# ----- Hộp lý do (gửi từ hộp xác nhận ở trang chi tiết) ---------------------------------------
class ReasonForm(forms.Form):
    """Lý do trả lại / từ chối / lưu trữ. Gợi ý không ghi họ tên (câu 30), không chặn lưu."""

    reason = forms.CharField(
        label="Lý do",
        help_text=REASON_HINT,
        widget=forms.Textarea(attrs={"rows": 2}),
        max_length=1000,
        error_messages={"required": "Nhập lý do."},
    )

    def __init__(self, *args, required=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason"].required = required


class AnonymizeForm(forms.Form):
    """Ẩn danh hóa theo yêu cầu (câu 38): lý do, số/ngày đơn, gõ lại mã hồ sơ."""

    reason = forms.CharField(
        label="Lý do",
        help_text=REASON_HINT,
        widget=forms.Textarea(attrs={"rows": 2}),
        max_length=1000,
        error_messages={"required": "Nhập lý do."},
    )
    request_ref = forms.CharField(
        label="Số hoặc ngày đơn yêu cầu",
        max_length=100,
        error_messages={"required": "Nhập số hoặc ngày đơn yêu cầu."},
    )
    confirm_code = forms.CharField(
        label="Gõ lại mã hồ sơ để xác nhận",
        error_messages={"required": "Gõ lại mã hồ sơ để xác nhận."},
    )

    def __init__(self, *args, worker=None, **kwargs):
        super().__init__(*args, **kwargs)
        if worker is not None:  # chỉ để bật nút ở giao diện; máy chủ kiểm tra lại
            self.fields["confirm_code"].widget.attrs.update(
                {"data-pa-match": worker.worker_code, "autocomplete": "off"}
            )


class ConsentForm(forms.Form):
    """Ghi nhận đồng ý xử lý dữ liệu. Ký giấy thì bắt buộc tệp biên bản đã ký."""

    consented = forms.TypedChoiceField(
        label="Kết quả",
        choices=[("1", "Đồng ý"), ("0", "Không đồng ý")],
        coerce=lambda v: v == "1",
        initial="1",
        error_messages={"required": "Chọn kết quả."},
    )
    consent_date = forms.DateField(
        label="Ngày đồng ý",
        input_formats=[DATE_FORMAT],
        widget=forms.DateInput(format=DATE_FORMAT, attrs={"placeholder": "dd/mm/yyyy"}),
        error_messages={"required": "Nhập ngày đồng ý.", "invalid": MSG_DATE},
    )
    method = forms.ChoiceField(
        label="Hình thức",
        choices=ConsentMethod.choices,
        error_messages={"required": "Chọn hình thức."},
    )
    file = forms.FileField(
        label="Biên bản đã ký",
        required=False,
        help_text="Bắt buộc khi chọn Ký giấy. JPG, PNG, PDF, DOC hoặc DOCX; tối đa 10 MB.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.setdefault("consent_date", datetime.date.today())

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("method") == ConsentMethod.PAPER and not cleaned.get("file"):
            self.add_error("file", "Ký giấy: tải lên tệp biên bản đã ký.")
        return cleaned


class ReopenForm(forms.Form):
    """Mở lại hồ sơ Lưu trữ: tạo lần ứng tuyển mới (câu 6)."""

    position = forms.ModelChoiceField(
        label="Vị trí ứng tuyển",
        queryset=Position.objects.none(),
        empty_label="Chọn vị trí",
        error_messages={"required": "Chọn vị trí ứng tuyển."},
    )
    source = forms.ModelChoiceField(
        label="Nguồn ứng tuyển",
        queryset=ApplicationSource.objects.none(),
        empty_label="Chọn nguồn",
        error_messages={"required": "Chọn nguồn ứng tuyển."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["position"].queryset = Position.objects.filter(is_active=True).order_by("name")
        self.fields["source"].queryset = ApplicationSource.objects.filter(is_active=True).order_by(
            "name"
        )
