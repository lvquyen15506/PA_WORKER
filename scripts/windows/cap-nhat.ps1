# Cap nhat.bat: cập nhật PA Worker lên phiên bản mới mà không mất dữ liệu.
# Trước khi chạy: giải nén bản mới và chép ĐÈ lên thư mục này (giữ nguyên tệp .env và thư mục
# backups). Các bước: sao lưu bằng bản đang chạy -> dựng image mới -> đổi quyền thư mục tệp (một
# lần) -> khởi động (web tự cập nhật CSDL) -> kiểm tra hệ thống, in phiên bản.
param([switch]$NoPause)

. "$PSScriptRoot\common.ps1"

try {
    Write-Title "PA Worker – cập nhật phiên bản"
    Assert-Docker
    if (-not (Test-Path ".env")) {
        Stop-WithError "Không thấy tệp .env. Khi chép bản mới phải giữ nguyên tệp .env cũ (hoặc chép lại từ USB)."
    }
    Show-DiskWarning

    Write-Step "Bước 1/4: sao lưu dữ liệu bằng phiên bản đang cài…"
    if (-not (Test-WebRunning)) {
        # Khởi động bản đang cài (image cũ) để sao lưu; chưa có image thì là máy mới, bỏ qua.
        $image = (& docker image ls -q pa_worker-web) 2>$null
        if ($image) {
            Invoke-Native "Không khởi động được bản đang cài để sao lưu." "docker" @("compose", "up", "-d", "--no-build")
            Wait-Healthy
        }
    }
    if (Test-WebRunning) {
        Invoke-Native "Sao lưu trước khi cập nhật không thành công; dừng cập nhật." "docker" @("compose", "exec", "-T", "web", "python", "manage.py", "backup")
    } else {
        Write-Warn "Chưa có bản cài nào đang chạy: bỏ qua sao lưu."
    }

    Write-Step "Bước 2/4: dựng phiên bản mới (cần Internet, có thể mất vài phút)…"
    Invoke-Native "Không dựng được phiên bản mới." "docker" @("compose", "build")

    Write-Step "Bước 3/4: khởi động phiên bản mới (tự cập nhật CSDL)…"
    Invoke-Native "Không khởi động được CSDL." "docker" @("compose", "up", "-d", "db")
    Repair-MediaOwner
    Invoke-Native "Không khởi động được phiên bản mới." "docker" @("compose", "up", "-d")
    Wait-Healthy

    Write-Step "Bước 4/4: kiểm tra hệ thống…"
    & docker compose exec -T web python manage.py system_check
    Write-Ok "Đã cập nhật. Nếu có lỗi, phục hồi bản sao lưu vừa tạo bằng Phuc hoi.bat (cùng phiên bản cũ)."
    Wait-Close -NoPause:$NoPause
    exit 0
} catch {
    Wait-Close -NoPause:$NoPause
    exit 1
}
