"""Form tuyển dụng (trang.md mục 5.7): lần ứng tuyển, học vấn, chứng chỉ, kinh nghiệm, bộ lọc.

Quy tắc kiểm tra nằm ở apps.recruitment.services (kiểm tra ở máy chủ); form chỉ lấy dữ liệu và
đưa lỗi từ service xuống từng ô."""

from django import forms

from apps.core.choices import RecruitmentStatus
from apps.core.formfields import REASON_HINT, active_or_current, date_field, datetime_field
from apps.core.models import ApplicationSource, EducationLevel, Position


class ApplicationForm(forms.Form):
    position = forms.ModelChoiceField(
        label="Vị trí ứng tuyển",
        queryset=Position.objects.none(),
        empty_label="— Chọn —",
        error_messages={"required": "Chọn vị trí ứng tuyển."},
    )
    source = forms.ModelChoiceField(
        label="Nguồn ứng tuyển",
        queryset=ApplicationSource.objects.none(),
        empty_label="— Chọn —",
        error_messages={"required": "Chọn nguồn ứng tuyển."},
    )
    applied_date = date_field("Ngày ứng tuyển", required=True)
    expected_salary = forms.IntegerField(
        label="Mức lương mong muốn (đồng)",
        required=False,
        min_value=0,
        error_messages={
            "invalid": "Nhập số nguyên, không có dấu chấm hay chữ.",
            "min_value": "Mức lương mong muốn phải là số không âm.",
        },
    )
    available_date = date_field("Ngày có thể nhận việc")
    status = forms.ChoiceField(
        label="Trạng thái tuyển dụng",
        choices=RecruitmentStatus.choices,
        initial=RecruitmentStatus.NEW,
    )
    interview_at = datetime_field("Thời gian phỏng vấn")
    interview_notes = forms.CharField(
        label="Ghi chú phỏng vấn", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    result_date = date_field("Ngày có kết quả")
    reject_reason = forms.CharField(
        label="Lý do không đạt",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=REASON_HINT,
    )

    def __init__(self, *args, instance=None, **kwargs):
        if instance is not None and not args and "data" not in kwargs:
            kwargs.setdefault("initial", self.initial_from(instance))
        super().__init__(*args, **kwargs)
        self.fields["position"].queryset = active_or_current(
            Position.objects.order_by("name"), instance.position if instance else None
        )
        self.fields["source"].queryset = active_or_current(
            ApplicationSource.objects.order_by("name"), instance.source if instance else None
        )
        self.fields["status"].help_text = (
            "Hẹn phỏng vấn cần thời gian phỏng vấn; Đạt, Không đạt, Ứng viên từ chối cần ngày có "
            "kết quả (mặc định hôm nay); Không đạt cần lý do."
        )

    @staticmethod
    def initial_from(app):
        import django.utils.timezone as tz

        interview = tz.localtime(app.interview_at) if app.interview_at else None
        return {
            "position": app.position_id,
            "source": app.source_id,
            "applied_date": app.applied_date,
            "expected_salary": int(app.expected_salary)
            if app.expected_salary is not None
            else None,
            "available_date": app.available_date,
            "status": app.status,
            "interview_at": interview,
            "interview_notes": app.interview_notes,
            "result_date": app.result_date,
            "reject_reason": app.reject_reason,
        }

    def service_data(self):
        return dict(self.cleaned_data)


class EducationForm(forms.Form):
    education_level = forms.ModelChoiceField(
        label="Trình độ",
        queryset=EducationLevel.objects.none(),
        empty_label="— Chọn —",
        error_messages={"required": "Chọn trình độ học vấn."},
    )
    school_name = forms.CharField(
        label="Trường", max_length=200, error_messages={"required": "Nhập tên trường."}
    )
    major = forms.CharField(label="Ngành", max_length=200, required=False)
    start_year = forms.IntegerField(label="Từ năm", required=False)
    end_year = forms.IntegerField(label="Đến năm", required=False)
    note = forms.CharField(
        label="Ghi chú", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, instance=None, **kwargs):
        if instance is not None and not args and "data" not in kwargs:
            kwargs.setdefault(
                "initial",
                {
                    "education_level": instance.education_level_id,
                    "school_name": instance.school_name,
                    "major": instance.major,
                    "start_year": instance.start_year,
                    "end_year": instance.end_year,
                    "note": instance.note,
                },
            )
        super().__init__(*args, **kwargs)
        self.fields["education_level"].queryset = active_or_current(
            EducationLevel.objects.order_by("rank"), instance.education_level if instance else None
        )

    def service_data(self):
        return dict(self.cleaned_data)


class CertificateForm(forms.Form):
    name = forms.CharField(
        label="Tên chứng chỉ", max_length=200, error_messages={"required": "Nhập tên chứng chỉ."}
    )
    issuer = forms.CharField(label="Nơi cấp", max_length=200, required=False)
    issue_date = date_field("Ngày cấp")
    expiry_date = date_field("Ngày hết hạn")
    note = forms.CharField(
        label="Ghi chú", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, instance=None, **kwargs):
        if instance is not None and not args and "data" not in kwargs:
            kwargs.setdefault(
                "initial",
                {
                    f: getattr(instance, f)
                    for f in ("name", "issuer", "issue_date", "expiry_date", "note")
                },
            )
        super().__init__(*args, **kwargs)

    def service_data(self):
        return dict(self.cleaned_data)


class ExperienceForm(forms.Form):
    company_name = forms.CharField(
        label="Công ty", max_length=200, error_messages={"required": "Nhập tên công ty."}
    )
    job_title = forms.CharField(label="Chức danh", max_length=200, required=False)
    start_date = date_field("Từ ngày")
    end_date = date_field("Đến ngày")
    description = forms.CharField(
        label="Mô tả", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, instance=None, **kwargs):
        if instance is not None and not args and "data" not in kwargs:
            kwargs.setdefault(
                "initial",
                {
                    f: getattr(instance, f)
                    for f in ("company_name", "job_title", "start_date", "end_date", "description")
                },
            )
        super().__init__(*args, **kwargs)

    def service_data(self):
        return dict(self.cleaned_data)


class RecruitmentFilterForm(forms.Form):
    """Bộ lọc /tuyen-dung/. `trang_thai` nhận một mã hoặc danh sách cách nhau bằng dấu phẩy (liên
    kết thẻ "Đang tuyển dụng" của Dashboard: NEW,SCREENING,INTERVIEW)."""

    trang_thai = forms.CharField(
        label="Trạng thái tuyển dụng",
        required=False,
        widget=forms.Select(choices=[("", "Tất cả")] + RecruitmentStatus.choices),
    )
    vi_tri = forms.ModelChoiceField(
        label="Vị trí", required=False, queryset=Position.objects.none(), empty_label="Tất cả"
    )
    nguon = forms.ModelChoiceField(
        label="Nguồn",
        required=False,
        queryset=ApplicationSource.objects.none(),
        empty_label="Tất cả",
    )
    tu_ngay = date_field("Ứng tuyển từ ngày")
    den_ngay = date_field("Ứng tuyển đến ngày")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vi_tri"].queryset = Position.objects.order_by("name")
        self.fields["nguon"].queryset = ApplicationSource.objects.order_by("name")

    def statuses(self):
        raw = (self.cleaned_data.get("trang_thai") or "").split(",")
        return [s for s in (x.strip() for x in raw) if s in RecruitmentStatus.values]
