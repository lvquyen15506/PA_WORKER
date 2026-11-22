"""API OCR bên ngoài: tùy chọn, tắt mặc định (docs/yeu-cau.md mục V bước 4).

Phase 5 chỉ làm phần cài đặt, cảnh báo và ghi nhật ký. CHƯA có mã gửi dữ liệu ra mạng: chưa chọn
nhà cung cấp cụ thể (quyết định 23/11/2026). Khi có, mọi lần gửi phải gọi `log_external_send`
TRƯỚC khi gửi ảnh; khóa API chỉ đọc từ `settings.EXTERNAL_OCR_API_KEY` (lấy từ .env).
"""

from apps.audit.services import log
from apps.core.choices import AuditAction
from apps.core.models import SystemSetting


def is_enabled():
    return SystemSetting.load().external_ocr_enabled


def log_external_send(user, session, request=None):
    """Ghi nhật ký EXTERNAL_OCR_SEND. note chỉ mô tả việc, không chứa tên người hay tên tệp."""
    return log(
        AuditAction.EXTERNAL_OCR_SEND,
        user=user,
        obj=session,
        note="Gửi ảnh giấy tờ tới API OCR bên ngoài",
        request=request,
    )
