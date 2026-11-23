"""Dữ liệu mẫu cho trang /ui-kit/ (hư cấu hoàn toàn; số giấy tờ giả luôn bắt đầu bằng 999)."""

import datetime

from django import forms
from django.core.paginator import Paginator

from . import badges
from .choices import (
    DocumentVerificationStatus,
    Gender,
    RecruitmentStatus,
    VerificationStatus,
    WorkStatus,
)


class SampleForm(forms.Form):
    full_name = forms.CharField(
        label="Họ và tên", max_length=100, help_text="Nhập đúng như trên giấy tờ."
    )
    phone = forms.CharField(label="Số điện thoại", max_length=10)
    gender = forms.ChoiceField(
        label="Giới tính", choices=[("", "Chọn")] + list(Gender.choices), required=False
    )
    birth_date = forms.DateField(label="Ngày sinh", required=False, input_formats=["%d/%m/%Y"])
    id_number = forms.CharField(label="Số CCCD", required=False, max_length=12)
    address = forms.CharField(label="Địa chỉ thường trú", required=False)
    department = forms.ChoiceField(
        label="Bộ phận", required=False, disabled=True, choices=[("van-phong", "Văn phòng")]
    )
    note = forms.CharField(
        label="Ghi chú", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class SampleFilterForm(forms.Form):
    q = forms.CharField(label="Tìm kiếm", required=False)
    status = forms.ChoiceField(
        label="Trạng thái hồ sơ",
        required=False,
        choices=[("", "Tất cả")] + list(VerificationStatus.choices),
    )
    work_status = forms.ChoiceField(
        label="Trạng thái làm việc",
        required=False,
        choices=[("", "Tất cả")] + list(WorkStatus.choices),
    )
    date_from = forms.DateField(label="Từ ngày", required=False, input_formats=["%d/%m/%Y"])


class SampleReasonForm(forms.Form):
    reason = forms.CharField(
        label="Lý do",
        help_text="Không ghi họ tên, chỉ dùng mã hồ sơ.",
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    request_no = forms.CharField(label="Số hoặc ngày đơn yêu cầu")
    confirm_code = forms.CharField(
        label="Gõ lại mã hồ sơ để xác nhận",
        widget=forms.TextInput(attrs={"data-pa-match": "HS-DEMO-0001", "autocomplete": "off"}),
    )


def _forms():
    normal = SampleForm(
        initial={
            "full_name": "Trần Thị Mẫu",
            "phone": "0900000001",
            "gender": Gender.FEMALE.value,
            "department": "van-phong",
        },
        prefix="n",
    )
    errors = SampleForm(
        data={"e-full_name": "", "e-phone": "09000", "e-birth_date": "31/02/2000"}, prefix="e"
    )
    errors.is_valid()  # sinh lỗi mẫu
    intake = SampleForm(
        initial={"full_name": "Lê Văn Mẫu", "id_number": "999000000001", "address": ""}, prefix="i"
    )
    return normal, errors, intake


def _rows():
    names = [
        "Nguyễn Văn Mẫu", "Trần Thị Thử", "Lê Hoàng Giả", "Phạm Thị Demo", "Võ Minh Kiểm",
        "Đặng Quốc Mẫu", "Bùi Thị Thử", "Hồ Văn Giả", "Ngô Thị Demo", "Dương Văn Kiểm",
    ]  # fmt: skip
    ver = list(VerificationStatus)
    work = list(WorkStatus)
    rows = []
    for i, name in enumerate(names):
        rows.append(
            {
                "code": f"HS-DEMO-{i + 1:04d}",
                "name": name,
                "dept": "Văn phòng" if i % 3 else None,
                "salary": f"{(7 + i) * 1_000_000:,}".replace(",", "."),
                "joined": datetime.date(2026, 1 + i % 10, 5 + i),
                "ver": ver[i % len(ver)],
                "work": work[i % len(work)],
                "actions": [
                    {"kind": "link", "icon": "bi-eye", "tooltip": "Xem", "url": "#bang"},
                    {"kind": "link", "icon": "bi-pencil", "tooltip": "Sửa", "url": "#bang"},
                    {
                        "kind": "menu",
                        "label": "Thêm",
                        "items": [
                            {"label": "Xem lịch sử", "url": "#bang"},
                            {
                                "label": "Lưu trữ hồ sơ",
                                "post_url": "#",
                                "title": "Lưu trữ hồ sơ",
                                "message": f"Lưu trữ hồ sơ HS-DEMO-{i + 1:04d}?",
                                "danger": True,
                            },
                            {"label": "Tải xuống (không có quyền)", "disabled": True},
                        ],
                    },
                ],
            }
        )
    return rows


COLUMNS = [
    {"key": "code", "label": "Mã hồ sơ", "kind": "text", "nowrap": True},
    {"key": "name", "label": "Họ và tên", "kind": "text"},
    {"key": "dept", "label": "Bộ phận", "kind": "text"},
    {"key": "salary", "label": "Mức lương (đồng)", "kind": "num"},
    {"key": "joined", "label": "Ngày vào làm", "kind": "date"},
    {"key": "ver", "label": "Trạng thái hồ sơ", "kind": "badge"},
    {"key": "work", "label": "Trạng thái làm việc", "kind": "badge"},
    {"key": "actions", "label": "Thao tác", "kind": "actions"},
]


PICK_COLUMNS = [
    {"key": "pick", "label": "Chọn", "kind": "check", "name": "ids", "form": "form-demo-chon"},
    {"key": "code", "label": "Mã hồ sơ", "kind": "text", "nowrap": True},
    {"key": "basis", "label": "Căn cứ lưu trữ", "kind": "text"},
    {"key": "expires", "label": "Hết hạn lưu trữ", "kind": "date"},
    {"key": "count", "label": "Số công nhân", "kind": "link", "num": True},
]


def _pick_rows():
    basis = ["Công nhân đã nghỉ", "Ứng viên không được tuyển", "Hồ sơ bị từ chối"]
    return [
        {
            "pick": 100 + i,
            "code": f"HS-DEMO-{i + 1:04d}",
            "basis": basis[i % 3],
            "expires": datetime.date(2026, 1 + i, 10),
            "count": {"text": i * 3, "url": "#bang"},
            "disabled": i == 3,  # dòng không chọn được
        }
        for i in range(4)
    ]


def _status_groups():
    def group(title, choices):
        return {"title": title, "values": [c.value for c in choices]}

    return [
        group("Trạng thái hồ sơ", VerificationStatus),
        group("Trạng thái làm việc", WorkStatus),
        group("Trạng thái tuyển dụng", RecruitmentStatus),
        group("Trạng thái xác minh tài liệu (chỉ trong tab Tài liệu)", DocumentVerificationStatus),
        {
            "title": "Chỉ số tự tính",
            "values": [badges.MISSING_DOCS, badges.COMPLETE, badges.EXPIRING],
        },
        {
            "title": "Nhãn hiển thị (không phải bộ trạng thái)",
            "values": [
                badges.ACCOUNT_ACTIVE,
                badges.ACCOUNT_LOCKED,
                badges.ACCOUNT_TEMP_LOCKED,
                badges.CATALOG_ACTIVE,
                badges.CATALOG_STOPPED,
                badges.LOGIN_OK,
                badges.LOGIN_FAILED,
            ],
        },
    ]


def build_context():
    normal, errors, intake = _forms()
    paginator = Paginator(range(512), 20)
    return {
        "columns": COLUMNS,
        "rows": _rows(),
        "status_groups": _status_groups(),
        "form_normal": normal,
        "form_errors": errors,
        "form_intake": intake,
        "intake_meta": {
            "full_name": {"source": "QR"},
            "id_number": {"source": "QR"},
            "address": {"source": "OCR", "low_confidence": True},
        },
        "filter_form": SampleFilterForm(),
        "reason_form": SampleReasonForm(),
        "page_middle": paginator.page(3),
        "page_first": paginator.page(1),
        "page_last": paginator.page(paginator.num_pages),
        "view_items": [
            ("Họ và tên", "Nguyễn Văn Mẫu"),
            ("Ngày sinh", "05/01/1995"),
            ("Số CCCD", "999••••••001"),
            ("Địa chỉ thường trú", None),
        ],
        "tabs": [
            {"label": "Thông tin cá nhân", "url": "#tab", "active": True},
            {"label": "Tuyển dụng & CV", "url": "#tab", "active": False},
            {"label": "Quá trình làm việc", "url": "#tab", "active": False},
        ],
        "header_actions": [
            {"label": "Xuất Excel", "kind": "secondary", "url": "#dau-trang"},
            {"label": "Lưu trữ", "kind": "danger", "modal": "modal-simple"},
            {
                "label": "Gửi duyệt",
                "kind": "secondary",
                "disabled": True,
                "tooltip": "Chưa đủ thông tin",
            },
            {"label": "Lưu hồ sơ", "kind": "primary", "url": "#dau-trang"},
        ],
        "none_rows": [],
        "header_breadcrumbs": [("Hồ sơ công nhân", "#dau-trang"), ("HS-DEMO-0001", None)],
        "token_names": [
            "navy",
            "blue",
            "bg",
            "surface",
            "border",
            "text",
            "muted",
            "success",
            "warning",
            "danger",
        ],  # fmt: skip
        "spacings": [4, 8, 12, 16, 24, 32],
        "chart": {
            "type": "bar",
            "labels": ["T6", "T7", "T8", "T9", "T10", "T11"],
            "values": [18, 24, 31, 27, 35, 42],
            "unit": "hồ sơ",
        },
        "chart_group": {
            "type": "bar",
            "labels": ["T6", "T7", "T8", "T9", "T10", "T11"],
            "datasets": [
                {"label": "Vào làm", "values": [12, 15, 20, 14, 22, 25]},
                {"label": "Nghỉ việc", "values": [4, 6, 3, 8, 5, 7]},
            ],
            "unit": "người",
        },
        "chart_horizontal": {
            "type": "bar",
            "horizontal": True,
            "labels": ["Xưởng may", "Kho vận", "Khối văn phòng", "Chưa có bộ phận"],
            "values": [180, 96, 41, 17],
            "unit": "người",
        },
        "pick_columns": PICK_COLUMNS,
        "pick_rows": _pick_rows(),
    }
