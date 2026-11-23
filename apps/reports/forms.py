"""Bộ lọc trang /bao-cao/ (trang.md 5.9): loại báo cáo, khoảng ngày, phòng ban."""

from django import forms
from django.forms.models import ModelChoiceIterator
from django.utils import timezone

from apps.core.formfields import date_field
from apps.core.models import Department

from . import reports, stats

MAX_MONTHS = 60


class _DepartmentIterator(ModelChoiceIterator):
    """Ô chọn phòng ban có thêm "Chưa có bộ phận" (câu 48) ngay sau "Tất cả"."""

    def __iter__(self):
        yield ("", self.field.empty_label)
        yield (DepartmentFilterField.NONE, stats.NO_SECTION)
        for obj in self.queryset:
            yield self.choice(obj)


class DepartmentFilterField(forms.ModelChoiceField):
    NONE = "chua-co"
    iterator = _DepartmentIterator

    def to_python(self, value):
        return self.NONE if value == self.NONE else super().to_python(value)

    def validate(self, value):
        if value != self.NONE:
            super().validate(value)


class ReportFilterForm(forms.Form):
    loai = forms.ChoiceField(
        label="Loại báo cáo", choices=[(r.code, r.title) for r in reports.REPORTS], required=False
    )
    tu_ngay = date_field("Từ ngày")  # chỉ áp cho báo cáo theo tháng (ghi ở dòng phạm vi)
    den_ngay = date_field("Đến ngày")
    phong_ban = DepartmentFilterField(
        label="Phòng ban", required=False, queryset=Department.objects.none(), empty_label="Tất cả"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phong_ban"].queryset = Department.objects.order_by("sort_order", "name")

    def clean(self):
        data = super().clean()
        start, end = data.get("tu_ngay"), data.get("den_ngay")
        default_start, default_end = stats.last_12_months(timezone.localdate())
        start, end = start or default_start, end or default_end
        if start > end:
            self.add_error("den_ngay", "Đến ngày phải sau hoặc bằng từ ngày.")
        elif len(stats.months_between(start, end)) > MAX_MONTHS:
            self.add_error("den_ngay", f"Khoảng thời gian tối đa {MAX_MONTHS} tháng.")
        return data

    def context(self):
        """Tham số đã chuẩn hóa để dựng báo cáo (giá trị lỗi/để trống thì dùng mặc định)."""
        default_start, default_end = stats.last_12_months(timezone.localdate())
        data = self.cleaned_data if self.is_bound else {}
        # Ngày sai (từng ô hoặc đảo ngược) thì dùng khoảng mặc định; phòng ban và loại báo cáo hợp
        # lệ vẫn được giữ để số liệu khớp với ô chọn đang hiện.
        dates_ok = not ({"tu_ngay", "den_ngay"} & set(self.errors))
        start = (data.get("tu_ngay") if dates_ok else None) or default_start
        end = (data.get("den_ngay") if dates_ok else None) or default_end
        code = data.get("loai") or reports.REPORTS[0].code
        department = data.get("phong_ban") or None
        if department == DepartmentFilterField.NONE:
            department = stats.NO_SECTION
        return reports.ReportContext(code=code, start=start, end=end, department=department)
