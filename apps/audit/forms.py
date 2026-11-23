"""Bộ lọc trang /nhat-ky/ (trang.md 5.9): người thực hiện, hồ sơ, hành động, khoảng ngày."""

from django import forms

from apps.accounts.models import User
from apps.core.choices import AuditAction
from apps.core.formfields import date_field

SYSTEM = "he-thong"  # nhật ký do hệ thống tự ghi (user rỗng)


class AuditFilterForm(forms.Form):
    nguoi = forms.ChoiceField(label="Người thực hiện", required=False)
    ho_so = forms.CharField(
        label="Hồ sơ",
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "Mã hồ sơ hoặc mã nhân viên"}),
    )
    hanh_dong = forms.ChoiceField(
        label="Hành động", required=False, choices=[("", "Tất cả")] + AuditAction.choices
    )
    tu_ngay = date_field("Từ ngày")
    den_ngay = date_field("Đến ngày")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        users = User.objects.order_by("username")
        self.fields["nguoi"].choices = [("", "Tất cả"), (SYSTEM, "Hệ thống")] + [
            (str(u.pk), f"{u.username} – {u.full_name}") for u in users
        ]
