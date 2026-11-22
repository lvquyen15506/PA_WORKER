"""Form trang Cài đặt (docs/thiet-ke/trang.md mục 5.2). Tab OCR và QR: ngưỡng tin cậy OCR,
cấu hình QR theo mẫu thẻ (câu 20), API OCR ngoài (tắt mặc định)."""

from django import forms

from apps.core.choices import IdDocType
from apps.core.models import QrFormat
from apps.intake.fields import DATE_FORMATS, FIELD_LABELS, SKIP

MAX_POSITIONS = len(FIELD_LABELS) + 2  # đủ chỗ cho mọi trường và vài ô "Bỏ qua"
POSITION_CHOICES = [("", "Không dùng"), (SKIP, "Bỏ qua (bỏ phần tử này)")] + list(
    FIELD_LABELS.items()
)
DATE_FORMAT_CHOICES = [(key, key) for key in DATE_FORMATS]

MSG_ID_REQUIRED = "Phải có đúng một vị trí là Số CCCD."
MSG_GAP = "Vị trí {n} để trống nhưng vị trí sau có giá trị. Hãy dồn các vị trí lên liền nhau."
MSG_DUPLICATE = "Trường {label} đang xuất hiện nhiều lần. Mỗi trường chỉ chọn một vị trí."
MSG_NEED_URL = "Nhập địa chỉ API OCR khi bật dịch vụ bên ngoài."


def format_prefix(qr_format):
    return qr_format.id_doc_type


def format_title(qr_format):
    return f"Cấu hình QR – {IdDocType(qr_format.id_doc_type).label}"


class OcrQrForm(forms.Form):
    ocr_confidence_threshold = forms.IntegerField(
        label="Ngưỡng tin cậy OCR (%)",
        min_value=1,
        max_value=100,
        help_text="Trường OCR có độ tin cậy dưới ngưỡng này được tô vàng và phải tích Đã kiểm tra.",
        error_messages={
            "required": "Nhập ngưỡng tin cậy từ 1 đến 100.",
            "invalid": "Nhập ngưỡng tin cậy từ 1 đến 100.",
            "min_value": "Ngưỡng tin cậy phải từ 1 đến 100.",
            "max_value": "Ngưỡng tin cậy phải từ 1 đến 100.",
        },
    )
    external_ocr_enabled = forms.BooleanField(
        label="Bật API OCR bên ngoài",
        required=False,
        help_text="Tắt mặc định. Khi bật, ảnh giấy tờ có thể được gửi ra ngoài máy chủ.",
    )
    external_ocr_url = forms.URLField(
        label="Địa chỉ API OCR bên ngoài",
        required=False,
        assume_scheme="https",
        max_length=200,
        help_text="Khóa API không nhập ở đây mà khai báo trong tệp .env (EXTERNAL_OCR_API_KEY).",
        error_messages={"invalid": "Nhập địa chỉ đầy đủ, bắt đầu bằng http:// hoặc https://."},
    )

    def __init__(self, *args, system_setting, qr_formats, **kwargs):
        super().__init__(*args, **kwargs)
        self.qr_formats = list(qr_formats)
        for qr_format in self.qr_formats:
            self._add_format_fields(qr_format)
        if not self.is_bound:
            self.initial = {
                "ocr_confidence_threshold": system_setting.ocr_confidence_threshold,
                "external_ocr_enabled": system_setting.external_ocr_enabled,
                "external_ocr_url": system_setting.external_ocr_url,
            }
            for qr_format in self.qr_formats:
                self._set_format_initial(qr_format)

    # ----- trường theo từng mẫu thẻ -----

    def _name(self, qr_format, suffix):
        return f"{format_prefix(qr_format)}__{suffix}"

    def _add_format_fields(self, qr_format):
        self.fields[self._name(qr_format, "is_active")] = forms.BooleanField(
            label="Đang dùng cấu hình này", required=False
        )
        self.fields[self._name(qr_format, "separator")] = forms.CharField(
            label="Ký tự phân cách",
            max_length=5,
            strip=False,
            help_text="Từ 1 đến 5 ký tự, ví dụ |",
            error_messages={
                "required": "Nhập ký tự phân cách (1 đến 5 ký tự).",
                "max_length": "Ký tự phân cách tối đa 5 ký tự.",
            },
        )
        self.fields[self._name(qr_format, "date_format")] = forms.ChoiceField(
            label="Định dạng ngày", choices=DATE_FORMAT_CHOICES
        )
        for position in range(1, MAX_POSITIONS + 1):
            self.fields[self._name(qr_format, f"pos{position}")] = forms.ChoiceField(
                label=f"Vị trí {position}", required=False, choices=POSITION_CHOICES
            )

    def _set_format_initial(self, qr_format):
        self.initial[self._name(qr_format, "is_active")] = qr_format.is_active
        self.initial[self._name(qr_format, "separator")] = qr_format.separator
        self.initial[self._name(qr_format, "date_format")] = qr_format.date_format
        order = list(qr_format.field_order)
        for position in range(1, MAX_POSITIONS + 1):
            value = order[position - 1] if position <= len(order) else ""
            self.initial[self._name(qr_format, f"pos{position}")] = value

    @property
    def ocr_fields(self):
        return [self["ocr_confidence_threshold"]]

    @property
    def external_fields(self):
        return [self["external_ocr_enabled"], self["external_ocr_url"]]

    def format_sections(self):
        """[(tiêu đề, [BoundField])] cho từng mẫu thẻ."""
        sections = []
        for qr_format in self.qr_formats:
            names = [
                self._name(qr_format, s) for s in ("is_active", "separator", "date_format")
            ] + [self._name(qr_format, f"pos{p}") for p in range(1, MAX_POSITIONS + 1)]
            sections.append((format_title(qr_format), [self[n] for n in names]))
        return sections

    # ----- kiểm tra -----

    def _clean_order(self, qr_format):
        values = [
            self.cleaned_data.get(self._name(qr_format, f"pos{p}"), "")
            for p in range(1, MAX_POSITIONS + 1)
        ]
        order, gap_at = [], None
        for position, value in enumerate(values, start=1):
            if not value:
                gap_at = gap_at or position
                continue
            if gap_at:
                self.add_error(self._name(qr_format, f"pos{position}"), MSG_GAP.format(n=gap_at))
                return None
            order.append(value)
        seen = set()
        for position, value in enumerate(order, start=1):
            if value != SKIP and value in seen:
                self.add_error(
                    self._name(qr_format, f"pos{position}"),
                    MSG_DUPLICATE.format(label=FIELD_LABELS[value]),
                )
                return None
            seen.add(value)
        if order.count("id_number") != 1:
            self.add_error(self._name(qr_format, "pos1"), MSG_ID_REQUIRED)
            return None
        return order

    def clean(self):
        cleaned = super().clean()
        self.orders = {}
        for qr_format in self.qr_formats:
            order = self._clean_order(qr_format)
            if order is not None:
                self.orders[qr_format.pk] = order
        if cleaned.get("external_ocr_enabled") and not cleaned.get("external_ocr_url"):
            self.add_error("external_ocr_url", MSG_NEED_URL)
        return cleaned

    def format_values(self, qr_format):
        """Giá trị đã kiểm tra của một mẫu thẻ (dùng khi lưu)."""
        return {
            "is_active": self.cleaned_data[self._name(qr_format, "is_active")],
            "separator": self.cleaned_data[self._name(qr_format, "separator")],
            "date_format": self.cleaned_data[self._name(qr_format, "date_format")],
            "field_order": self.orders[qr_format.pk],
        }


def load_qr_formats():
    return QrFormat.objects.order_by("id_doc_type")
