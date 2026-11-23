# Phuc hoi.bat: phục hồi dữ liệu từ một file sao lưu trong thư mục backups.
# - Liệt kê các file sao lưu, chọn một file, gõ PHUC HOI để xác nhận.
# - Dừng web và scheduler, phục hồi (kiểm tra file và khóa trước; dữ liệu đang có được tự sao lưu
#   trước khi thay), rồi khởi động lại.
# - Dùng được trên bản cài mới (máy mới): chép .env cũ (từ USB) và file sao lưu vào thư mục
#   backups trước, rồi chạy Phuc hoi.bat (không cần chạy PA Worker.bat trước).
# Tham số (kiểm thử tự động): -File ten-file.pawbk -Yes -NoPause
param([string]$File = "", [switch]$Yes, [switch]$NoPause)

. "$PSScriptRoot\common.ps1"

try {
    Write-Title "PA Worker – phục hồi từ bản sao lưu"
    Assert-Docker
    if (-not (Test-Path ".env")) {
        Stop-WithError ("Chưa có tệp .env. Chép tệp .env đã cất (USB) vào thư mục $Root rồi chạy lại. " +
            "Phục hồi cần đúng khóa mã hóa của bản sao lưu.")
    }
    $dir = Join-Path $Root "backups"
    $files = @(Get-ChildItem -Path $dir -Filter "pa-worker-*.pawbk" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending)
    if (-not $File) {
        if ($files.Count -eq 0) { Stop-WithError "Thư mục $dir chưa có file sao lưu nào (pa-worker-....pawbk)." }
        Write-Host "Các file sao lưu (mới nhất ở trên):"
        for ($i = 0; $i -lt $files.Count; $i++) {
            $size = [math]::Round($files[$i].Length / 1MB, 1)
            Write-Host ("  {0}. {1}  ({2} MB, {3:dd/MM/yyyy HH:mm})" -f ($i + 1), $files[$i].Name, $size, $files[$i].LastWriteTime)
        }
        $pick = Read-Host "Gõ số thứ tự file cần phục hồi"
        $n = 0
        if (-not [int]::TryParse($pick, [ref]$n) -or $n -lt 1 -or $n -gt $files.Count) {
            Stop-WithError "Số thứ tự không đúng. Chạy lại Phuc hoi.bat."
        }
        $File = $files[$n - 1].Name
    }
    $File = Split-Path $File -Leaf
    if (-not (Test-Path (Join-Path $dir $File))) { Stop-WithError "Không có file $File trong thư mục $dir." }

    if (-not $Yes) {
        Write-Host ""
        Write-Host "Phục hồi sẽ THAY TOÀN BỘ dữ liệu đang có bằng dữ liệu trong $File." -ForegroundColor Yellow
        Write-Host "Dữ liệu đang có sẽ được tự sao lưu trước (file pa-worker-truoc-phuc-hoi-....pawbk)."
        $confirm = Read-Host "Gõ PHUC HOI (chữ in hoa) để xác nhận"
        if ($confirm -cne "PHUC HOI") { Stop-WithError "Chưa xác nhận; không thay đổi gì." }
    }

    Write-Step "Đang chuẩn bị (dựng image nếu là máy mới)…"
    Invoke-Native "Không dựng được image." "docker" @("compose", "build")
    Invoke-Native "Không khởi động được CSDL." "docker" @("compose", "up", "-d", "db")
    Write-Step "Đang dừng web và scheduler…"
    & docker compose stop web scheduler
    Repair-MediaOwner
    $ok = $true
    & docker compose run --rm --no-deps web python manage.py restore $File --yes
    if ($LASTEXITCODE -ne 0) { $ok = $false }
    Write-Step "Đang khởi động lại hệ thống…"
    Invoke-Native "Không khởi động lại được hệ thống." "docker" @("compose", "up", "-d")
    Wait-Healthy
    if (-not $ok) {
        Stop-WithError "Phục hồi không thành công (xem thông báo phía trên). Dữ liệu đang có giữ nguyên."
    }
    Write-Ok "Đã phục hồi từ $File. Đăng nhập lại để kiểm tra dữ liệu."
    Wait-Close -NoPause:$NoPause
    exit 0
} catch {
    Wait-Close -NoPause:$NoPause
    exit 1
}
