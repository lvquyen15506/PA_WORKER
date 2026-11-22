from django.urls import path

from . import views

urlpatterns = [
    path("nhap-cccd/", views.upload, name="intake_upload"),
    path("nhap-cccd/<uuid:pk>/", views.review, name="intake_review"),
    path("nhap-cccd/<uuid:pk>/tep/<slug:slot>/", views.session_file, name="intake_file"),
    path("nhap-cccd/<uuid:pk>/kiem-tra-trung/", views.check_duplicate, name="intake_check"),
    path("nhap-cccd/<uuid:pk>/huy/", views.cancel, name="intake_cancel"),
    path("nhap-cccd/<uuid:pk>/xoay/<slug:slot>/", views.rotate, name="intake_rotate"),
    path(
        "nhap-cccd/<uuid:pk>/mo-ho-so-cu/<int:worker_pk>/",
        views.open_existing,
        name="intake_open_existing",
    ),
]
