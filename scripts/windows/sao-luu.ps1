# Sao luu.bat: sao lưu ngay CSDL và tệp hồ sơ ra thư mục backups (file mã hóa, có ngày giờ).
# Hệ thống phải đang chạy (PA Worker.bat). Scheduler cũng tự sao lưu mỗi ngày một lần.
param([switch]$NoPause)

. "$PSScriptRoot\common.ps1"

try {
    Write-Title "PA Worker – sao lưu"
    Assert-Docker
    if (-not (Test-WebRunning)) {
        Stop-WithError "PA Worker chưa chạy. Chạy PA Worker.bat trước rồi sao lưu."
    }
    Show-DiskWarning
    Invoke-Native "Sao lưu không thành công (xem thông báo phía trên)." "docker" @("compose", "exec", "-T", "web", "python", "manage.py", "backup")
    Write-Host ""
    Write-Host "File sao lưu nằm trong thư mục: $(Join-Path $Root 'backups')"
    Write-Host "Hãy chép file mới nhất ra USB hoặc ổ đĩa ngoài (Hướng dẫn cài đặt, mục Sao lưu)."
    Wait-Close -NoPause:$NoPause
    exit 0
} catch {
    Wait-Close -NoPause:$NoPause
    exit 1
}
