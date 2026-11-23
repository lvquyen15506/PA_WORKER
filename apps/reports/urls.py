from django.urls import path

from . import views, views_import

urlpatterns = [
    path("", views.dashboard, name="home"),
    path("bao-cao/", views.report_page, name="report_page"),
    path("bao-cao/xuat-excel/", views.report_export, name="report_export"),
    path("bao-cao/in/", views.report_print, name="report_print"),
    path("ho-so/nhap-excel/", views_import.import_page, name="worker_import"),
    path(
        "ho-so/nhap-excel/file-mau/", views_import.template_download, name="worker_import_template"
    ),
]
