"""Toàn bộ TextChoices của hệ thống, khai báo MỘT chỗ (docs/thiet-ke/models.md mục 2).

Không viết chuỗi trạng thái ở nơi khác. Chỉ có bốn bộ trạng thái:
RecruitmentStatus, VerificationStatus, WorkStatus, DocumentVerificationStatus.
"""

from django.db import models


# --- Bốn bộ trạng thái -------------------------------------------------------------
class RecruitmentStatus(models.TextChoices):
    NEW = "NEW", "Mới nộp"
    SCREENING = "SCREENING", "Đang sàng lọc"
    INTERVIEW = "INTERVIEW", "Hẹn phỏng vấn"
    PASSED = "PASSED", "Đạt"
    FAILED = "FAILED", "Không đạt"
    DECLINED = "DECLINED", "Ứng viên từ chối"


class VerificationStatus(models.TextChoices):
    DRAFT = "DRAFT", "Nháp"
    PENDING = "PENDING", "Chờ duyệt"
    NEEDS_INFO = "NEEDS_INFO", "Cần bổ sung"
    VERIFIED = "VERIFIED", "Đã xác minh"
    REJECTED = "REJECTED", "Bị từ chối"
    ARCHIVED = "ARCHIVED", "Lưu trữ"


class WorkStatus(models.TextChoices):
    AWAITING = "AWAITING", "Chờ nhận việc"
    PROBATION = "PROBATION", "Thử việc"
    ACTIVE = "ACTIVE", "Đang làm việc"
    SUSPENDED = "SUSPENDED", "Tạm hoãn"
    RESIGNED = "RESIGNED", "Đã nghỉ việc"


class DocumentVerificationStatus(models.TextChoices):
    """Bộ thứ tư, chỉ dùng trong tab Tài liệu (lam-ro-yeu-cau.md câu 3)."""

    UNVERIFIED = "UNVERIFIED", "Chưa xác minh"
    MATCHED = "MATCHED", "Đã đối chiếu bản gốc"
    INVALID = "INVALID", "Không hợp lệ"


# --- Danh sách giá trị khác --------------------------------------------------------
class RoleCode(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    HR_MANAGER = "HR_MANAGER", "Quản lý nhân sự"
    HR_STAFF = "HR_STAFF", "Nhân viên HR"
    VIEWER = "VIEWER", "Viewer"


class Gender(models.TextChoices):
    MALE = "MALE", "Nam"
    FEMALE = "FEMALE", "Nữ"


class IdDocType(models.TextChoices):
    CCCD_2021 = "CCCD_2021", "CCCD gắn chip (mẫu 2021)"
    CAN_CUOC_2024 = "CAN_CUOC_2024", "Thẻ Căn cước (từ 01/7/2024)"
    CCCD_2016 = "CCCD_2016", "CCCD mã vạch (mẫu 2016)"


class ConsentMethod(models.TextChoices):
    PAPER = "PAPER", "Ký giấy"
    ELECTRONIC = "ELECTRONIC", "Xác nhận điện tử"


class FieldSource(models.TextChoices):
    QR = "QR", "QR"
    OCR = "OCR", "OCR"
    HINT = "HINT", "Gợi ý"  # nơi cấp, quốc tịch, hạn thẻ tính theo quy định; luôn phải kiểm tra
    MANUAL = "MANUAL", "Nhập tay"


class ResignReason(models.TextChoices):
    SELF = "SELF", "Tự nghỉ"
    CONTRACT_END = "CONTRACT_END", "Hết hợp đồng"
    TERMINATED = "TERMINATED", "Chấm dứt hợp đồng"
    OTHER = "OTHER", "Khác"


class ContractType(models.TextChoices):
    PROBATION = "PROBATION", "Thử việc"
    FIXED_TERM = "FIXED_TERM", "Xác định thời hạn"
    INDEFINITE = "INDEFINITE", "Không xác định thời hạn"


class EmploymentChangeType(models.TextChoices):
    ONBOARD = "ONBOARD", "Tiếp nhận vào làm"
    TRANSFER = "TRANSFER", "Điều chuyển"
    POSITION_CHANGE = "POSITION_CHANGE", "Đổi chức danh"
    SHIFT_CHANGE = "SHIFT_CHANGE", "Đổi ca"
    STATUS_CHANGE = "STATUS_CHANGE", "Đổi trạng thái làm việc"
    IMPORT = "IMPORT", "Nhập từ Excel"


class RetentionBasis(models.TextChoices):
    """Sáu căn cứ hạn lưu trữ, thứ tự xét theo câu 2."""

    RESIGNED = "RESIGNED", "Công nhân đã nghỉ"
    EMPLOYEE_OTHER = "EMPLOYEE_OTHER", "Công nhân lưu trữ khác"
    FAILED_CANDIDATE = "FAILED_CANDIDATE", "Ứng viên không được tuyển"
    REJECTED = "REJECTED", "Hồ sơ bị từ chối"
    ABANDONED = "ABANDONED", "Hồ sơ bỏ dở"
    CANDIDATE_OTHER = "CANDIDATE_OTHER", "Ứng viên lưu trữ khác"


class CodeType(models.TextChoices):
    WORKER = "WORKER", "Mã hồ sơ"
    EMPLOYEE = "EMPLOYEE", "Mã nhân viên"


class AnonymizationKind(models.TextChoices):
    EXPIRED = "EXPIRED", "Hết hạn lưu trữ"
    SUBJECT_REQUEST = "SUBJECT_REQUEST", "Theo yêu cầu của chủ thể"


class AuditAction(models.TextChoices):
    CREATE = "CREATE", "Tạo"
    UPDATE = "UPDATE", "Sửa"
    STATUS_CHANGE = "STATUS_CHANGE", "Đổi trạng thái"
    REOPEN = "REOPEN", "Mở lại hồ sơ"
    VIEW_FULL_ID = "VIEW_FULL_ID", "Xem số CCCD đầy đủ"
    VIEW_FILE = "VIEW_FILE", "Xem tài liệu"
    DOWNLOAD_FILE = "DOWNLOAD_FILE", "Tải tài liệu"
    UPLOAD_FILE = "UPLOAD_FILE", "Tải lên tài liệu"
    REPLACE_FILE = "REPLACE_FILE", "Thay thế tài liệu"
    EXPORT = "EXPORT", "Xuất Excel"
    PRINT = "PRINT", "In báo cáo"
    IMPORT = "IMPORT", "Nhập Excel"
    ANONYMIZE = "ANONYMIZE", "Ẩn danh hóa"
    INTAKE_CREATE = "INTAKE_CREATE", "Tạo phiên nhận diện"
    INTAKE_SAVE = "INTAKE_SAVE", "Lưu từ phiên nhận diện"
    INTAKE_CANCEL = "INTAKE_CANCEL", "Hủy phiên nhận diện"
    INTAKE_EXPIRE = "INTAKE_EXPIRE", "Phiên nhận diện hết hạn"
    EXTERNAL_OCR_SEND = "EXTERNAL_OCR_SEND", "Gửi ảnh tới API OCR"
    ACCOUNT_LOCK = "ACCOUNT_LOCK", "Khóa tài khoản"
    ACCOUNT_UNLOCK = "ACCOUNT_UNLOCK", "Mở khóa tài khoản"
    PASSWORD_RESET = "PASSWORD_RESET", "Đặt lại mật khẩu"
    BACKUP = "BACKUP", "Sao lưu"
    RESTORE = "RESTORE", "Phục hồi"
