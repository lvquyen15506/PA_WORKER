# Chép các file sao lưu mới (pa-worker-*.pawbk) từ thư mục backups sang ổ đĩa ngoài/thư mục khác.
# Không xóa gì ở thư mục đích. Task Scheduler gọi tệp này mỗi ngày (dang-ky-chep-sao-luu.ps1).
#   powershell -ExecutionPolicy Bypass -File scripts\windows\chep-sao-luu.ps1 -Dest "E:\PA Worker sao luu"
param([Parameter(Mandatory = $true)][string]$Dest)

$ErrorActionPreference = "Stop"
$source = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path "backups"
$log = Join-Path $source "chep-sao-luu.log"

function Write-Log([string]$Text) {
    Add-Content -Path $log -Value ("{0:dd/MM/yyyy HH:mm:ss} {1}" -f (Get-Date), $Text) -Encoding UTF8
}

try {
    if (-not (Test-Path $Dest)) {
        Write-Log "Không thấy thư mục đích $Dest (USB chưa cắm?). Bỏ qua lần này."
        exit 0
    }
    $copied = 0
    foreach ($file in Get-ChildItem -Path $source -Filter "pa-worker-*.pawbk") {
        $target = Join-Path $Dest $file.Name
        if (-not (Test-Path $target) -or (Get-Item $target).Length -ne $file.Length) {
            Copy-Item -Path $file.FullName -Destination $target -Force
            $copied++
        }
    }
    Write-Log "Đã chép $copied file sao lưu sang $Dest."
} catch {
    Write-Log "LỖI khi chép sao lưu: $($_.Exception.Message)"
    exit 1
}
