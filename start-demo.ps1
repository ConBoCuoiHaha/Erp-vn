# Mở app ERP ra Internet cho sếp test.
#
#   Lần đầu (chỉ 1 lần): devtunnel user login
#   Sau đó:              .\start-demo.ps1
#
# Cửa sổ này phải giữ mở trong suốt lúc sếp test. Ctrl+C để tắt tunnel.
# Máy không được sleep — tunnel chạy từ chính máy này.

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$py   = 'C:\Users\ADMIN\AppData\Local\Programs\Python\Python312\python.exe'
$port = 5199

$pass = (Get-Content (Join-Path $root '.demo-password.txt') -Raw).Trim()
$env:ERP_USER = 'lfood'
$env:ERP_PASS = $pass

# --- 1. server tĩnh có mật khẩu -------------------------------------------
Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Start-Process -FilePath $py -ArgumentList (Join-Path $root 'serve.py'), $port `
  -WorkingDirectory $root -WindowStyle Hidden
Start-Sleep -Seconds 2

$hdr = @{ Authorization = 'Basic ' + [Convert]::ToBase64String(
          [Text.Encoding]::UTF8.GetBytes("lfood:$pass")) }
try {
  $null = Invoke-WebRequest "http://127.0.0.1:$port/index.html" -Headers $hdr -UseBasicParsing
  Write-Host "[OK] Server chay tren cong $port" -ForegroundColor Green
} catch {
  Write-Host "[LOI] Server khong len duoc. Kiem tra python: $py" -ForegroundColor Red
  exit 1
}

# --- 2. kiem tra dang nhap devtunnel --------------------------------------
$who = (devtunnel user show 2>&1) -join ' '
if ($who -match 'expired|not logged|Login token') {
  Write-Host ""
  Write-Host "Chua dang nhap devtunnel. Chay lenh nay truoc roi chay lai script:" -ForegroundColor Yellow
  Write-Host "    devtunnel user login" -ForegroundColor Cyan
  exit 1
}

# --- 3. mo tunnel ----------------------------------------------------------
Write-Host ""
Write-Host "=======================================================" -ForegroundColor Green
Write-Host " Gui cho sep: link ben duoi + tai khoan dang nhap"
Write-Host "   Tai khoan : lfood"
Write-Host "   Mat khau  : $pass"
Write-Host "=======================================================" -ForegroundColor Green
Write-Host ""

devtunnel host -p $port --allow-anonymous
