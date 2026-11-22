"""Form nhập từ CCCD và CV (docs/thiet-ke/trang.md mục 5.6, phac-thao-trang.md mục 4)."""

from django import forms

from apps.core.choices import IdDocType
from apps.core.models import EducationLevel
from apps.workers.forms import _date_field

AUTO = ""
MSG_NEED_FILE = "Chọn ít nhất một tệp: ảnh mặt trước, ảnh mặt sau hoặc CV."


class IntakeUploadForm(forms.Form):
    front_image = forms.FileField(
        label="Ảnh mặt trước CCCD",
        required=False,
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png"}),
    )
    back_image = forms.FileField(
        label="Ảnh mặt sau CCCD",
        required=False,
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png"}),
    )
    cv_file = forms.FileField(
        label="CV (PDF, DOC, DOCX, JPG, PNG)",
        required=False,
        help_text="Tối đa 10 MB mỗi tệp. Ảnh nhận JPG hoặc PNG.",
        widget=forms.FileInput(attrs={"accept": ".pdf,.doc,.docx,.jpg,.jpeg,.png"}),
    )
    doc_type = forms.ChoiceField(
        label="Loại giấy tờ",
        required=False,
        choices=[(AUTO, "Tự nhận biết")] + IdDocType.choices,
        help_text="Để Tự nhận biết nếu chưa chắc. Chọn tay thì hệ thống dùng đúng mẫu thẻ đó.",
    )

    def clean(self):
        cleaned = super().clean()
        if not any(cleaned.get(n) for n in ("front_image", "back_image", "cv_file")):
            raise forms.ValidationError(MSG_NEED_FILE)
        return cleaned


class CvViewForm(forms.Form):
    """Ô chỉ đọc hiện văn bản trích từ CV để HR bôi đen đoạn chữ rồi "Đưa vào trường…"."""

    cv_text = forms.CharField(
        label="Văn bản trích từ CV",
        required=False,
        widget=forms.Textarea(attrs={"rows": 12, "readonly": True}),
    )


# ----- Các khối nhập từ CV: vài trường tối thiểu, HR sửa tay (không tự tạo thông tin) -----


def _filled(cleaned):
    return any(v not in (None, "") for k, v in cleaned.items())


class EducationRowForm(forms.Form):
    education_level = forms.ModelChoiceField(
        label="Trình độ",
        required=False,
        queryset=EducationLevel.objects.filter(is_active=True).order_by("rank"),
        empty_label="Chọn trình độ",
    )
    school_name = forms.CharField(label="Tên trường", max_length=200, required=False)
    major = forms.CharField(label="Chuyên ngành", max_length=200, required=False)
    start_year = forms.IntegerField(label="Từ năm", required=False, min_value=1950, max_value=2100)
    end_year = forms.IntegerField(label="Đến năm", required=False, min_value=1950, max_value=2100)

    def clean(self):
        cleaned = super().clean()
        if _filled(cleaned):
            if not cleaned.get("school_name") and "school_name" not in self.errors:
                self.add_error("school_name", "Nhập tên trường.")
            if not cleaned.get("education_level") and "education_level" not in self.errors:
                self.add_error("education_level", "Chọn trình độ học vấn.")
            start, end = cleaned.get("start_year"), cleaned.get("end_year")
            if start and end and start > end:
                self.add_error("end_year", "Năm kết thúc phải sau hoặc bằng năm bắt đầu.")
        return cleaned


class ExperienceRowForm(forms.Form):
    company_name = forms.CharField(label="Công ty", max_length=200, required=False)
    job_title = forms.CharField(label="Chức danh", max_length=200, required=False)
    start_date = _date_field("Từ ngày")
    end_date = _date_field("Đến ngày")
    description = forms.CharField(
        label="Mô tả", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def clean(self):
        cleaned = super().clean()
        if _filled(cleaned):
            if not cleaned.get("company_name") and "company_name" not in self.errors:
                self.add_error("company_name", "Nhập tên công ty.")
            start, end = cleaned.get("start_date"), cleaned.get("end_date")
            if start and end and start > end:
                self.add_error("end_date", "Ngày kết thúc phải sau hoặc bằng ngày bắt đầu.")
        return cleaned


class CertificateRowForm(forms.Form):
    name = forms.CharField(label="Tên chứng chỉ", max_length=200, required=False)
    issuer = forms.CharField(label="Nơi cấp", max_length=200, required=False)
    issue_date = _date_field("Ngày cấp")

    def clean(self):
        cleaned = super().clean()
        if _filled(cleaned) and not cleaned.get("name") and "name" not in self.errors:
            self.add_error("name", "Nhập tên chứng chỉ.")
        return cleaned


EducationFormSet = forms.formset_factory(EducationRowForm, extra=1, max_num=5)
ExperienceFormSet = forms.formset_factory(ExperienceRowForm, extra=1, max_num=5)
CertificateFormSet = forms.formset_factory(CertificateRowForm, extra=1, max_num=5)


def filled_rows(formset):
    """Các dòng có dữ liệu (dict đã kiểm tra); dòng trống bị bỏ."""
    rows = []
    for form in formset.forms:
        data = getattr(form, "cleaned_data", None) or {}
        if _filled(data):
            rows.append({k: v for k, v in data.items() if v not in (None, "")})
    return rows
