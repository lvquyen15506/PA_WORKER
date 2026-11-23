"""Template tag/filter dùng chung cho giao diện (skill pa-ui)."""

from django import template
from django.conf import settings
from django.utils.html import format_html

from apps.core import badges

register = template.Library()


@register.simple_tag
def app_version():
    """Phiên bản phần mềm (một nguồn: settings.APP_VERSION). Dùng được cả ở trang lỗi 500
    (không có context processor)."""
    return settings.APP_VERSION


@register.filter
def status_badge(value, label=None):
    """{{ "PENDING"|status_badge }} -> nhãn màu theo bảng ở pa-ui mục 5.

    `label` (tùy chọn) thay chữ hiển thị, giữ nguyên màu. Ví dụ:
    {{ "account_temp_locked"|status_badge:"Khóa tạm đến 14:05" }}.
    """
    text, color = badges.lookup(value)
    return format_html('<span class="pa-badge pa-badge--{}">{}</span>', color, label or text)


@register.filter
def get_item(mapping, key):
    """Lấy mapping[key] trong template; không có thì None."""
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def is_wide(bound_field):
    """Trường nhiều dòng chiếm cả hàng trong lưới 2 cột."""
    return bound_field.field.widget.__class__.__name__ == "Textarea"


@register.filter
def pa_widget(bound_field, extra=""):
    """Vẽ ô nhập của một BoundField kèm class Bootstrap; thêm is-invalid khi có lỗi."""
    widget = bound_field.field.widget
    name = widget.__class__.__name__
    if name in ("Select", "SelectMultiple"):
        css = "form-select"
    elif name in ("CheckboxInput",):
        css = "form-check-input"
    else:
        css = "form-control"
    if bound_field.errors:
        css += " is-invalid"
    if extra:
        css += f" {extra}"
    return bound_field.as_widget(attrs={"class": css})
