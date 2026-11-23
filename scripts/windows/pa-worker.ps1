# PA Worker.bat: khởi động PA Worker (lần đầu thì cài đặt).
# - Kiểm tra Docker Desktop (chưa chạy thì mở).
# - Chưa có .env: hỏi bản Thật/Demo, tạo .env (sinh khóa), nhắc cất khóa.
# - Đề nghị thêm IP máy chủ vào ALLOWED_HOSTS để máy khác trong mạng truy cập.
# - docker compose up -d --build, chờ web sẵn sàng.
# - Lần đầu (chưa có tài khoản): bản Demo nạp dữ liệu giả lập; bản Thật tạo Admin đầu tiên.
#   Mật khẩu tạm chỉ hiện trên màn hình này.
# - Mở trình duyệt vào trang đăng nhập.
# Tham số (dùng khi kiểm thử tự động): -Mode demo|that -AdminUser ten -AddLanIp -NoBrowser -NoPause
param(
    [ValidateSet("", "demo", "that")][string]$Mode = "",
    [string]$AdminUser = "",
    [switch]$AddLanIp,
    [switch]$NoBrowser,
    [switch]$NoPause
)

. "$PSScriptRoot\common.ps1"

try {
    Write-Title "PA Worker – khởi động"
    Assert-Docker
    Show-DiskWarning

    # ----- Lần đầu: tạo .env -----
    if (-not (Test-Path ".env")) {
        Write-Title "Cài đặt lần đầu"
        if (-not $Mode) {
            Write-Host "Chọn loại bản cài:"
            Write-Host "  1. Bản Thật – dùng cho dữ liệu công nhân thật của doanh nghiệp"
            Write-Host "  2. Bản Demo – có sẵn 4 tài khoản mẫu và khoảng 500 hồ sơ giả lập để trình diễn"
            $choice = Read-Host "Gõ 1 hoặc 2 rồi nhấn Enter"
            if ($choice -eq "2") { $Mode = "demo" } elseif ($choice -eq "1") { $Mode = "that" }
            else { Stop-WithError "Chỉ gõ 1 hoặc 2. Chạy lại PA Worker.bat." }
        }
        Write-Step "Đang tạo tệp .env và sinh khóa mã hóa…"
        Invoke-MakeEnv @("--mode", $Mode)
        Write-Host ""
        Write-Host "QUAN TRỌNG – CẤT KHÓA MÃ HÓA" -ForegroundColor Yellow
        Write-Host "Tệp .env trong thư mục $Root chứa khóa mã hóa dữ liệu."
        Write-Host "Chép tệp .env vào USB riêng (hoặc in ra giấy và niêm phong), cất ở nơi an toàn."
        Write-Host "Mất khóa thì KHÔNG đọc lại được dữ liệu đã mã hóa và KHÔNG phục hồi được bản sao lưu."
        if (-not $NoPause) { Read-Host "Đã cất bản sao tệp .env? Nhấn Enter để tiếp tục" | Out-Null }
    }

    # ----- Truy cập từ máy khác trong mạng: ALLOWED_HOSTS -----
    $ip = Get-LanIP
    $hosts = Get-EnvValue "ALLOWED_HOSTS"
    if ($ip -and $hosts -and -not (($hosts -split ",") -contains $ip)) {
        $add = $AddLanIp
        if (-not $add -and -not $NoPause) {
            Write-Host ""
            Write-Host "Địa chỉ IP của máy này trong mạng nội bộ: $ip"
            $answer = Read-Host "Cho phép máy khác trong mạng truy cập bằng địa chỉ này? Gõ C (có) hoặc K (không)"
            $add = ($answer -match "^[cCyY]")
        }
        if ($add) {
            Invoke-MakeEnv @("--allowed-hosts", $ip)
            Write-Step "Nhớ mở cổng $(Get-Port) trên tường lửa: chạy scripts\windows\mo-cong-8000.ps1 (Hướng dẫn cài đặt, bước 6)."
        }
    }

    # ----- Khởi động -----
    Write-Title "Khởi động hệ thống"
    Write-Step "Đang dựng và chạy các container (lần đầu cần Internet và có thể mất 10–20 phút)…"
    Invoke-Native "Không khởi động được hệ thống (docker compose build)." "docker" @("compose", "build")
    Invoke-Native "Không khởi động được CSDL." "docker" @("compose", "up", "-d", "db")
    Repair-MediaOwner
    Invoke-Native "Không khởi động được hệ thống (docker compose up)." "docker" @("compose", "up", "-d")
    Wait-Healthy

    # ----- Lần đầu: tài khoản -----
    $hasUser = (& docker compose exec -T web python manage.py shell -c "from apps.accounts.models import User;print(User.objects.exists())" 2>$null | Select-Object -Last 1)
    if ($hasUser -match "False") {
        if ((Get-EnvValue "DEMO_MODE") -eq "1") {
            Write-Title "Nạp dữ liệu giả lập (bản Demo)"
            Write-Step "Đang tạo 4 tài khoản mẫu và khoảng 500 hồ sơ giả lập (khoảng 1–2 phút)…"
            Invoke-Native "Không nạp được dữ liệu giả lập." "docker" @("compose", "exec", "-T", "web", "python", "manage.py", "seed_demo")
            Write-Host "Ghi lại các mật khẩu tạm ở trên; mỗi tài khoản phải đổi mật khẩu khi đăng nhập lần đầu." -ForegroundColor Yellow
        } else {
            Write-Title "Tạo tài khoản Admin đầu tiên"
            if (-not $AdminUser) {
                if ($NoPause) { $AdminUser = "admin" }
                else {
                    $AdminUser = Read-Host "Tên đăng nhập cho Admin (Enter để dùng 'admin')"
                    if (-not $AdminUser) { $AdminUser = "admin" }
                }
            }
            Invoke-Native "Không tạo được tài khoản Admin." "docker" @("compose", "exec", "-T", "web", "python", "manage.py", "create_first_admin", "--username", $AdminUser)
            Write-Host "Ghi lại mật khẩu tạm ở trên; khi đăng nhập lần đầu hệ thống yêu cầu đổi mật khẩu." -ForegroundColor Yellow
        }
    }

    $port = Get-Port
    Write-Title "PA Worker đã chạy"
    Write-Host "Trên máy này:            http://localhost:$port"
    $hosts = Get-EnvValue "ALLOWED_HOSTS"
    if ($ip -and $hosts -and (($hosts -split ",") -contains $ip)) {
        Write-Host "Từ máy khác trong mạng:  http://${ip}:$port"
    }
    if (-not $NoBrowser) { Start-Process "http://localhost:$port/dang-nhap/" | Out-Null }
    Wait-Close -NoPause:$NoPause
    exit 0
} catch {
    Wait-Close -NoPause:$NoPause
    exit 1
}
