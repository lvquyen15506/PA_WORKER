from django.urls import path, register_converter

from . import views


class ChildKindConverter:
    """Loại dòng con của tab Tuyển dụng; giá trị khác không khớp URL (404)."""

    regex = "hoc-van|chung-chi|kinh-nghiem"

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


register_converter(ChildKindConverter, "kind")

urlpatterns = [
    path("tuyen-dung/", views.recruitment_list, name="recruitment_list"),
    path("ho-so/<int:worker_id>/ung-tuyen/them/", views.application_add, name="application_add"),
    path("ung-tuyen/<int:pk>/sua/", views.application_edit, name="application_edit"),
    path("ho-so/<int:worker_id>/<kind:kind>/them/", views.child_add, name="recruitment_child_add"),
    path("<kind:kind>/<int:pk>/sua/", views.child_edit, name="recruitment_child_edit"),
    path("<kind:kind>/<int:pk>/xoa/", views.child_delete, name="recruitment_child_delete"),
]
