from django.urls import path

from . import settings_views, views

urlpatterns = [
    path("", views.home, name="home"),
    path("gioi-thieu/", views.about, name="about"),
    path("ui-kit/", views.ui_kit_view, name="ui_kit"),
    path("cai-dat/", settings_views.settings_home, name="settings_home"),
    path("cai-dat/ocr-qr/", settings_views.settings_ocr_qr, name="settings_ocr_qr"),
]
