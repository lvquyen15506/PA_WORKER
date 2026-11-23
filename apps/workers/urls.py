from django.urls import path

from . import export, views, views_workflow

urlpatterns = [
    path("ho-so/", views.worker_list, name="worker_list"),
    path("ho-so/xuat-excel/", export.export_workers, name="worker_export"),
    path("ho-so/them/", views.worker_add, name="worker_add"),
    path("ho-so/them/nhap-tay/", views.worker_create, name="worker_create"),
    path("ho-so/kiem-tra-trung/", views.check_duplicate, name="worker_check_duplicate"),
    path("ho-so/<int:pk>/", views.worker_detail, name="worker_detail"),
    path("ho-so/<int:pk>/sua/", views.worker_edit, name="worker_edit"),
    path("ho-so/<int:pk>/cccd-day-du/", views.show_full_id, name="worker_full_id"),
    path("ho-so/<int:pk>/dong-y/", views.consent, name="worker_consent"),
    path("ho-so/<int:pk>/dong-y/mau-in/", views.consent_print, name="worker_consent_print"),
    path("ho-so/<int:pk>/lich-su/chi-tiet/", views.history_detail, name="worker_history_detail"),
    path("ho-so/<int:pk>/gui-duyet/", views_workflow.submit, name="worker_submit"),
    path("ho-so/<int:pk>/duyet/", views_workflow.approve, name="worker_approve"),
    path("ho-so/<int:pk>/tra-lai/", views_workflow.send_back, name="worker_send_back"),
    path("ho-so/<int:pk>/tu-choi/", views_workflow.reject, name="worker_reject"),
    path("ho-so/<int:pk>/luu-tru/", views_workflow.archive, name="worker_archive"),
    path("ho-so/<int:pk>/mo-lai/", views_workflow.reopen, name="worker_reopen"),
    path(
        "ho-so/<int:pk>/an-danh-theo-yeu-cau/",
        views_workflow.anonymize_on_request,
        name="worker_anonymize",
    ),
    path("duyet-ho-so/", views_workflow.review_queue, name="review_queue"),
]
