from django.urls import path

from . import views

urlpatterns = [
    path("ho-so/<int:worker_id>/tai-lieu/them/", views.upload, name="document_upload"),
    path("tai-lieu/<int:pk>/xem/", views.view_file, name="document_view"),
    path("tai-lieu/<int:pk>/tai-xuong/", views.download_file, name="document_download"),
    path("tai-lieu/<int:pk>/thay-the/", views.replace, name="document_replace"),
    path("tai-lieu/<int:pk>/xac-minh/", views.verify, name="document_verify"),
    path("tai-lieu/<int:pk>/lich-su/", views.history, name="document_history"),
]
