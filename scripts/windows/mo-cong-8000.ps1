# Mở cổng PA Worker (mặc định 8000) trên Windows Defender Firewall cho mạng Private, để máy khác
# trong mạng nội bộ truy cập được. Tự xin quyền Administrator (Windows hỏi "Yes/No").
# Chạy: nhấp chuột phải tệp này -> Run with PowerShell.
param([switch]$NoPause)

. "$PSScriptRoot\common.ps1"

$port = Get-Port
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Step "Cần quyền Administrator để sửa tường lửa; Windows sẽ hỏi xác nhận."
    Start-Process powershell -Verb RunAs -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"")
    exit 0
}

try {
    $name = "PA Worker (cổng $port)"
    if (Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue) {
        Write-Ok "Đã có quy tắc tường lửa '$name'."
    } else {
        New-NetFirewallRule -DisplayName $name -Direction Inbound -Protocol TCP -LocalPort $port `
            -Profile Private -Action Allow | Out-Null
        Write-Ok "Đã mở cổng $port (TCP, chiều vào) cho mạng Private."
    }
    Write-Host "Kiểm tra mạng Wi-Fi/LAN của máy chủ đang đặt là Private (Settings > Network & internet)."
} catch {
    Write-Host "LỖI: không sửa được tường lửa: $($_.Exception.Message)" -ForegroundColor Red
}
Wait-Close -NoPause:$NoPause
