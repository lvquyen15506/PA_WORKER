"""Validator mật khẩu: tối thiểu 8 ký tự và có cả chữ lẫn số. Thông báo tiếng Việt
(bản dịch có sẵn của Django thiếu câu này nên không dùng MinimumLengthValidator)."""

import re

from django.core.exceptions import ValidationError

MIN_LENGTH = 8


class MinLengthValidator:
    def validate(self, password, user=None):
        if len(password) < MIN_LENGTH:
            raise ValidationError(
                f"Mật khẩu quá ngắn, cần ít nhất {MIN_LENGTH} ký tự.", code="password_too_short"
            )

    def get_help_text(self):
        return f"Mật khẩu cần ít nhất {MIN_LENGTH} ký tự."


class LetterAndDigitValidator:
    def validate(self, password, user=None):
        if not re.search(r"[^\W\d_]", password) or not re.search(r"\d", password):
            raise ValidationError(
                "Mật khẩu phải có cả chữ và số.", code="password_no_letter_or_digit"
            )

    def get_help_text(self):
        return "Mật khẩu tối thiểu 8 ký tự, gồm cả chữ và số."
