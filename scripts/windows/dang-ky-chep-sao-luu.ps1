# Đăng ký tác vụ Task Scheduler "PA Worker – chép sao lưu": mỗi ngày lúc 17:30 (và khi đăng nhập
# Windows nếu lỡ giờ) chép các file sao lưu mới sang thư mục đích (ổ đĩa ngoài, ổ mạng…).
# Sao lưu thì container scheduler đã tự làm mỗi ngày; tác vụ này chỉ CHÉP ra nơi khác.
#   powershell -ExecutionPolicy Bypass -File scripts\windows\dang-ky-chep-sao-luu.ps1 -Dest "E:\PA Worker sao luu"
#   thêm -Remove để gỡ tác vụ.
param([string]$Dest = "", [string]$At = "17:30", [switch]$Remove, [switch]$NoPause)

. "$PSScriptRoot\common.ps1"

$taskName = "PA Worker - chep sao luu"
try {
    if ($Remove) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
        Write-Ok "Đã gỡ tác vụ '$taskName'."
    } else {
        if (-not $Dest) { $Dest = Read-Host "Thư mục đích (ví dụ E:\PA Worker sao luu)" }
        if (-not $Dest) { Stop-WithError "Chưa nhập thư mục đích." }
        if (-not (Test-Path $Dest)) { New-Item -ItemType Directory -Path $Dest | Out-Null }
        $script = Join-Path $PSScriptRoot "chep-sao-luu.ps1"
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument (
            "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`" -Dest `"$Dest`"")
        $triggers = @(
            (New-ScheduledTaskTrigger -Daily -At $At),
            (New-ScheduledTaskTrigger -AtLogOn)
        )
        $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings `
            -Description "Chép file sao lưu PA Worker sang $Dest" -Force | Out-Null
        Write-Ok "Đã đăng ký tác vụ '$taskName': mỗi ngày lúc $At và khi đăng nhập, chép sang $Dest."
        Write-Host "Nhật ký chép: backups\chep-sao-luu.log"
    }
    Wait-Close -NoPause:$NoPause
    exit 0
} catch {
    Wait-Close -NoPause:$NoPause
    exit 1
}
