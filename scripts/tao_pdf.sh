#!/usr/bin/env bash
# Tạo .pdf từ 3 .docx trong docs/ban-giao/ bằng LibreOffice chạy trong container
# tạm (docker run --rm, KHÔNG gắn LibreOffice vào image dự án).
# Chạy trên Git Bash (Windows). Yêu cầu: đã chạy scripts/tao_tai_lieu_word.py trước.
#
# Font: .docx ghi "Segoe UI" (font hệ thống Windows). Container Linux không có
# Segoe UI nên LibreOffice tự thay bằng font có sẵn (DejaVu Sans/Liberation,
# đều đủ dấu tiếng Việt) -> PDF vẫn đọc đúng tiếng Việt. Nếu muốn PDF đúng hệt
# font Windows, copy C:\Windows\Fonts\seg*.ttf vào thư mục fonts/ cạnh repo
# rồi chạy: GANTI_FONT=1 bash scripts/tao_pdf.sh
set -euo pipefail

cd "$(dirname "$0")/.."
WINROOT=$(pwd -W)   # đường Windows của repo (để map volume vào container)
REPO_UNIX=$(pwd)    # đường Git-Bash/Unix của repo
BANGIAO="$REPO_UNIX/docs/ban-giao"

rm -rf "$BANGIAO/pdf-tam"; mkdir -p "$BANGIAO/pdf-tam"

# (tuỳ chọn) gắn font Segoe UI vào container khi có
FONTVOLUME=""
if [ "${GANTI_FONT:-0}" = "1" ] && [ -d "$REPO_UNIX/fonts" ]; then
  FONTVOLUME=" -v $REPO_UNIX/fonts:/fonts-nguoi-dung:ro"
fi

# Chưa có image libreoffice:latest trên máy thì dựng một image tạm từ Debian (chỉ cần một lần,
# image này không thuộc dự án và không vào bản phát hành).
if ! docker image inspect libreoffice:latest >/dev/null 2>&1; then
  echo "Dựng image LibreOffice tạm (lần đầu, vài phút)..."
  docker build -t libreoffice:latest - <<'DOCKERFILE'
FROM debian:trixie-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends libreoffice-writer fonts-dejavu fonts-liberation fontconfig \
 && rm -rf /var/lib/apt/lists/*
DOCKERFILE
fi

echo "Chạy LibreOffice (container tạm) để tạo PDF..."
docker run --rm \
  -v "$WINROOT:/w" \
  -v "$WINROOT/docs/ban-giao/pdf-tam:/out" \
  $FONTVOLUME \
  --entrypoint sh \
  libreoffice:latest \
  -c "
    set -e
    if [ -d /fonts-nguoi-dung ] && ls /fonts-nguoi-dung/*.ttf >/dev/null 2>&1; then
      mkdir -p /usr/share/fonts/truetype/custom
      cp /fonts-nguoi-dung/*.ttf /usr/share/fonts/truetype/custom/
      fc-cache -f >/dev/null 2>&1 || true
    fi
    mkdir -p /tmp/lo
    cd /w/docs/ban-giao
    for f in Pa-Worker-*.docx; do
      /usr/bin/soffice --headless -env:UserInstallation=file:///tmp/lo \
        --convert-to pdf --outdir /out \"/w/docs/ban-giao/\$f\"
    done
    echo 'PDF đã tạo:'; ls -1 /out/*.pdf
  "

# Đưa PDF từ thư mục tạm về docs/ban-giao/ (cạnh .docx) để bước kiểm tra đọc được.
mv -f "$BANGIAO"/pdf-tam/*.pdf "$BANGIAO"/

echo "=== Kiểm tra (pdfplumber trong container web) ==="
docker compose exec -T web python - <<'PYEOF'
import pdfplumber, glob
for path in sorted(glob.glob("docs/ban-giao/Pa-Worker-*.pdf")):
    with pdfplumber.open(path) as pdf:
        n_trang = len(pdf.pages)
        n_ong = sum(len(pg.images) for pg in pdf.pages)
        n_khung = sum(1 for pg in pdf.pages if "ẢNH CẦN CHỤP" in (pg.extract_text() or ""))
        print(f"{path}: {n_trang} trang, {n_ong} ảnh nhúng, {n_khung} trang có [ẢNH CẦN CHỤP]")
PYEOF
echo "Xong. PDF nằm trong docs/ban-giao/. (Thư mục pdf-tam tạm đã giữ để bạn kiểm tra, chạy lại sẽ xoá.)"
