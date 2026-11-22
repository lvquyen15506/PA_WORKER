"""Form tải lên, thay thế và xác minh tài liệu."""

from django import forms
from django.core.exceptions import ValidationError

from apps.core.choices import DocumentVerificationStatus
from apps.core.models import DocumentType

from .validators import MAX_SIZE, validate_upload

FILE_HINT = "JPG, PNG, PDF, DOC hoặc DOCX; tối đa 10 MB."


class _FileForm(forms.Form):
    file = forms.FileField(
        label="Tệp",
        help_text=FILE_HINT,
        error_messages={"required": "Chọn tệp cần tải lên.", "empty": "Tệp rỗng."},
    )
    note = forms.CharField(
        label="Ghi chú", required=False, widget=forms.Textarea(attrs={"rows": 2}), max_length=1000
    )

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if uploaded.size > MAX_SIZE:
            raise ValidationError("Tệp vượt quá 10 MB.")
        validate_upload(uploaded)  # ném ValidationError tiếng Việt nếu không hợp lệ
        return uploaded


class UploadForm(_FileForm):
    document_type = forms.ModelChoiceField(
        label="Loại tài liệu",
        queryset=DocumentType.objects.none(),
        empty_label="— Chọn loại tài liệu —",
        error_messages={"required": "Chọn loại tài liệu."},
    )
    field_order = ["document_type", "file", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["document_type"].queryset = DocumentType.objects.filter(is_active=True)


class ReplaceForm(_FileForm):
    pass


class VerifyForm(forms.Form):
    status = forms.ChoiceField(
        label="Trạng thái xác minh",
        choices=DocumentVerificationStatus.choices,
        error_messages={"required": "Chọn trạng thái xác minh."},
    )
    note = forms.CharField(
        label="Ghi chú", required=False, widget=forms.Textarea(attrs={"rows": 2}), max_length=1000
    )
