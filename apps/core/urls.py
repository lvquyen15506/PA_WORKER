from django.urls import path

from . import settings_views, views

urlpatterns = [
    path("", views.home, name="home"),
    path("gioi-thieu/", views.about, name="about"),
    path("ui-kit/", views.ui_kit_view, name="ui_kit"),
    path("cai-dat/", settings_views.settings_home, name="settings_home"),
    path("cai-dat/ocr-qr/", settings_views.settings_ocr_qr, name="settings_ocr_qr"),
    path("cai-dat/sinh-ma/", settings_views.settings_codes, name="settings_codes"),
    path("cai-dat/nguong/", settings_views.settings_thresholds, name="settings_thresholds"),
    path("cai-dat/danh-muc/", settings_views.catalog_home, name="settings_catalogs"),
    path("cai-dat/danh-muc/<slug:loai>/", settings_views.catalog_list, name="settings_catalog"),
    path(
        "cai-dat/danh-muc/<slug:loai>/them/",
        settings_views.catalog_add,
        name="settings_catalog_add",
    ),
    path(
        "cai-dat/danh-muc/<slug:loai>/<int:pk>/sua/",
        settings_views.catalog_edit,
        name="settings_catalog_edit",
    ),
    path(
        "cai-dat/danh-muc/<slug:loai>/<int:pk>/ngung/",
        settings_views.catalog_stop,
        name="settings_catalog_stop",
    ),
    path(
        "cai-dat/danh-muc/<slug:loai>/<int:pk>/dung-lai/",
        settings_views.catalog_resume,
        name="settings_catalog_resume",
    ),
]
