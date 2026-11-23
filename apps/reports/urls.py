from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="home"),
    path("bao-cao/", views.report_page, name="report_page"),
    path("bao-cao/xuat-excel/", views.report_export, name="report_export"),
    path("bao-cao/in/", views.report_print, name="report_print"),
]
