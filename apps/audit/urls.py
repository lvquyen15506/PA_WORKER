from django.urls import path

from . import views

urlpatterns = [
    path("nhat-ky/", views.audit_list, name="audit_list"),
    path("nhat-ky/<int:pk>/", views.audit_detail, name="audit_detail"),
]
