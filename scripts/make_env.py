"""Tạo tệp .env cho lần cài đầu tiên.

- Sinh SECRET_KEY, mật khẩu CSDL, FIELD_ENCRYPTION_KEY và HASH_KEY.
- KHÔNG BAO GIỜ ghi đè .env đã có (tránh mất khóa mã hóa).
- KHÔNG in giá trị khóa ra màn hình.

Chạy:  python scripts/make_env.py
Chỉ dùng thư viện chuẩn (không cần cài Django hay cryptography).
"""

import base64
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
EXAMPLE_PATH = ROOT / ".env.example"


def new_fernet_key():
    """Khóa Fernet: 32 byte ngẫu nhiên, base64 url-safe (giống Fernet.generate_key())."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


def new_hash_key():
    """Khóa băm HMAC: 32 byte ngẫu nhiên, base64 url-safe."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


def main():
    # Console Windows hay dùng cp1252; ép UTF-8 để in được tiếng Việt có dấu.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if ENV_PATH.exists():
        print("Đã có tệp .env, không ghi đè (để không làm mất khóa mã hóa). Không có gì thay đổi.")
        return 0
    if not EXAMPLE_PATH.exists():
        print("Không tìm thấy .env.example.", file=sys.stderr)
        return 1

    values = {
        "SECRET_KEY": secrets.token_urlsafe(50),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
        "FIELD_ENCRYPTION_KEY": new_fernet_key(),
        "HASH_KEY": new_hash_key(),
    }
    lines = []
    for line in EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        key = line.partition("=")[0]
        if "=" in line and not line.startswith("#") and key in values:
            line = f"{key}={values[key]}"
        lines.append(line)
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("Đã tạo tệp .env.")
    print()
    print("QUAN TRỌNG: Cất bản sao FIELD_ENCRYPTION_KEY và HASH_KEY ở nơi riêng")
    print("(USB hoặc giấy niêm phong). Mất khóa là mất dữ liệu đã mã hóa.")
    print("Hai khóa này không nằm trong file sao lưu của hệ thống.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
