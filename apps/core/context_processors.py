"""Menu sidebar theo vai trò (docs/thiet-ke/trang.md mục 2). Kiểm tra quyền thật vẫn ở từng view."""

from .choices import RoleCode

A, Q, H, V = (
    RoleCode.ADMIN.value,
    RoleCode.HR_MANAGER.value,
    RoleCode.HR_STAFF.value,
    RoleCode.VIEWER.value,
)

# (nhãn, icon, URL, các vai trò thấy)
MENU = [
    ("Tổng quan", "bi-speedometer2", "/", {A, Q, H, V}),
    ("Hồ sơ công nhân", "bi-people", "/ho-so/", {A, Q, H, V}),
    ("Thêm hồ sơ", "bi-person-plus", "/ho-so/them/", {A, Q, H}),
    ("Tuyển dụng", "bi-briefcase", "/tuyen-dung/", {A, Q, H, V}),
    ("Duyệt hồ sơ", "bi-check2-square", "/duyet-ho-so/", {A, Q}),
    ("Báo cáo", "bi-bar-chart", "/bao-cao/", {A, Q, H, V}),
    ("Nhật ký thao tác", "bi-clock-history", "/nhat-ky/", {A, Q}),
    # v1.1.1: lối tắt tới danh mục công ty khách (Q chỉ xem, A thêm/sửa)
    ("Công ty khách", "bi-building", "/cai-dat/danh-muc/cong-ty-khach/", {A, Q}),
    ("Tài khoản", "bi-person-gear", "/tai-khoan/", {A}),
    ("Cài đặt", "bi-gear", "/cai-dat/", {A}),
]


def build_menu(role_code, path):
    """Danh sách mục menu cho vai trò; mục đang chọn là mục có URL khớp dài nhất với đường dẫn."""
    items = [m for m in MENU if role_code in m[3]]
    active = None
    for _label, _icon, url, _roles in items:
        match = path == "/" if url == "/" else path.startswith(url)
        if match and (active is None or len(url) > len(active)):
            active = url
    return [
        {"label": label, "icon": icon, "url": url, "active": url == active}
        for label, icon, url, _roles in items
    ]


def navigation(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {"pa_menu": build_menu(user.role.code, request.path)}
