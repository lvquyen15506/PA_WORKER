"""Trang nhập hồ sơ từ file Excel `/ho-so/nhap-excel/` và tải file mẫu (trang.md 5.4).

Admin, Quản lý nhân sự, Nhân viên HR vào được (Viewer 403). Phần thông tin làm việc (cột B) do bộ
nhập kiểm tra vai trò từng dòng: HR nhập dòng có phần B thì dòng đó báo lỗi.
"""

from django import forms
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.permissions import role_required
from apps.core import excel
from apps.workers.rules import ALL_STAFF

from . import excel_template, importer

STAFF = tuple(ALL_STAFF)
RESULT_COLUMNS = [
    {"key": "row", "label": "Dòng", "kind": "num"},
    {"key": "column", "label": "Cột", "kind": "text"},
    {"key": "message", "label": "Nội dung", "kind": "text"},
]


class ImportForm(forms.Form):
    file = forms.FileField(
        label="Tệp Excel (.xlsx)",
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "accept": ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            }
        ),
        help_text="Dùng file mẫu. Tối đa 10 MB và 1.000 dòng mỗi lần.",
    )


def _rows(issues):
    return [{"row": i.row, "column": i.column, "message": i.message} for i in issues]


@role_required(*STAFF)
@require_http_methods(["GET", "POST"])
def import_page(request):
    form = ImportForm()
    result = None
    if request.method == "POST":
        form = ImportForm(request.POST, request.FILES)
        upload = request.FILES.get("file")
        if upload is None:
            form.is_valid()
            form.add_error("file", "Chọn tệp Excel để nhập.")
        else:
            data = upload.read(importer.MAX_BYTES + 1)
            result = importer.import_workbook(request.user, data, request=request)
    return render(
        request,
        "reports/import.html",
        {
            "form": form,
            "result": result,
            "error_rows": _rows(result.errors) if result else [],
            "warning_rows": _rows(result.warnings) if result else [],
            "columns": RESULT_COLUMNS,
            "today": timezone.localdate().strftime("%d/%m/%Y"),
            "max_rows": importer.MAX_ROWS,
            "crumbs": [
                ("Hồ sơ công nhân", "/ho-so/"),
                ("Thêm hồ sơ", "/ho-so/them/"),
                ("Từ file Excel", None),
            ],
        },
    )


@role_required(*STAFF)
@require_GET
def template_download(request):
    return excel.xlsx_response(excel_template.build_template(), "File-mau-nhap-ho-so.xlsx")
