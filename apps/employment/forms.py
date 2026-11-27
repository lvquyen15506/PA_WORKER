"""Form quá trình làm việc (trang.md mục 5.8): tiếp nhận, ghi nhận thay đổi, hợp đồng.

Quy tắc nghiệp vụ kiểm tra ở apps.employment.services; form lấy dữ liệu và chuyển lỗi xuống ô."""

from django import forms

from apps.core.choices import ContractType, ResignReason, WorkStatus
from apps.core.formfields import REASON_HINT, active_or_current, date_field, is_unbound
from apps.core.models import ClientCompany, Position, Section, Shift, Team
from apps.documents.forms import FILE_HINT
from apps.documents.validators import MAX_SIZE, validate_upload
from apps.workers.models import Worker


def _section_label(section):
    return f"{section.name} ({section.department.name})"


def _team_label(team):
    return f"{team.name} ({team.section.name})"


class _StructureMixin:
    """Bộ phận, tổ, chức danh, ca, người quản lý (nhập mã nhân viên) dùng chung cho hai form."""

    def _add_structure(self, current=None):
        self.fields["section"] = forms.ModelChoiceField(
            label="Bộ phận",
            required=False,
            queryset=active_or_current(
                Section.objects.select_related("department").order_by(
                    "department__sort_order", "sort_order", "name"
                ),
                current.section if current and current.section_id else None,
            ),
            empty_label="Chưa có bộ phận",
            help_text="Không bắt buộc: công nhân cung ứng có thể chưa thuộc bộ phận nội bộ nào.",
        )
        self.fields["section"].label_from_instance = _section_label
        self.fields["team"] = forms.ModelChoiceField(
            label="Tổ",
            required=False,
            queryset=active_or_current(
                Team.objects.select_related("section").order_by(
                    "section__sort_order", "sort_order", "name"
                ),
                current.team if current and current.team_id else None,
            ),
            empty_label="Không có tổ",
            help_text="Chỉ chọn khi đã chọn bộ phận; tổ phải thuộc bộ phận đó.",
        )
        self.fields["team"].label_from_instance = _team_label
        self.fields["position"] = forms.ModelChoiceField(
            label="Chức danh",
            queryset=active_or_current(
                Position.objects.order_by("name"), current.position if current else None
            ),
            empty_label="— Chọn —",
            error_messages={"required": "Chọn chức danh."},
        )
        self.fields["shift"] = forms.ModelChoiceField(
            label="Ca làm việc",
            required=False,
            queryset=active_or_current(
                Shift.objects.order_by("name"),
                current.shift if current and current.shift_id else None,
            ),
            empty_label="Chưa có ca",
        )
        self.fields["manager_code"] = forms.CharField(
            label="Mã nhân viên của người quản lý trực tiếp",
            required=False,
            max_length=20,
            help_text="Không bắt buộc. Nhập mã nhân viên của một công nhân khác.",
        )

    def clean_manager_code(self):
        code = (self.cleaned_data.get("manager_code") or "").strip()
        if not code:
            self.manager = None
            return ""
        manager = Worker.objects.filter(employee_code__iexact=code).first()
        if manager is None:
            raise forms.ValidationError("Không tìm thấy công nhân có mã nhân viên này.")
        self.manager = manager
        return code

    def structure_data(self):
        data = self.cleaned_data
        return {
            "section": data.get("section"),
            "team": data.get("team"),
            "position": data.get("position"),
            "shift": data.get("shift"),
            "manager": getattr(self, "manager", None),
        }


