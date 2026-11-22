"""Danh sách hồ sơ: bộ lọc, tìm không dấu, sắp xếp (yeu-cau.md IV.7; trang.md mục 5.4).

Tên tham số trên URL là tiếng Việt không dấu, trùng với các liên kết của thẻ Dashboard ở trang.md
mục 5.3 (Phase 7 chỉ thêm các tham số riêng của Dashboard). Tìm theo số CCCD (12 chữ số) tra giá trị
băm và chỉ với Admin, Quản lý nhân sự, Nhân viên HR; Viewer nhập số CCCD thì chỉ được xử lý như chữ
thường, không biết hồ sơ có tồn tại hay không.
"""

import re

from django import forms
from django.db.models import F, OuterRef, Q, Subquery

from apps.core.choices import RecruitmentStatus, VerificationStatus, WorkStatus
from apps.core.crypto import compute_id_hash
from apps.core.models import Department, EducationLevel, Position, Section
from apps.core.text import compute_name_search
from apps.recruitment.models import Application, Education

from . import indicators
from .models import Worker
from .rules import ALL_STAFF, role_code

PAGE_SIZE = 20
DATE_FORMAT = "%d/%m/%Y"
ALL = [("", "Tất cả")]
YES = [("", "Tất cả"), ("1", "Có")]

# Giá trị sap_xep -> (nhãn, các cột ORDER BY). Giá trị trống = mới nhất trước.
SORTS = {
    "": ("Mới tạo trước", [F("id").desc()]),
    "ten": ("Họ tên A–Z", [F("name_search").asc(), F("id").asc()]),
    "-ten": ("Họ tên Z–A", [F("name_search").desc(), F("id").asc()]),
    "ma-nv": ("Mã NV tăng dần", [F("employee_code").asc(nulls_last=True), F("id").asc()]),
    "-ma-nv": ("Mã NV giảm dần", [F("employee_code").desc(nulls_last=True), F("id").asc()]),
    "ngay-sinh": ("Ngày sinh tăng dần", [F("date_of_birth").asc(nulls_last=True), F("id").asc()]),
    "-ngay-sinh": ("Ngày sinh giảm dần", [F("date_of_birth").desc(nulls_last=True), F("id").asc()]),
    "ngay-vao-lam": (
        "Ngày vào làm cũ nhất trước",
        [F("employment__start_date").asc(nulls_last=True), F("id").asc()],
    ),
    "-ngay-vao-lam": (
        "Ngày vào làm mới nhất trước",
        [F("employment__start_date").desc(nulls_last=True), F("id").asc()],
    ),
}


def _date(label):
    return forms.DateField(
        label=label,
        required=False,
        input_formats=[DATE_FORMAT],
        widget=forms.DateInput(format=DATE_FORMAT, attrs={"placeholder": "dd/mm/yyyy"}),
        error_messages={"invalid": "Nhập ngày đúng định dạng dd/mm/yyyy."},
    )


