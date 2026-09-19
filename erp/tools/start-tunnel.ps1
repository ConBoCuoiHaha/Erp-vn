# Mở ERP LiFeOOD ra Internet qua Microsoft Dev Tunnels, link HTTPS cố định. Chạy bằng start-tunnel.bat.
# Lần đầu: mở trình duyệt để bạn đăng nhập tài khoản Microsoft hoặc GitHub (chỉ bạn làm, script không lưu mật khẩu).
# Đóng cửa sổ hoặc bấm Ctrl+C là tắt link; app trên máy vẫn chạy.
$ErrorActionPreference = 'Continue'  # lệnh ngoài (docker, devtunnel) kiểm bằng $LASTEXITCODE
Set-Location (Split-Path $PSScriptRoot -Parent)
$idFile = '.tunnel-id'
$opts = @('--host-header', 'unchanged', '--origin-header', 'unchanged')  # Odoo cần thấy đúng địa chỉ công khai
function Step($m) { Write-Host "`n>> $m" -ForegroundColor Cyan }

if (-not (Get-Command devtunnel -ErrorAction SilentlyContinue)) {
    Step 'Cài công cụ devtunnel của Microsoft'
    winget install -e --id Microsoft.devtunnel --accept-source-agreements --accept-package-agreements
    $env:Path += ";$env:LOCALAPPDATA\Microsoft\WinGet\Links"
}

Step 'Kiểm tra Docker'
docker info *> $null
if ($LASTEXITCODE) {
    Start-Process "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    for ($i = 0; $i -lt 60 -and $LASTEXITCODE; $i++) { Start-Sleep 5; docker info *> $null }
    if ($LASTEXITCODE) { throw 'Docker Desktop chưa chạy. Mở Docker Desktop, đợi "Engine running" rồi chạy lại.' }
}
docker compose up -d
if ($LASTEXITCODE) { throw 'Không bật được app (docker compose up).' }

Step 'Đợi Odoo sẵn sàng'
$ready = $false
for ($i = 0; $i -lt 60 -and -not $ready; $i++) {
    try { Invoke-WebRequest http://127.0.0.1:8069/web/login -UseBasicParsing -TimeoutSec 5 | Out-Null; $ready = $true }
    catch { Start-Sleep 3 }
}
if (-not $ready) { throw 'Odoo không phản hồi ở http://127.0.0.1:8069. Xem: docker compose logs odoo' }

Step 'Đăng nhập devtunnel'
devtunnel user show *> $null
if ($LASTEXITCODE) { devtunnel user login; if ($LASTEXITCODE) { throw 'Chưa đăng nhập devtunnel.' } }

$id = if (Test-Path $idFile) { (Get-Content $idFile -Raw).Trim() } else { 'lifeood-erp' }
devtunnel show $id *> $null
if ($LASTEXITCODE) {
    Step "Tạo tunnel $id (một lần; hết hạn sau 30 ngày không dùng thì tự tạo lại cùng tên)"
    $out = devtunnel create $id --allow-anonymous --expiration 30d @opts 2>&1 | Out-String
    if ($LASTEXITCODE) {
        # tên đã có người dùng: để dịch vụ tự đặt tên, lưu lại để lần sau dùng đúng link đó
        $out = devtunnel create --allow-anonymous --expiration 30d @opts 2>&1 | Out-String
        if ($LASTEXITCODE -or $out -notmatch 'Tunnel ID\s*:\s*(\S+)') { throw "Không tạo được tunnel:`n$out" }
        $id = $Matches[1]
    }
    devtunnel port create $id -p 8069 --protocol http @opts
    if ($LASTEXITCODE) { throw 'Không mở được cổng 8069 trên tunnel.' }
    Set-Content $idFile $id
}

# link có dạng https://<tên>-8069.<vùng>.devtunnels.ms, dựng từ mã tunnel đầy đủ "<tên>.<vùng>"
$info = devtunnel show $id 2>&1 | Out-String
if ($info -notmatch 'Tunnel ID\s*:\s*([a-z0-9-]+)\.([a-z0-9]+)') { throw "Không đọc được mã tunnel $id`n$info" }
$url = "https://$($Matches[1])-8069.$($Matches[2]).devtunnels.ms"

Step "Đặt địa chỉ hệ thống = $url (đường dẫn trong thư đặt lại mật khẩu)"
"env['ir.config_parameter'].sudo().set_param('web.base.url', '$url'); env['ir.config_parameter'].sudo().set_param('web.base.url.freeze', 'True'); env.cr.commit()" |
    docker compose exec -T odoo odoo shell -c /etc/odoo/odoo.conf -d lfood --no-http *> $null

# giữ máy không ngủ khi cửa sổ này còn mở (không đổi cài đặt nguồn của Windows; gập máy vẫn theo cài đặt nắp máy)
Add-Type -Namespace LFood -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[LFood.Power]::SetThreadExecutionState([uint32]2147483649) | Out-Null  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED

Set-Clipboard $url
Write-Host "`n==============================================================" -ForegroundColor Green
Write-Host " Link cho công ty: $url   (đã chép vào clipboard)" -ForegroundColor Green
Write-Host " Lần đầu mở, trang của Microsoft hỏi xác nhận: bấm Continue." -ForegroundColor Green
Write-Host " Nhớ: đổi mật khẩu các tài khoản mẫu (lfood2026) trước khi gửi link." -ForegroundColor Yellow
Write-Host "==============================================================`n" -ForegroundColor Green

while ($true) {
    devtunnel host $id
    Write-Host 'Mất kết nối tunnel, thử lại sau 10 giây (Ctrl+C để tắt)...' -ForegroundColor Yellow
    Start-Sleep 10
}
