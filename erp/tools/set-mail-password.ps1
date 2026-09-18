# Nhập mật khẩu ứng dụng Gmail cho máy chủ thư hệ thống (dùng để gửi thư đặt lại mật khẩu).
# Chạy trong thư mục erp:  powershell -ExecutionPolicy Bypass -File tools\set-mail-password.ps1
# Mật khẩu gõ vào không hiện lên màn hình, không ghi vào tệp nào, chỉ lưu trong cơ sở dữ liệu của hệ thống.
Set-Location (Split-Path $PSScriptRoot -Parent)
$sec = Read-Host 'Mat khau ung dung Gmail (16 ky tu)' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
try {
    $env:LFOOD_SMTP_PASS = ([Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)) -replace '\s', ''
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
if (-not $env:LFOOD_SMTP_PASS) { Write-Host 'Chua nhap mat khau.'; exit 1 }
$py = @'
import os
server = env.ref('lfood_security.mail_server_gmail').sudo()
server.write({'smtp_pass': os.environ['LFOOD_SMTP_PASS']})
env.cr.commit()
try:
    server.test_smtp_connection()
    print('KET QUA: da luu mat khau, ket noi Gmail thanh cong')
except Exception as e:
    print('KET QUA: da luu mat khau nhung ket noi loi -', str(e).splitlines()[0])
'@
try {
    $py | docker compose run --rm -T -e LFOOD_SMTP_PASS odoo odoo shell -c /etc/odoo/odoo.conf -d lfood --no-http 2>&1 |
        Select-String -Pattern '^KET QUA'
} finally {
    Remove-Item Env:LFOOD_SMTP_PASS -ErrorAction SilentlyContinue
}