class OnboardForm(_StructureMixin, forms.Form):
    received_date = date_field("Ngày tiếp nhận", required=True)
    start_date = date_field("Ngày bắt đầu", required=True)

    def __init__(self, *args, application=None, **kwargs):
        if application is not None and is_unbound(args, kwargs):
            kwargs.setdefault("initial", {"position": application.position_id})
        super().__init__(*args, **kwargs)
        self._add_structure()
        self.order_fields(
            [
                "received_date",
                "start_date",
                "section",
                "team",
                "position",
                "shift",
                "manager_code",
            ]
        )

        # v1.1.1: phần không bắt buộc "Gán công ty khách ngay" (đợt làm việc đầu tiên).
        self.fields["assign_client_company"] = forms.ModelChoiceField(
            label="Công ty khách hàng",
            required=False,
            queryset=ClientCompany.objects.filter(is_active=True).order_by("name", "location"),
            empty_label="Chưa gán",
            help_text="Không bắt buộc. Để trống nếu chưa biết công nhân làm cho công ty nào.",
        )
        self.fields["assign_position"] = forms.ModelChoiceField(
            label="Vị trí tại công ty khách",
            required=False,
            queryset=Position.objects.filter(is_active=True).order_by("name"),
            empty_label="— Chọn —",
        )
        self.fields["assign_start_date"] = date_field("Ngày bắt đầu tại công ty khách")

    ASSIGN_FIELDS = ("assign_client_company", "assign_position", "assign_start_date")

    def main_fields(self):
        return [f for f in self.visible_fields() if f.name not in self.ASSIGN_FIELDS]

    def assign_fields(self):
        return [self[name] for name in self.ASSIGN_FIELDS]

    def clean(self):
        cleaned = super().clean()
        company = cleaned.get("assign_client_company")
        position = cleaned.get("assign_position")
        start = cleaned.get("assign_start_date")
        if company is None:
            if position is not None or start is not None:
                self.add_error(
                    "assign_client_company",
                    "Chọn công ty khách hàng, hoặc xóa vị trí và ngày bắt đầu nếu chưa gán.",
                )
            return cleaned
        if position is None:
            self.add_error("assign_position", "Chọn vị trí tại công ty khách.")
        if start is None:
            self.add_error("assign_start_date", "Nhập ngày bắt đầu tại công ty khách.")
        return cleaned

    def service_data(self):
        data = {k: self.cleaned_data[k] for k in ("received_date", "start_date")}
        data.update(self.structure_data())
        company = self.cleaned_data.get("assign_client_company")
        if company is not None:
            data["assignment"] = {
                "client_company": company,
                "position": self.cleaned_data["assign_position"],
                "start_date": self.cleaned_data["assign_start_date"],
            }
        return data


class ChangeForm(_StructureMixin, forms.Form):
    effective_date = date_field("Ngày hiệu lực", required=True)
    work_status = forms.ChoiceField(label="Trạng thái làm việc", choices=WorkStatus.choices)
    resign_date = date_field("Ngày nghỉ việc")
    resign_reason = forms.ChoiceField(
        label="Lý do nghỉ việc", required=False, choices=[("", "— Chọn —")] + ResignReason.choices
    )
    resign_note = forms.CharField(
        label="Ghi chú nghỉ việc",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text=REASON_HINT,
    )
    decision_no = forms.CharField(label="Số quyết định", required=False, max_length=50)
    reason = forms.CharField(
        label="Lý do thay đổi",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text=REASON_HINT,
    )

    def __init__(self, *args, employment, **kwargs):
        if is_unbound(args, kwargs):
            manager = employment.manager
            kwargs.setdefault(
                "initial",
                {
                    "section": employment.section_id,
                    "team": employment.team_id,
                    "position": employment.position_id,
                    "shift": employment.shift_id,
                    "manager_code": manager.employee_code if manager else "",
                    "work_status": employment.work_status,
                },
            )
        super().__init__(*args, **kwargs)
        self._add_structure(employment)
        self.fields[
            "work_status"
        ].help_text = "Đã nghỉ việc cần ngày nghỉ và lý do; sau đó không đổi tiếp được."
        self.order_fields(
            [
                "effective_date",
                "section",
                "team",
                "position",
                "shift",
                "manager_code",
                "work_status",
                "resign_date",
                "resign_reason",
                "resign_note",
                "decision_no",
                "reason",
            ]
        )

    def service_data(self):
        data = self.structure_data()
        for name in (
            "effective_date",
            "work_status",
            "resign_date",
            "resign_reason",
            "resign_note",
            "decision_no",
            "reason",
        ):
            data[name] = self.cleaned_data.get(name)
        return data


