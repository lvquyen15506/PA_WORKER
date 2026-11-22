from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("gioi-thieu/", views.about, name="about"),
    path("ui-kit/", views.ui_kit_view, name="ui_kit"),
]
