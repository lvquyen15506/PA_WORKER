"""Ngân sách thời gian cho một lượt nhận diện (Phase 5, quyết định 5).

Gunicorn timeout 120 giây nên cả lượt (kiểm tra ảnh + QR + OCR + CV) chỉ được dùng tối đa
`INTAKE_TOTAL_BUDGET_SECONDS` (90). Mỗi giai đoạn lấy phần còn lại; hết thì bỏ giai đoạn sau.
"""

import time

from django.conf import settings


class Budget:
    def __init__(self, total=None, clock=time.monotonic):
        self.total = float(settings.INTAKE_TOTAL_BUDGET_SECONDS if total is None else total)
        self._clock = clock
        self._start = clock()
        self.exhausted = False  # đặt True khi có giai đoạn phải bỏ vì hết thời gian

    def elapsed(self):
        return self._clock() - self._start

    def remaining(self):
        return max(0.0, self.total - self.elapsed())

    @property
    def expired(self):
        return self.remaining() <= 0

    def timeout_for(self, cap):
        """Thời gian tối đa cho một lần gọi: nhỏ hơn giữa `cap` và phần còn lại."""
        return min(float(cap), self.remaining())

    def mark_exhausted(self):
        self.exhausted = True
