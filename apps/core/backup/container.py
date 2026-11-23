"""Đóng gói nhiều phần trong luồng sao lưu (bên trong lớp mã hóa của `stream`).

Không dùng tar vì tar phải biết trước kích thước mỗi tệp, còn bản dump CSDL được đẩy thẳng từ
pg_dump vào luồng (không ghi bản rõ ra đĩa). Định dạng:

    phần     = b"F" | độ dài tên (2 byte) | tên UTF-8 | các khối | 0 (4 byte)
    một khối = độ dài (4 byte) | dữ liệu
    kết thúc = b"E"

Tên phần: "db.dump", "media/<đường dẫn tương đối>", "manifest.json". Khi đọc, tên được kiểm tra
(không tuyệt đối, không có "..") để không ghi ra ngoài thư mục đích.
"""

import struct
from pathlib import PurePosixPath

from .stream import MSG_CORRUPT, BackupError

ENTRY = b"F"
END = b"E"
NAME_LEN = struct.Struct(">H")
BLOCK_LEN = struct.Struct(">I")
BLOCK_SIZE = 1024 * 1024


def write_entry(writer, name, blocks):
    """Ghi một phần; `blocks` là các khối bytes. Trả tổng số byte dữ liệu."""
    encoded = name.encode("utf-8")
    writer.write(ENTRY + NAME_LEN.pack(len(encoded)) + encoded)
    total = 0
    for block in blocks:
        if block:
            writer.write(BLOCK_LEN.pack(len(block)))
            writer.write(block)
            total += len(block)
    writer.write(BLOCK_LEN.pack(0))
    return total


def write_end(writer):
    writer.write(END)


def _read_exact(reader, size):
    data = reader.read(size)
    if len(data) != size:
        raise BackupError(MSG_CORRUPT)
    return data


def safe_name(name):
    """Tên phần hợp lệ: đường dẫn tương đối, không có '..', không rỗng."""
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name or "\x00" in name:
        raise BackupError(MSG_CORRUPT)
    return name


def read_entries(reader):
    """Sinh (tên, các khối dữ liệu). Phải đọc hết các khối của một phần trước khi sang phần sau."""
    while True:
        kind = _read_exact(reader, 1)
        if kind == END:
            if reader.read(1):
                raise BackupError(MSG_CORRUPT)
            return
        if kind != ENTRY:
            raise BackupError(MSG_CORRUPT)
        (length,) = NAME_LEN.unpack(_read_exact(reader, NAME_LEN.size))
        try:
            name = _read_exact(reader, length).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BackupError(MSG_CORRUPT) from exc
        safe_name(name)
        yield name, _blocks(reader)


def _blocks(reader):
    while True:
        (length,) = BLOCK_LEN.unpack(_read_exact(reader, BLOCK_LEN.size))
        if length == 0:
            return
        if length > 64 * BLOCK_SIZE:
            raise BackupError(MSG_CORRUPT)
        yield _read_exact(reader, length)
