# Hàm dùng chung cho các tệp .bat của PA Worker (Windows PowerShell 5.1).
# Các script khác nạp tệp này bằng:  . "$PSScriptRoot\common.ps1"
# Không bao giờ in giá trị khóa hay mật khẩu trong .env ra màn hình.

# Continue: docker ghi tiến độ ra stderr; PowerShell 5.1 coi đó là lỗi nếu để "Stop". Mọi lệnh
# ngoài được kiểm tra bằng $LASTEXITCODE (Invoke-Native), lỗi thật dừng bằng Stop-WithError.
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root
# Image Python dùng để tạo .env khi máy chưa cài Python (cùng image gốc của Dockerfile).
$PythonImage = "python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b"

function Write-Title([string]$Text) {
    Write-Host ""
    Write-Host "==== $Text ====" -ForegroundColor Cyan
}

function Write-Step([string]$Text) { Write-Host "-> $Text" }
function Write-Ok([string]$Text) { Write-Host "OK: $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "CẢNH BÁO: $Text" -ForegroundColor Yellow }

function Stop-WithError([string]$Text) {
    Write-Host ""
    Write-Host "LỖI: $Text" -ForegroundColor Red
    throw $Text
}

function Invoke-Native {
    # Chạy lệnh ngoài (docker…), dừng với thông báo tiếng Việt khi lệnh lỗi.
    param([string]$Message, [string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { Stop-WithError $Message }
}

function Test-DockerRunning {
    & docker info *> $null
    return ($LASTEXITCODE -eq 0)
}

function Assert-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Stop-WithError "Máy chưa cài Docker Desktop. Xem Hướng dẫn cài đặt, bước 2."
    }
    if (Test-DockerRunning) { return }
    Write-Step "Docker Desktop chưa chạy, đang mở Docker Desktop…"
    $exe = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path $exe) { Start-Process $exe | Out-Null }
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 5
        if (Test-DockerRunning) { Write-Ok "Docker Desktop đã chạy."; return }
    }
    Stop-WithError ("Docker Desktop không khởi động được sau 5 phút. Mở Docker Desktop bằng tay, " +
        "chờ biểu tượng cá voi báo 'Engine running' rồi chạy lại. Xem Xử lý sự cố, mục Docker không chạy.")
}

function Get-EnvValue([string]$Name) {
    # Đọc một biến KHÔNG bí mật trong .env (DEMO_MODE, PA_PORT, ALLOWED_HOSTS).
    if (-not (Test-Path ".env")) { return $null }
    foreach ($line in Get-Content ".env" -Encoding UTF8) {
        if ($line.StartsWith("$Name=")) { return $line.Substring($Name.Length + 1).Trim() }
    }
    return $null
}

function Get-Port {
    # Biến môi trường PA_PORT (nếu đặt) được Compose ưu tiên hơn .env, nên ở đây cũng vậy.
    $port = $env:PA_PORT
    if (-not $port) { $port = Get-EnvValue "PA_PORT" }
    if (-not $port) { $port = "8000" }
    return $port
}

function Get-LanIP {
    # Địa chỉ IPv4 trong mạng nội bộ của máy chủ (bỏ địa chỉ ảo của Docker/WSL).
    $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object {
        $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" -and
        $_.InterfaceAlias -notmatch "vEthernet|WSL|Docker|Loopback|VirtualBox|VMware"
    } | Sort-Object -Property InterfaceMetric
    if ($ips) { return @($ips)[0].IPAddress }
    return $null
}

function Invoke-MakeEnv([string[]]$Arguments) {
    # make_env.py chạy trong container Python: máy không cần cài Python.
    $mount = "${Root}:/w"
    & docker run --rm -v $mount $PythonImage python /w/scripts/make_env.py @Arguments
    if ($LASTEXITCODE -ne 0) { Stop-WithError "Không tạo/sửa được tệp .env." }
}

function Wait-Healthy([int]$TimeoutSeconds = 600) {
    Write-Step "Đang chờ hệ thống sẵn sàng (lần đầu có thể mất vài phút)…"
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $id = (& docker compose ps -q web) 2>$null
        if ($id) {
            $state = (& docker inspect --format "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}" $id) 2>$null
            if ($state -match "running healthy") { Write-Ok "Hệ thống đã sẵn sàng."; return }
            if ($state -match "exited|dead") { break }
        }
        Start-Sleep -Seconds 5
    }
    Write-Host ""
    Write-Host "Nhật ký gần nhất của web:" -ForegroundColor Yellow
    & docker compose logs --no-color --tail 25 web
    Stop-WithError "Hệ thống chưa sẵn sàng. Đọc thông báo phía trên (thường là thiếu hoặc sai khóa trong .env); xem Xử lý sự cố."
}

function Repair-MediaOwner {
    # Bản trước Phase 8 chạy bằng root: đổi chủ thư mục tệp sang người dùng app (một lần, nhanh).
    # Không dùng dấu ngoặc kép trong lệnh: PowerShell 5.1 truyền sai ngoặc kép lồng cho lệnh ngoài.
    $cmd = '[ $(stat -c %u /app/private_media) = 1000 ] || chown -R app:app /app/private_media'
    & docker compose run --rm --no-deps -u root --entrypoint sh web -c $cmd
    if ($LASTEXITCODE -ne 0) { Stop-WithError "Không đổi được quyền thư mục tệp hồ sơ." }
}

function Test-WebRunning {
    $id = (& docker compose ps -q --status running web) 2>$null
    return [bool]$id
}

function Show-DiskWarning {
    $drive = (Get-Item $Root).PSDrive
    $freeGb = [math]::Round($drive.Free / 1GB, 1)
    if ($drive.Free -lt 5GB) {
        Write-Warn "Ổ $($drive.Name): chỉ còn $freeGb GB trống. Xóa bớt bản sao lưu cũ hoặc giải phóng dung lượng (Xử lý sự cố, mục Đầy đĩa)."
    } else {
        Write-Step "Ổ $($drive.Name): còn $freeGb GB trống."
    }
}

function Wait-Close([switch]$NoPause) {
    if (-not $NoPause) {
        Write-Host ""
        Read-Host "Nhấn Enter để đóng cửa sổ" | Out-Null
    }
}
