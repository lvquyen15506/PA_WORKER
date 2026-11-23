"""Mã hóa luồng cho file sao lưu (docs/lam-ro-yeu-cau.md câu 49 mục 3).

Định dạng (phiên bản 1):

    phần đầu  = MAGIC (6 byte) | muối (16) | tiền tố nonce (8) | giá trị kiểm tra khóa (16)
    mỗi khúc  = cờ khúc cuối (1) | độ dài bản mã (4, big-endian) | bản mã AES-GCM

- Khóa AES-256 = HKDF-SHA256(FIELD_ENCRYPTION_KEY, muối riêng mỗi file, info cố định). Cùng một
  khóa .env nhưng mỗi file có khóa con khác nhau.
- Nonce khúc i = tiền tố nonce | i (4 byte). Dữ liệu xác thực kèm (AAD) = phần đầu | i | cờ khúc
  cuối: sửa một byte, đổi thứ tự khúc, ghép khúc của file khác hay cắt bớt phần cuối đều bị phát
  hiện. Khúc cuối luôn có (có thể rỗng); hết dữ liệu mà chưa gặp khúc cuối = file bị cắt cụt.
- Giá trị kiểm tra khóa (HMAC của khóa con) cho phép báo rõ "sai khóa" thay vì "file hỏng".
- Mỗi khúc tối đa 1 MiB bản rõ, nên mã hóa/giải mã không cần nạp cả file vào bộ nhớ.
"""

import base64
import hashlib
import hmac
import os
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"PAWBK\x01"  # "PA Worker backup", định dạng 1
INFO = b"pa-worker-backup-v1"
CHUNK_SIZE = 1024 * 1024
TAG_SIZE = 16
HEADER = struct.Struct(">6s16s8s16s")
RECORD = struct.Struct(">BI")
MAX_CHUNKS = 2**32


class BackupError(Exception):
    """Lỗi sao lưu/phục hồi; thông điệp tiếng Việt hiển thị thẳng cho người dùng."""


MSG_NOT_BACKUP = "Tệp này không phải file sao lưu PA Worker."
MSG_WRONG_KEY = (
    "Khóa FIELD_ENCRYPTION_KEY trong tệp .env không khớp với file sao lưu này (hoặc phần đầu file "
    "bị hỏng). Hãy chép đúng khóa đã cất khi cài đặt (USB hoặc giấy niêm phong) vào .env rồi thử "
    "lại. Không có đúng khóa thì không đọc được bản sao lưu."
)
MSG_CORRUPT = (
    "File sao lưu bị hỏng hoặc đã bị sửa (không qua được kiểm tra toàn vẹn). "
    "Hãy dùng một bản sao lưu khác."
)
MSG_TRUNCATED = (
    "File sao lưu bị thiếu phần cuối (chép chưa xong hoặc bị cắt). Hãy dùng một bản sao lưu khác."
)


def derive_key(field_key, salt):
    """Khóa AES-256 riêng cho một file sao lưu, sinh từ FIELD_ENCRYPTION_KEY và muối của file."""
    ikm = base64.urlsafe_b64decode(field_key)
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=INFO).derive(ikm)


def key_check(key):
    return hmac.new(key, b"pa-worker-backup-key-check", hashlib.sha256).digest()[:16]


def _nonce(prefix, index):
    return prefix + struct.pack(">I", index)


def _aad(header, index, final):
    return header + struct.pack(">QB", index, int(final))


class EncryptingWriter:
    """Đối tượng giống tệp (chỉ có write/close): ghi bản rõ vào, bản mã ra `raw`."""

    def __init__(self, raw, field_key):
        self.raw = raw
        salt = os.urandom(16)
        self.prefix = os.urandom(8)
        key = derive_key(field_key, salt)
        self.aead = AESGCM(key)
        self.header = HEADER.pack(MAGIC, salt, self.prefix, key_check(key))
        raw.write(self.header)
        self.buffer = bytearray()
        self.index = 0
        self.closed = False

    def write(self, data):
        self.buffer += data
        # Lớn hơn hẳn CHUNK_SIZE mới xả, để khúc cuối luôn giữ phần còn lại.
        while len(self.buffer) > CHUNK_SIZE:
            self._emit(bytes(self.buffer[:CHUNK_SIZE]), final=False)
            del self.buffer[:CHUNK_SIZE]
        return len(data)

    def _emit(self, plain, final):
        if self.index >= MAX_CHUNKS:
            raise BackupError("File sao lưu quá lớn.")
        cipher = self.aead.encrypt(
            _nonce(self.prefix, self.index), plain, _aad(self.header, self.index, final)
        )
        self.raw.write(RECORD.pack(int(final), len(cipher)))
        self.raw.write(cipher)
        self.index += 1

    def close(self):
        if not self.closed:
            self._emit(bytes(self.buffer), final=True)
            self.buffer.clear()
            self.closed = True


class DecryptingReader:
    """Đọc file sao lưu đã mã hóa, trả bản rõ qua read(n). Lỗi toàn vẹn -> BackupError."""

    def __init__(self, raw, field_key):
        self.raw = raw
        header = raw.read(HEADER.size)
        if len(header) < HEADER.size or not header.startswith(MAGIC):
            raise BackupError(MSG_NOT_BACKUP)
        _magic, salt, self.prefix, check = HEADER.unpack(header)
        key = derive_key(field_key, salt)
        if not hmac.compare_digest(key_check(key), check):
            raise BackupError(MSG_WRONG_KEY)
        self.header = header
        self.aead = AESGCM(key)
        self.chunks = self._chunks()
        self.pending = b""
        self.eof = False

    def _chunks(self):
        index = 0
        while True:
            record = self.raw.read(RECORD.size)
            if len(record) < RECORD.size:
                raise BackupError(MSG_TRUNCATED)
            final, length = RECORD.unpack(record)
            if final not in (0, 1) or length > CHUNK_SIZE + TAG_SIZE:
                raise BackupError(MSG_CORRUPT)
            cipher = self.raw.read(length)
            if len(cipher) < length:
                raise BackupError(MSG_TRUNCATED)
            try:
                plain = self.aead.decrypt(
                    _nonce(self.prefix, index), cipher, _aad(self.header, index, final)
                )
            except InvalidTag as exc:
                raise BackupError(MSG_CORRUPT) from exc
            yield plain
            index += 1
            if final:
                if self.raw.read(1):  # còn dữ liệu sau khúc cuối: file bị ghép thêm
                    raise BackupError(MSG_CORRUPT)
                return

    def read(self, size):
        """Đọc đúng `size` byte (ít hơn khi hết dữ liệu)."""
        out = bytearray(self.pending)
        while len(out) < size and not self.eof:
            try:
                out += next(self.chunks)
            except StopIteration:
                self.eof = True
        self.pending = bytes(out[size:])
        return bytes(out[:size])
