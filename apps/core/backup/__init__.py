"""Sao lưu và phục hồi (Phase 8, kịch bản nghiệm thu 17, docs/lam-ro-yeu-cau.md câu 31, 49).

- `stream`: mã hóa cả file sao lưu (AES-GCM theo khúc, khóa sinh từ FIELD_ENCRYPTION_KEY).
- `container`: đóng gói nhiều phần (bản dump CSDL, tệp media, manifest) trong một luồng.
- `service`: tạo, kiểm tra, phục hồi bản sao lưu; kiểm tra dung lượng đĩa; xóa bớt bản cũ.

File sao lưu KHÔNG chứa .env, SECRET_KEY hay hai khóa; phục hồi cần đúng FIELD_ENCRYPTION_KEY
và HASH_KEY đã cất riêng khi cài.
"""
