"""Danh mục ở trang Cài đặt (trang.md mục 5.2): 10 loại khai báo MỘT chỗ.

Mỗi loại có thêm, sửa, ngừng sử dụng, dùng lại; không có xóa (mục đã dùng thì chỉ ngừng). Mục
ngừng sử dụng không hiện trong ô chọn khi tạo mới nhưng vẫn hiện ở dữ liệu cũ. Tên được chuẩn hóa
khoảng trắng khi lưu; trùng tên trong cùng phạm vi bị chặn khi so không phân biệt hoa thường và
khoảng trắng thừa (giữ dấu). Công ty khách còn có cảnh báo "Có thể trùng" khi tên chỉ trùng lúc
bỏ dấu (câu 48).
"""

from dataclasses import dataclass, field

from django import forms

from .formfields import active_or_current
from .models import (
    ApplicationSource,
    ClientCompany,
    Department,
    DocumentType,
    EducationLevel,
    Position,
    RequiredDocumentGroup,
    Section,
    Shift,
    Team,
)
from .text import collapse_spaces, compute_name_search, normalize_key

MSG_DUPLICATE = "Đã có {noun} này trong danh mục."
MSG_DUPLICATE_CLIENT = "Đã có công ty khách này ở địa điểm này trong danh mục."
MSG_SYSTEM_TYPE = "Loại tài liệu này được phần mềm sử dụng nên không ngừng sử dụng được."


@dataclass(frozen=True)
class Catalog:
    slug: str
    title: str  # tên loại danh mục, viết hoa chữ đầu: "Phòng ban"
    noun: str  # dùng trong câu: "Thêm phòng ban"
    model: type
    fields: tuple
    # (khóa, nhãn cột, hàm lấy giá trị) cho bảng danh sách, trước cột Trạng thái.
    columns: tuple
    # Các trường xác định "trùng": tên + phạm vi cha (bộ phận trong phòng ban...).
    unique_on: tuple = ("name",)
    help_texts: dict = field(default_factory=dict)


def _name(obj):
    return obj.name


CATALOGS = [
    Catalog(
        "phong-ban",
        "Phòng ban",
        "phòng ban",
        Department,
        ("name", "sort_order"),
        (("name", "Tên phòng ban", _name), ("sort_order", "Thứ tự", lambda o: o.sort_order)),
    ),
    Catalog(
        "bo-phan",
        "Bộ phận",
        "bộ phận",
        Section,
        ("department", "name", "sort_order"),
        (
            ("name", "Tên bộ phận", _name),
            ("department", "Phòng ban", lambda o: o.department.name),
            ("sort_order", "Thứ tự", lambda o: o.sort_order),
        ),
        unique_on=("department", "name"),
    ),
    Catalog(
        "to",
        "Tổ",
        "tổ",
        Team,
        ("section", "name", "sort_order"),
        (
            ("name", "Tên tổ", _name),
            ("section", "Bộ phận", lambda o: f"{o.section.name} ({o.section.department.name})"),
            ("sort_order", "Thứ tự", lambda o: o.sort_order),
        ),
        unique_on=("section", "name"),
    ),
    Catalog(
        "chuc-danh",
        "Chức danh",
        "chức danh",
        Position,
        ("name",),
        (("name", "Tên chức danh", _name),),
    ),
    Catalog(
        "ca",
        "Ca làm việc",
        "ca làm việc",
        Shift,
        ("name", "time_range"),
        (("name", "Tên ca", _name), ("time_range", "Khung giờ", lambda o: o.time_range)),
        help_texts={"time_range": "Ví dụ 06:00-14:00."},
    ),
    Catalog(
        "nguon-ung-tuyen",
        "Nguồn ứng tuyển",
        "nguồn ứng tuyển",
        ApplicationSource,
        ("name",),
        (("name", "Nguồn ứng tuyển", _name),),
    ),
    Catalog(
        "trinh-do",
        "Trình độ học vấn",
        "trình độ",
        EducationLevel,
        ("name", "rank"),
        (("name", "Trình độ", _name), ("rank", "Cấp bậc", lambda o: o.rank)),
        help_texts={"rank": "Số lớn hơn là trình độ cao hơn (dùng để tính trình độ cao nhất)."},
    ),
    Catalog(
        "nhom-tai-lieu",
        "Nhóm tài liệu bắt buộc",
        "nhóm tài liệu",
        RequiredDocumentGroup,
        ("name", "sort_order"),
        (("name", "Nhóm tài liệu", _name), ("sort_order", "Thứ tự", lambda o: o.sort_order)),
    ),
    Catalog(
        "loai-tai-lieu",
        "Loại tài liệu",
        "loại tài liệu",
        DocumentType,
        ("name", "required_group", "sort_order"),
        (
            ("name", "Loại tài liệu", _name),
            ("code", "Mã", lambda o: o.system_code),
            (
                "group",
                "Nhóm bắt buộc",
                lambda o: o.required_group.name if o.required_group else None,
            ),
            ("sort_order", "Thứ tự", lambda o: o.sort_order),
        ),
        help_texts={"required_group": "Để trống nếu loại này không thuộc nhóm bắt buộc nào."},
    ),
    Catalog(
        "cong-ty-khach",
        "Công ty khách hàng",
        "công ty khách",
        ClientCompany,
        ("name", "location"),
        (("name", "Tên công ty", _name), ("location", "Địa điểm", lambda o: o.location)),
        unique_on=("name", "location"),
        help_texts={
            "name": "Mỗi địa điểm của cùng một công ty là một dòng riêng.",
            "location": "Tỉnh hoặc thành phố.",
        },
    ),
]
BY_SLUG = {c.slug: c for c in CATALOGS}


