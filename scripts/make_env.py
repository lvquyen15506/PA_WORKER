"""Tạo tệp .env cho lần cài đầu tiên, hoặc sửa riêng dòng ALLOWED_HOSTS.

- Sinh SECRET_KEY, mật khẩu CSDL, FIELD_ENCRYPTION_KEY và HASH_KEY.
- KHÔNG BAO GIỜ ghi đè .env đã có (tránh mất khóa mã hóa); với .env đã có chỉ được sửa dòng
  ALLOWED_HOSTS (--allowed-hosts), không đụng tới dòng nào khác.
- KHÔNG in giá trị khóa ra màn hình.

Chạy:
    python scripts/make_env.py --mode demo        # bản Demo (được nạp dữ liệu giả lập)
    python scripts/make_env.py --mode that        # bản Thật (mặc định)
    python scripts/make_env.py --allowed-hosts 192.168.1.20   # thêm IP máy chủ vào ALLOWED_HOSTS
Máy không cài Python thì chạy trong container (PA Worker.bat làm việc này):
    docker run --rm -v "<thư mục PA Worker>:/w" python:3.12-slim python /w/scripts/make_env.py
Chỉ dùng thư viện chuẩn (không cần cài Django hay cryptography).
"""

import argparse
import base64
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = Path(os.environ.get("PA_ENV_PATH") or ROOT / ".env")
EXAMPLE_PATH = ROOT / ".env.example"
DEFAULT_HOSTS = ["localhost", "127.0.0.1"]


def new_fernet_key():
    """Khóa Fernet: 32 byte ngẫu nhiên, base64 url-safe (giống Fernet.generate_key())."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


def new_hash_key():
    """Khóa băm HMAC: 32 byte ngẫu nhiên, base64 url-safe."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


def valid_host(host):
    """Tên máy hoặc địa chỉ IPv4 đơn giản; không nhận dấu * (ALLOWED_HOSTS không dùng *)."""
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789.-")
    return bool(host) and set(host.lower()) <= allowed and not host.startswith((".", "-"))


def set_allowed_hosts(extra):
    """Thêm các host vào dòng ALLOWED_HOSTS của .env đã có. Chỉ đổi đúng dòng đó."""
    hosts = [h.strip() for h in extra.split(",") if h.strip()]
    bad = [h for h in hosts if not valid_host(h)]
    if bad:
        print(f"Địa chỉ không hợp lệ: {', '.join(bad)}. Ví dụ đúng: 192.168.1.20", file=sys.stderr)
        return 1
    if not ENV_PATH.exists():
        print(
            "Chưa có tệp .env. Chạy PA Worker.bat (hoặc make_env.py) để cài trước.",
            file=sys.stderr,
        )
        return 1
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith("ALLOWED_HOSTS="):
            current = [h.strip() for h in line.partition("=")[2].split(",") if h.strip()]
            merged = current + [h for h in hosts if h not in current]
            lines[i] = "ALLOWED_HOSTS=" + ",".join(merged)
            found = True
    if not found:
        lines.append("ALLOWED_HOSTS=" + ",".join(DEFAULT_HOSTS + hosts))
    # Ghi tệp tạm rồi thay thế: không để .env dở dang nếu máy tắt giữa chừng.
    tmp = ENV_PATH.with_name(ENV_PATH.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, ENV_PATH)
    print("Đã cập nhật ALLOWED_HOSTS trong .env. Chạy lại PA Worker.bat để áp dụng.")
    return 0


def main(argv=None):
    # Console Windows hay dùng cp1252; ép UTF-8 để in được tiếng Việt có dấu.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Tạo tệp .env cho PA Worker.")
    parser.add_argument("--mode", choices=["demo", "that"], default="that")
    parser.add_argument(
        "--allowed-hosts", help="Thêm IP/tên máy chủ vào ALLOWED_HOSTS (.env đã có)"
    )
    args = parser.parse_args(argv)
    if args.allowed_hosts:
        return set_allowed_hosts(args.allowed_hosts)
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
        "DEMO_MODE": "1" if args.mode == "demo" else "0",
        "DEBUG": "0",
    }
    lines = []
    for line in EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        key = line.partition("=")[0]
        if "=" in line and not line.startswith("#") and key in values:
            line = f"{key}={values[key]}"
        lines.append(line)
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("Đã tạo tệp .env (" + ("bản Demo" if args.mode == "demo" else "bản Thật") + ").")
    print()
    print("QUAN TRỌNG: Cất bản sao FIELD_ENCRYPTION_KEY và HASH_KEY ở nơi riêng")
    print("(USB hoặc giấy niêm phong). Mất khóa là mất dữ liệu đã mã hóa.")
    print("Hai khóa này không nằm trong file sao lưu; file sao lưu được mã hóa bằng khóa này,")
    print("nên mất khóa thì cũng không phục hồi được bản sao lưu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
