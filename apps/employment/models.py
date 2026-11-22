"""Quá trình làm việc, lịch sử điều chuyển, hợp đồng (docs/thiet-ke/models.md mục 3.8), đợt làm
việc tại công ty khách và lịch sử lương (v1.1, mục 3.9).

Không sửa trực tiếp section/team/position/shift/manager/work_status: mọi thay đổi đi qua
apps.employment.services.change_employment, hàm này thêm dòng EmploymentHistory.
"""

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.db.models import F, Q

from apps.core.choices import ContractType, EmploymentChangeType, ResignReason, WorkStatus
from apps.core.crypto import EncryptedTextField
from apps.core.models_base import AppendOnlyModel, NoUpdateQuerySet


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
    # Không bắt buộc từ v1.1 (câu 48): công nhân cung ứng có thể chưa thuộc bộ phận nội bộ nào.
    section = models.ForeignKey(
        "core.Section", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
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
        """Phòng ban suy ra từ bộ phận; chưa có bộ phận thì None (câu 15, 48)."""
        return self.section.department if self.section_id else None

    def clean(self):
        errors = {}
        if self.team_id and not self.section_id:
            errors["team"] = "Chọn bộ phận trước khi chọn tổ."
        elif self.team_id and self.team.section_id != self.section_id:
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
    # Người quản lý trực tiếp (thêm ở Phase 6, câu 48).
    from_manager = models.ForeignKey(
        "workers.Worker", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    to_manager = models.ForeignKey(
        "workers.Worker", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
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


class WorkAssignment(models.Model):
    """Đợt làm việc tại một công ty khách hàng (v1.1, câu 40). Mỗi lúc một công nhân chỉ một
    công ty: tối đa một đợt đang mở (end_date rỗng, ràng buộc CSDL) và các đợt không chồng lấn
    ngày (kiểm tra trong apps.employment.services). Không xóa; nhập nhầm thì sửa."""

    worker = models.ForeignKey(
        "workers.Worker", on_delete=models.PROTECT, related_name="work_assignments"
    )
    client_company = models.ForeignKey(
        "core.ClientCompany", on_delete=models.PROTECT, related_name="assignments"
    )
    position = models.ForeignKey("core.Position", on_delete=models.PROTECT, related_name="+")
    start_date = models.DateField("Ngày bắt đầu")
    end_date = models.DateField("Ngày kết thúc", null=True, blank=True)  # ngày làm cuối cùng
    note = models.TextField("Ghi chú", blank=True)  # trường cá nhân (PERSONAL_FIELDS)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")),
                name="workassignment_end_after_start",
            ),
            models.UniqueConstraint(
                fields=["worker"],
                condition=Q(end_date__isnull=True),
                name="uniq_workassignment_one_open_per_worker",
            ),
        ]

    def __str__(self):
        return f"Đợt làm việc {self.pk} của {self.worker.worker_code}"


class SalaryHistory(AppendOnlyModel):
    """Lịch sử lương tháng và đơn giá tháng của một đợt làm việc (v1.1, câu 41, 42, 48).

    Chỉ thêm: không sửa (model, QuerySet; PostgreSQL có trigger chặn UPDATE), không xóa, trừ
    khi ẩn danh hóa hồ sơ (apps.workers.retention._wipe, ngoại lệ ghi ở CLAUDE.md). Hai khoản
    tiền mã hóa Fernet, lưu dạng chuỗi số nguyên VNĐ. `worker` luôn bằng `assignment.worker`.
    """

    append_only_allow_delete = True  # chỉ retention._wipe gọi xóa (có test quét mã nguồn)
    objects = NoUpdateQuerySet.as_manager()

    assignment = models.ForeignKey(
        WorkAssignment, on_delete=models.PROTECT, related_name="salary_history"
    )
    worker = models.ForeignKey(
        "workers.Worker", on_delete=models.PROTECT, related_name="salary_history"
    )
    monthly_salary_enc = EncryptedTextField("Lương tháng")
    client_unit_price_enc = EncryptedTextField("Đơn giá tháng", null=True, blank=True)
    effective_date = models.DateField("Ngày áp dụng")
    reason = models.TextField("Lý do")
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_date", "-id"]
        verbose_name_plural = "salary history"

    def __str__(self):
        return f"Lương {self.worker.worker_code} từ {self.effective_date:%d/%m/%Y}"

    @property
    def monthly_salary(self):
        return int(self.monthly_salary_enc) if self.monthly_salary_enc else None

    @property
    def client_unit_price(self):
        return int(self.client_unit_price_enc) if self.client_unit_price_enc else None
