"""Tính toán ngày tháng dùng chung (không thêm thư viện ngoài)."""

import calendar


def add_months(value, months):
    """Cộng (hoặc trừ, nếu âm) số tháng vào date/datetime; ngày vượt cuối tháng thì lùi về
    ngày cuối tháng (31/01 + 1 tháng = 28/02 hoặc 29/02)."""
    index = value.year * 12 + (value.month - 1) + months
    year, month_zero = divmod(index, 12)
    month = month_zero + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def add_years(value, years):
    """Cộng số năm; 29/02 + 1 năm = 28/02."""
    return add_months(value, years * 12)
