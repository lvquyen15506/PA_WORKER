from django.urls import path

from . import views

urlpatterns = [
    path("ung-tuyen/<int:pk>/tiep-nhan/", views.onboard, name="employment_onboard"),
    path("ho-so/<int:pk>/lam-viec/thay-doi/", views.change, name="employment_change"),
    path("ho-so/<int:pk>/hop-dong/them/", views.contract_add, name="contract_add"),
    path("hop-dong/<int:pk>/sua/", views.contract_edit, name="contract_edit"),
    path("ho-so/<int:pk>/dot-lam-viec/them/", views.assignment_add, name="assignment_add"),
    path("dot-lam-viec/<int:pk>/sua/", views.assignment_edit, name="assignment_edit"),
    path("dot-lam-viec/<int:pk>/luong/them/", views.salary_add, name="salary_add"),
]
