"""Quá trình làm việc, lịch sử điều chuyển, hợp đồng (docs/thiet-ke/models.md mục 3.8).

Không sửa trực tiếp section/team/position/shift/work_status: mọi thay đổi đi qua
apps.employment.services.change_employment (Phase 6), hàm này thêm dòng EmploymentHistory.
"""

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models

from apps.core.choices import ContractType, EmploymentChangeType, ResignReason, WorkStatus
from apps.core.models_base import AppendOnlyModel


class Employment(models.Model):
    worker = models.OneToOneField(
        "workers.Worker", on_delete=models.PROTECT, related_name="employment"
    )
    # Có khi tiếp nhận từ ứng tuyển; rỗng khi nhập Excel.
    application = models.OneToOneField(
        "recruitment.Application",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="employment",
    )
    received_date = models.DateField("Ngày tiếp nhận")
    start_date = models.DateField("Ngày bắt đầu")
    section = models.ForeignKey("core.Section", on_delete=models.PROTECT, related_name="+")
    team = models.ForeignKey(
        "core.Team", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    position = models.ForeignKey("core.Position", on_delete=models.PROTECT, related_name="+")
    shift = models.ForeignKey(
        "core.Shift", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    manager = models.ForeignKey(
        "workers.Worker",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="managed_employments",
    )
    work_status = models.CharField(
        max_length=20, choices=WorkStatus.choices, default=WorkStatus.AWAITING, db_index=True
    )
    resign_date = models.DateField(null=True, blank=True)
    resign_reason = models.CharField(max_length=20, choices=ResignReason.choices, blank=True)
    resign_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Làm việc: {self.worker.worker_code}"

    @property
    def department(self):
        return self.section.department

    def clean(self):
        errors = {}
        if self.team_id and self.section_id and self.team.section_id != self.section_id:
            errors["team"] = "Tổ phải thuộc bộ phận đã chọn."
        if self.manager_id and self.manager_id == self.worker_id:
            errors["manager"] = "Người quản lý trực tiếp không được là chính mình."
        if self.work_status == WorkStatus.RESIGNED:
            if not self.resign_date:
                errors["resign_date"] = "Nhập ngày nghỉ việc."
            if not self.resign_reason:
                errors["resign_reason"] = "Chọn lý do nghỉ việc."
        if errors:
            raise ValidationError(errors)


class EmploymentHistory(AppendOnlyModel):
    worker = models.ForeignKey(
        "workers.Worker", on_delete=models.PROTECT, related_name="employment_history"
    )
    change_type = models.CharField(max_length=20, choices=EmploymentChangeType.choices)
    effective_date = models.DateField()
    decision_no = models.CharField(max_length=50, blank=True)
    reason = models.TextField(blank=True)
    from_section = models.ForeignKey(
        "core.Section", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    to_section = models.ForeignKey(
        "core.Section", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    from_team = models.ForeignKey(
        "core.Team", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    to_team = models.ForeignKey(
        "core.Team", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    from_position = models.ForeignKey(
        "core.Position", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    to_position = models.ForeignKey(
        "core.Position", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    from_shift = models.ForeignKey(
        "core.Shift", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    to_shift = models.ForeignKey(
        "core.Shift", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    from_work_status = models.CharField(max_length=20, choices=WorkStatus.choices, blank=True)
    to_work_status = models.CharField(max_length=20, choices=WorkStatus.choices, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_date", "-id"]


class Contract(models.Model):
    worker = models.ForeignKey("workers.Worker", on_delete=models.PROTECT, related_name="contracts")
    contract_no = models.CharField("Số hợp đồng", max_length=50, unique=True)
    contract_type = models.CharField("Loại hợp đồng", max_length=20, choices=ContractType.choices)
    signed_date = models.DateField("Ngày ký")
    effective_date = models.DateField("Ngày hiệu lực")
    expiry_date = models.DateField("Ngày hết hạn", null=True, blank=True)
    # Tệp loại CONTRACT của cùng hồ sơ; hiển thị qua current_document (câu 32).
    document = models.ForeignKey(
        "documents.WorkerDocument",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contracts",
    )
    note = models.TextField(blank=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_date", "-id"]

    def __str__(self):
        return self.contract_no

    @property
    def current_document(self):
        """Bản hiện hành của chuỗi thay thế: đi theo replaced_by tới bản is_current."""
        doc = self.document
        while doc is not None and not doc.is_current:
            try:
                doc = doc.replaced_by
            except ObjectDoesNotExist:
                break
        return doc

    def clean(self):
        errors = {}
        if self.contract_type != ContractType.INDEFINITE and not self.expiry_date:
            errors["expiry_date"] = "Nhập ngày hết hạn."
        if self.expiry_date and self.effective_date and self.expiry_date <= self.effective_date:
            errors["expiry_date"] = "Ngày hết hạn phải sau ngày hiệu lực."
        if errors:
            raise ValidationError(errors)
