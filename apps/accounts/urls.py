from django.urls import path

from . import views

urlpatterns = [
    path("dang-nhap/", views.login_stub, name="login"),
]