class WorkerFilterForm(forms.Form):
    q = forms.CharField(
        label="Tìm kiếm",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Mã, họ tên, số điện thoại"}),
    )
    phong_ban = forms.ModelChoiceField(
        label="Phòng ban", required=False, queryset=Department.objects.none(), empty_label="Tất cả"
    )
    bo_phan = forms.ModelChoiceField(
        label="Bộ phận", required=False, queryset=Section.objects.none(), empty_label="Tất cả"
    )
    chuc_danh = forms.ModelChoiceField(
        label="Chức danh", required=False, queryset=Position.objects.none(), empty_label="Tất cả"
    )
    trinh_do = forms.ModelChoiceField(
        label="Trình độ cao nhất",
        required=False,
        queryset=EducationLevel.objects.none(),
        empty_label="Tất cả",
    )
    trang_thai_ho_so = forms.ChoiceField(
        label="Trạng thái hồ sơ", required=False, choices=ALL + VerificationStatus.choices
    )
    trang_thai_lam_viec = forms.ChoiceField(
        label="Trạng thái làm việc", required=False, choices=ALL + WorkStatus.choices
    )
    trang_thai_tuyen_dung = forms.ChoiceField(
        label="Trạng thái tuyển dụng", required=False, choices=ALL + RecruitmentStatus.choices
    )
    thieu_giay_to = forms.ChoiceField(label="Thiếu giấy tờ", required=False, choices=YES)
    hoan_thien = forms.ChoiceField(label="Hoàn thiện", required=False, choices=YES)
    tiep_nhan_tu = _date("Tiếp nhận từ ngày")
    tiep_nhan_den = _date("Tiếp nhận đến ngày")
    sap_xep = forms.ChoiceField(
        label="Sắp xếp", required=False, choices=[(k, v[0]) for k, v in SORTS.items()]
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phong_ban"].queryset = Department.objects.order_by("sort_order", "name")
        self.fields["bo_phan"].queryset = Section.objects.select_related("department").order_by(
            "department__sort_order", "sort_order", "name"
        )
        self.fields["chuc_danh"].queryset = Position.objects.order_by("name")
        self.fields["trinh_do"].queryset = EducationLevel.objects.order_by("rank")


def _search_q(text, user):
    """Điều kiện tìm nhanh: mã hồ sơ, mã NV, họ tên không dấu, SĐT.

    Đủ 12 chữ số là số CCCD (tra giá trị băm), chỉ với người có quyền."""
    text = (text or "").strip()
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    if len(digits) == 12 and digits == re.sub(r"[\s.-]", "", text) and role_code(user) in ALL_STAFF:
        return Q(identity__id_number_hash=compute_id_hash(digits))
    condition = (
        Q(worker_code__icontains=text)
        | Q(employee_code__icontains=text)
        | Q(name_search__contains=compute_name_search(text))
    )
    if digits:
        condition |= Q(phone__contains=digits)
    return condition


def build_queryset(user, cleaned):
    """Queryset hồ sơ theo bộ lọc đã kiểm tra (cleaned_data của WorkerFilterForm)."""
    qs = Worker.objects.select_related("employment__section", "employment__position")

    search = _search_q(cleaned.get("q"), user)
    if search is not None:
        qs = qs.filter(search)
    if cleaned.get("phong_ban"):
        qs = qs.filter(employment__section__department=cleaned["phong_ban"])
    if cleaned.get("bo_phan"):
        qs = qs.filter(employment__section=cleaned["bo_phan"])
    if cleaned.get("chuc_danh"):
        qs = qs.filter(employment__position=cleaned["chuc_danh"])
    if cleaned.get("trang_thai_ho_so"):
        qs = qs.filter(verification_status=cleaned["trang_thai_ho_so"])
    if cleaned.get("trang_thai_lam_viec"):
        qs = qs.filter(employment__work_status=cleaned["trang_thai_lam_viec"])
    if cleaned.get("tiep_nhan_tu"):
        qs = qs.filter(employment__received_date__gte=cleaned["tiep_nhan_tu"])
    if cleaned.get("tiep_nhan_den"):
        qs = qs.filter(employment__received_date__lte=cleaned["tiep_nhan_den"])
    if cleaned.get("trinh_do"):
        # Trình độ cao nhất của mỗi người = bậc lớn nhất trong các dòng học vấn (câu 14).
        top = (
            Education.objects.filter(worker=OuterRef("pk"))
            .order_by("-education_level__rank")
            .values("education_level__rank")[:1]
        )
        qs = qs.annotate(top_rank=Subquery(top)).filter(top_rank=cleaned["trinh_do"].rank)
    if cleaned.get("trang_thai_tuyen_dung"):
        # Xét lần ứng tuyển gần nhất [Nội bộ].
        latest = Application.objects.filter(worker=OuterRef("pk")).order_by("-applied_date", "-id")
        qs = qs.annotate(latest_application=Subquery(latest.values("status")[:1])).filter(
            latest_application=cleaned["trang_thai_tuyen_dung"]
        )
    if cleaned.get("thieu_giay_to") or cleaned.get("hoan_thien"):
        qs = indicators.annotate_documents(qs)  # chỉ thêm cột một lần dù dùng cả hai bộ lọc
    if cleaned.get("thieu_giay_to"):
        qs = qs.filter(missing_documents=True)
    if cleaned.get("hoan_thien"):  # Hoàn thiện = Đã xác minh và không thiếu giấy tờ
        qs = qs.filter(verification_status=VerificationStatus.VERIFIED, missing_documents=False)
    return qs.order_by(*SORTS[cleaned.get("sap_xep") or ""][1])
