from django.urls import path

from . import views

urlpatterns = [
    path("ung-tuyen/<int:pk>/tiep-nhan/", views.onboard, name="employment_onboard"),
    path("ho-so/<int:pk>/lam-viec/thay-doi/", views.change, name="employment_change"),
    path("ho-so/<int:pk>/hop-dong/them/", views.contract_add, name="contract_add"),
    path("hop-dong/<int:pk>/sua/", views.contract_edit, name="contract_edit"),
]
