"""apps.core.dates: cộng tháng/năm không dùng thư viện ngoài."""

import datetime

import pytest

from apps.core.dates import add_months, add_years

D = datetime.date


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (D(2026, 1, 15), 6, D(2026, 7, 15)),
        (D(2026, 1, 31), 1, D(2026, 2, 28)),  # năm thường: lùi về cuối tháng
        (D(2028, 1, 31), 1, D(2028, 2, 29)),  # năm nhuận
        (D(2026, 8, 31), 1, D(2026, 9, 30)),
        (D(2026, 11, 30), 3, D(2027, 2, 28)),  # qua năm
        (D(2026, 3, 1), 12, D(2027, 3, 1)),
        (D(2026, 7, 15), -6, D(2026, 1, 15)),  # trừ tháng
        (D(2026, 3, 31), -1, D(2026, 2, 28)),
        (D(2026, 1, 10), -1, D(2025, 12, 10)),  # trừ qua năm
        (D(2026, 5, 5), 0, D(2026, 5, 5)),
        (D(2026, 1, 1), 24, D(2028, 1, 1)),
    ],
)
def test_add_months(start, months, expected):
    assert add_months(start, months) == expected


def test_add_years_ngay_nhuan_ve_28_2():
    assert add_years(D(2028, 2, 29), 1) == D(2029, 2, 28)
    assert add_years(D(2028, 2, 29), 4) == D(2032, 2, 29)
    assert add_years(D(2020, 6, 15), 10) == D(2030, 6, 15)


def test_add_months_giu_nguyen_gio_cua_datetime():
    moment = datetime.datetime(2026, 1, 31, 15, 30)
    assert add_months(moment, 1) == datetime.datetime(2026, 2, 28, 15, 30)
