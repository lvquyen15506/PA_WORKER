"""Form tài khoản (giao diện tạm, Phase 2)."""

from django import forms
from django.contrib.auth.forms import PasswordChangeForm

from .models import Role, User


class BootstrapMixin:
    """Gắn class Bootstrap cho ô nhập (giao diện tạm)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs.setdefault("class", css)


class LoginForm(forms.Form):
    username = forms.CharField(label="Tên đăng nhập", max_length=150)
    password = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput)


class ChangePasswordForm(BootstrapMixin, PasswordChangeForm):
    error_messages = {
        **PasswordChangeForm.error_messages,
        "password_incorrect": "Mật khẩu hiện tại không đúng.",
        "password_mismatch": "Hai mật khẩu mới không giống nhau.",
        "same_password": "Mật khẩu mới phải khác mật khẩu hiện tại.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Mật khẩu hiện tại"
        self.fields["new_password1"].label = "Mật khẩu mới"
        self.fields["new_password2"].label = "Nhập lại mật khẩu mới"
        self.fields["new_password1"].help_text = "Tối thiểu 8 ký tự, gồm cả chữ và số."

    def clean(self):
        cleaned = super().clean()
        old, new = cleaned.get("old_password"), cleaned.get("new_password1")
        if old and new and old == new:
            self.add_error("new_password1", self.error_messages["same_password"])
        return cleaned


class UserCreateForm(BootstrapMixin, forms.Form):
    username = forms.CharField(label="Tên đăng nhập", max_length=150)
    full_name = forms.CharField(label="Họ tên", max_length=100)
    role = forms.ModelChoiceField(label="Vai trò", queryset=Role.objects.order_by("id"))

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Tên đăng nhập này đã có.")
        return username


class UserEditForm(BootstrapMixin, forms.Form):
    full_name = forms.CharField(label="Họ tên", max_length=100)
    role = forms.ModelChoiceField(label="Vai trò", queryset=Role.objects.order_by("id"))

    def __init__(self, *args, editing_self=False, **kwargs):
        super().__init__(*args, **kwargs)
        if editing_self:  # Admin không tự đổi vai trò; máy chủ cũng kiểm tra lại
            self.fields["role"].disabled = True
            self.fields["role"].help_text = "Bạn không thể đổi vai trò của chính mình."


class LoginHistoryFilterForm(BootstrapMixin, forms.Form):
    username = forms.CharField(label="Tên đăng nhập", required=False)
    result = forms.ChoiceField(
        label="Kết quả",
        required=False,
        choices=[("", "Tất cả"), ("ok", "Thành công"), ("fail", "Thất bại")],
    )
    date_from = forms.DateField(label="Từ ngày", required=False, input_formats=["%d/%m/%Y"])
    date_to = forms.DateField(label="Đến ngày", required=False, input_formats=["%d/%m/%Y"])