def _key(value):
    """Giá trị dùng để so trùng: chữ thì chuẩn hóa, đối tượng thì theo pk."""
    if hasattr(value, "pk"):
        return value.pk
    return normalize_key(value) if isinstance(value, str) else value


def find_duplicate(catalog, values, exclude_pk=None):
    """Dòng khác trùng tên trong cùng phạm vi (không phân biệt hoa thường, khoảng trắng thừa)."""
    target = tuple(_key(values.get(name)) for name in catalog.unique_on)
    qs = catalog.model.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    for obj in qs:
        if tuple(_key(getattr(obj, name)) for name in catalog.unique_on) == target:
            return obj
    return None


def similar_client_companies(name, exclude_pk=None):
    """Công ty khách có tên chỉ trùng khi bỏ dấu (khác khi so giữ dấu): cảnh báo, không chặn."""
    plain, exact = compute_name_search(name), normalize_key(name)
    if not plain:
        return []
    qs = ClientCompany.objects.order_by("name", "location")
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return [
        c for c in qs if compute_name_search(c.name) == plain and normalize_key(c.name) != exact
    ]


class CatalogForm(forms.ModelForm):
    catalog = None  # gán khi tạo lớp qua catalog_form_class

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, f in self.fields.items():
            if isinstance(f, forms.ModelChoiceField):
                current = getattr(self.instance, name, None) if self.instance.pk else None
                f.queryset = active_or_current(f.queryset, current)
                f.empty_label = "— Chọn —" if f.required else "Không thuộc nhóm nào"
            if name in self.catalog.help_texts:
                f.help_text = self.catalog.help_texts[name]

    def clean(self):
        cleaned = super().clean()
        for name, value in list(cleaned.items()):
            if isinstance(value, str):
                cleaned[name] = collapse_spaces(value)
        if self.errors:
            return cleaned
        duplicate = find_duplicate(self.catalog, cleaned, exclude_pk=self.instance.pk)
        if duplicate is not None:
            message = (
                MSG_DUPLICATE_CLIENT
                if self.catalog.model is ClientCompany
                else MSG_DUPLICATE.format(noun=self.catalog.noun)
            )
            # Gắn lỗi vào ô tên nên Django bỏ qua kiểm tra unique trùng lặp của chính ô đó
            # (validate_unique loại các trường đã có lỗi); các unique khác (cấp bậc) vẫn chạy.
            self.add_error("name", message)
        return cleaned


def catalog_form_class(catalog):
    return forms.modelform_factory(
        catalog.model,
        form=type(f"{catalog.model.__name__}CatalogForm", (CatalogForm,), {"catalog": catalog}),
        fields=catalog.fields,
    )
