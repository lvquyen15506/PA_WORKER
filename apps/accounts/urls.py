from django.urls import path

from . import views

urlpatterns = [
    path("dang-nhap/", views.login_view, name="login"),
    path("dang-xuat/", views.logout_view, name="logout"),
    path("doi-mat-khau/", views.change_password, name="change_password"),
    path("tai-khoan/", views.user_list, name="user_list"),
    path("tai-khoan/them/", views.user_create, name="user_create"),
    path("tai-khoan/lich-su-dang-nhap/", views.login_history, name="login_history"),
    path("tai-khoan/<int:pk>/sua/", views.user_edit, name="user_edit"),
    path("tai-khoan/<int:pk>/khoa/", views.user_lock, name="user_lock"),
    path("tai-khoan/<int:pk>/mo-khoa/", views.user_unlock, name="user_unlock"),
    path(
        "tai-khoan/<int:pk>/dat-lai-mat-khau/",
        views.user_reset_password,
        name="user_reset_password",
    ),
]
