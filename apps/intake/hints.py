"""Gợi ý cho trường không đọc được từ ảnh thẻ (nguồn "Gợi ý", luôn tô vàng, HR phải tích Đã kiểm
tra). Mọi giá trị cố định theo mẫu thẻ khai báo MỘT chỗ ở đây, không viết rải rác.

- Nơi cấp: giá trị cố định theo mẫu thẻ.
- Quốc tịch: "Việt Nam" với thẻ CCCD/Căn cước.
- Có giá trị đến: tính từ ngày sinh và ngày cấp theo mốc tuổi 25, 40, 60 (Luật Căn cước công dân
  và Luật Căn cước). Cấp thẻ trong vòng 2 năm trước một mốc (kể cả đúng ngày 2 năm trước) thì có
  giá trị đến mốc kế tiếp; từ 60 tuổi thẻ không thời hạn (trả None). [Giả định] cách tính ranh giới
  2 năm là bao gồm; doanh nghiệp đối chiếu quy định khi dùng, nên giá trị này luôn tô vàng.
"""

import datetime

from apps.core.choices import IdDocType
from apps.core.dates import add_years

AGE_MILESTONES = (25, 40, 60)
WINDOW_YEARS = 2  # cấp trong vòng 2 năm trước mốc thì tính sang mốc kế tiếp

# Nơi cấp in trên thẻ theo mẫu thẻ (dữ liệu cấu hình, không phải dữ liệu cá nhân).
ISSUE_PLACE_HINT = {
    IdDocType.CCCD_2021.value: "Cục Cảnh sát quản lý hành chính về trật tự xã hội",
    IdDocType.CCCD_2016.value: "Cục Cảnh sát ĐKQL cư trú và DLQG về dân cư",
    IdDocType.CAN_CUOC_2024.value: "Bộ Công an",
}
NATIONALITY_HINT = "Việt Nam"
CAN_CUOC_2024_START = datetime.date(2024, 7, 1)  # Căn cước chỉ cấp từ ngày này (câu 20)


def compute_expiry(date_of_birth, issue_date):
    """Ngày hết hạn theo quy định, hoặc None nếu không thời hạn (cấp từ 60 tuổi, hoặc cấp trong 2
    năm trước 60 tuổi) hoặc dữ liệu không dùng được."""
    if not date_of_birth or not issue_date or issue_date < date_of_birth:
        return None
    milestones = [add_years(date_of_birth, age) for age in AGE_MILESTONES]
    for index, milestone in enumerate(milestones):
        if milestone <= issue_date:
            continue  # đã qua mốc này khi cấp
        if issue_date >= add_years(milestone, -WINDOW_YEARS):
            return milestones[index + 1] if index + 1 < len(milestones) else None
        return milestone
    return None
