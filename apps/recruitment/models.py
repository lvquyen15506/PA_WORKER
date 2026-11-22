"""Ứng tuyển, học vấn, chứng chỉ, kinh nghiệm (docs/thiet-ke/models.md mục 3.7)."""

from django.db import models

from apps.core.choices import RecruitmentStatus


class Application(models.Model):
    worker = models.ForeignKey(
        "workers.Worker", on_delete=models.PROTECT, related_name="applications"
    )
    position = models.ForeignKey("core.Position", on_delete=models.PROTECT, related_name="+")
    source = models.ForeignKey("core.ApplicationSource", on_delete=models.PROTECT, related_name="+")
    applied_date = models.DateField("Ngày ứng tuyển")
    expected_salary = models.DecimalField(  # VNĐ; ẩn với Viewer (câu 13)
        "Mức lương mong muốn", max_digits=12, decimal_places=0, null=True, blank=True
    )
    available_date = models.DateField("Ngày có thể nhận việc", null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=RecruitmentStatus.choices,
        default=RecruitmentStatus.NEW,
        db_index=True,
    )
    interview_at = models.DateTimeField(null=True, blank=True)
    interview_notes = models.TextField(blank=True)
    result_date = models.DateField(null=True, blank=True)
    reject_reason = models.TextField(blank=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_date", "-id"]

    def __str__(self):
        return f"{self.worker.worker_code} – {self.applied_date}"


class Education(models.Model):
    worker = models.ForeignKey("workers.Worker", on_delete=models.PROTECT, related_name="education")
    education_level = models.ForeignKey(
        "core.EducationLevel", on_delete=models.PROTECT, related_name="+"
    )
    school_name = models.CharField(max_length=200)
    major = models.CharField(max_length=200, blank=True)
    start_year = models.PositiveSmallIntegerField(null=True, blank=True)
    end_year = models.PositiveSmallIntegerField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "education"

    def __str__(self):
        return f"{self.worker.worker_code} – học vấn #{self.pk}"


class Certificate(models.Model):
    worker = models.ForeignKey(
        "workers.Worker", on_delete=models.PROTECT, related_name="certificates"
    )
    name = models.CharField(max_length=200)
    issuer = models.CharField(max_length=200, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True)

    def __str__(self):
        return f"{self.worker.worker_code} – chứng chỉ #{self.pk}"


class WorkExperience(models.Model):
    worker = models.ForeignKey(
        "workers.Worker", on_delete=models.PROTECT, related_name="work_experiences"
    )
    company_name = models.CharField(max_length=200)
    job_title = models.CharField(max_length=200, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.worker.worker_code} – kinh nghiệm #{self.pk}"