class ContractForm(forms.Form):
    contract_no = forms.CharField(
        label="Số hợp đồng", max_length=60, error_messages={"required": "Nhập số hợp đồng."}
    )
    contract_type = forms.ChoiceField(label="Loại hợp đồng", choices=ContractType.choices)
    signed_date = date_field("Ngày ký", required=True)
    effective_date = date_field("Ngày hiệu lực", required=True)
    expiry_date = date_field(
        "Ngày hết hạn", help_text="Bắt buộc trừ hợp đồng không xác định thời hạn."
    )
    file = forms.FileField(label="Tệp hợp đồng", required=False, help_text=FILE_HINT)
    note = forms.CharField(
        label="Ghi chú", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, instance=None, allow_file=True, **kwargs):
        if instance is not None and is_unbound(args, kwargs):
            kwargs.setdefault(
                "initial",
                {
                    f: getattr(instance, f)
                    for f in (
                        "contract_no",
                        "contract_type",
                        "signed_date",
                        "effective_date",
                        "expiry_date",
                        "note",
                    )
                },
            )
        super().__init__(*args, **kwargs)
        if not allow_file:
            # Hồ sơ không cho tải tài liệu ở trạng thái này (ma trận 4.4): bỏ ô tệp.
            del self.fields["file"]

    def clean_file(self):
        uploaded = self.cleaned_data.get("file")
        if uploaded:
            if uploaded.size > MAX_SIZE:
                raise forms.ValidationError("Tệp vượt quá 10 MB.")
            validate_upload(uploaded)  # ném ValidationError tiếng Việt nếu không hợp lệ
        return uploaded

    def service_data(self):
        data = {
            k: self.cleaned_data.get(k)
            for k in (
                "contract_no",
                "contract_type",
                "signed_date",
                "effective_date",
                "expiry_date",
                "note",
            )
        }
        data["uploaded"] = self.cleaned_data.get("file")
        return data


# --- Đợt làm việc và lương (v1.1) ----------------------------------------------------------------
class AssignmentForm(forms.Form):
    client_company = forms.ModelChoiceField(
        label="Công ty khách hàng",
        queryset=ClientCompany.objects.none(),
        empty_label="— Chọn —",
        error_messages={"required": "Chọn công ty khách hàng."},
    )
    position = forms.ModelChoiceField(
        label="Vị trí",
        queryset=Position.objects.none(),
        empty_label="— Chọn —",
        error_messages={"required": "Chọn vị trí."},
    )
    start_date = date_field("Ngày bắt đầu", required=True)
    end_date = date_field(
        "Ngày kết thúc", help_text="Để trống nếu đợt chưa kết thúc. Là ngày làm cuối cùng."
    )
    previous_end_date = date_field(
        "Ngày kết thúc của đợt hiện tại",
        help_text="Chỉ nhập khi công nhân đang có đợt làm việc chưa kết thúc: đợt đó được kết thúc "
        "vào ngày này khi lưu đợt mới.",
    )
    note = forms.CharField(
        label="Ghi chú",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text=REASON_HINT,
    )

    def __init__(self, *args, instance=None, **kwargs):
        if instance is not None and is_unbound(args, kwargs):
            kwargs.setdefault(
                "initial",
                {
                    "client_company": instance.client_company_id,
                    "position": instance.position_id,
                    "start_date": instance.start_date,
                    "end_date": instance.end_date,
                    "note": instance.note,
                },
            )
        super().__init__(*args, **kwargs)
        self.fields["client_company"].queryset = active_or_current(
            ClientCompany.objects.order_by("name", "location"),
            instance.client_company if instance else None,
        )
        self.fields["position"].queryset = active_or_current(
            Position.objects.order_by("name"), instance.position if instance else None
        )
        if instance is not None:  # chỉ khi thêm mới mới có đợt cũ cần kết thúc
            del self.fields["previous_end_date"]

    def service_data(self):
        return {k: v for k, v in self.cleaned_data.items()}


class SalaryForm(forms.Form):
    monthly_salary = forms.IntegerField(
        label="Lương tháng (đồng)",
        min_value=1,
        error_messages={
            "required": "Nhập lương tháng.",
            "invalid": "Nhập số nguyên, không có dấu chấm hay chữ.",
            "min_value": "Lương tháng phải lớn hơn 0.",
        },
    )
    client_unit_price = forms.IntegerField(
        label="Đơn giá tháng tính cho công ty khách (đồng)",
        required=False,
        min_value=1,
        help_text="Không bắt buộc.",
        error_messages={
            "invalid": "Nhập số nguyên, không có dấu chấm hay chữ.",
            "min_value": "Đơn giá tháng phải lớn hơn 0.",
        },
    )
    effective_date = date_field("Ngày áp dụng", required=True)
    reason = forms.CharField(
        label="Lý do thay đổi",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text=REASON_HINT,
        error_messages={"required": "Nhập lý do thay đổi."},
    )

    def __init__(self, *args, latest=None, **kwargs):
        if latest is not None and is_unbound(args, kwargs):
            # Đổi một khoản thì khoản kia giữ giá trị cũ: điền sẵn từ dòng gần nhất của đợt.
            kwargs.setdefault(
                "initial",
                {
                    "monthly_salary": latest.monthly_salary,
                    "client_unit_price": latest.client_unit_price,
                },
            )
        super().__init__(*args, **kwargs)

    def service_data(self):
        return dict(self.cleaned_data)
