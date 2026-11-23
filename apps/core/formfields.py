"""Trường form dùng chung: ngày dd/mm/yyyy, ngày giờ, ô chọn danh mục chỉ lấy mục đang dùng."""

from django import forms
from django.db.models import Q

DATE_FORMAT = "%d/%m/%Y"
DATETIME_FORMAT = "%d/%m/%Y %H:%M"
MSG_DATE = "Nhập ngày đúng định dạng dd/mm/yyyy."
MSG_DATETIME = "Nhập giờ đúng định dạng dd/mm/yyyy hh:mm."
REASON_HINT = "Không ghi họ tên, chỉ dùng mã hồ sơ."


def date_field(label, *, required=False, **kwargs):
    return forms.DateField(
        label=label,
        required=required,
        input_formats=[DATE_FORMAT],
        widget=forms.DateInput(format=DATE_FORMAT, attrs={"placeholder": "dd/mm/yyyy"}),
        error_messages={"invalid": MSG_DATE, "required": f"Nhập {label.lower()}."},
        **kwargs,
    )


def datetime_field(label, *, required=False, **kwargs):
    return forms.DateTimeField(
        label=label,
        required=required,
        input_formats=[DATETIME_FORMAT],
        widget=forms.DateTimeInput(
            format=DATETIME_FORMAT, attrs={"placeholder": "dd/mm/yyyy hh:mm"}
        ),
        error_messages={"invalid": MSG_DATETIME, "required": f"Nhập {label.lower()}."},
        **kwargs,
    )


def active_or_current(queryset, current=None):
    """Ô chọn khi tạo/sửa: chỉ mục đang dùng, cộng mục hiện tại của bản ghi (dữ liệu cũ)."""
    condition = Q(is_active=True)
    if current is not None:
        condition |= Q(pk=current.pk)
    return queryset.filter(condition)
