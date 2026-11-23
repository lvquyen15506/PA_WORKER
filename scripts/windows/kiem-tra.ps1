# Kiem tra.bat: kiểm tra nhanh tình trạng hệ thống (Docker, các container, khóa, dung lượng đĩa,
# bản sao lưu mới nhất). Dùng khi xử lý sự cố (docs/xu-ly-su-co.md).
param([switch]$NoPause)

. "$PSScriptRoot\common.ps1"

$code = 0
try {
    Write-Title "PA Worker – kiểm tra hệ thống"
    if (-not (Test-DockerRunning)) {
        Stop-WithError "Docker Desktop chưa chạy. Mở Docker Desktop hoặc chạy PA Worker.bat."
    }
    Write-Ok "Docker Desktop đang chạy."
    Show-DiskWarning
    Write-Host ""
    & docker compose ps --format "table {{.Service}}\t{{.State}}\t{{.Status}}"
    if (-not (Test-WebRunning)) {
        Stop-WithError "PA Worker chưa chạy. Chạy PA Worker.bat."
    }
    Write-Host ""
    & docker compose exec -T web python manage.py system_check
    if ($LASTEXITCODE -ne 0) { $code = 1 }
    Write-Host ""
    Write-Host "Dung lượng Docker đang dùng:"
    & docker system df
} catch {
    $code = 1
}
Wait-Close -NoPause:$NoPause
exit $code
