<#
Khôi phục dữ liệu ERP LiFeOOD từ một bản sao lưu.

  An toàn (mặc định): khôi phục vào cơ sở dữ liệu MỚI để xem lại, không đụng dữ liệu đang dùng
    .\tools\restore.ps1 -Backup "C:\Users\ADMIN\ERP-Backup\daily\2026-09-14_120000"
    -> mở http://localhost:8069/web/login?db=lfood_restore

  Thay dữ liệu đang dùng (phải gõ xác nhận; tự sao lưu dữ liệu hiện tại trước):
    .\tools\restore.ps1 -Backup "...\daily\2026-09-14_120000" -Replace
#>
param(
  [Parameter(Mandatory = $true)][string]$Backup,
  [string]$Target = 'lfood_restore',
  [switch]$Replace
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path "$Backup\database.dump")) { throw "Không thấy database.dump trong $Backup" }

Write-Host "Kiểm tra mã băm tệp sao lưu..."
foreach ($line in Get-Content "$Backup\SHA256SUMS") {
  $hash, $name = $line -split '\s+', 2
  $actual = (Get-FileHash -Algorithm SHA256 (Join-Path $Backup $name.Trim('*'))).Hash.ToLower()
  if ($actual -ne $hash) { throw "Tệp $name bị hỏng hoặc bị sửa (mã băm không khớp). Dừng khôi phục." }
}
Write-Host "Mã băm khớp." -ForegroundColor Green

if ($Replace) {
  $Target = 'lfood'
  $answer = Read-Host "Sẽ THAY TOÀN BỘ dữ liệu đang dùng bằng bản sao lưu. Gõ KHOI PHUC để tiếp tục"
  if ($answer -ne 'KHOI PHUC') { Write-Host 'Đã hủy.'; exit 1 }
  Write-Host 'Sao lưu dữ liệu hiện tại trước khi thay...'
  $pre = "$(Get-Date -Format yyyyMMdd_HHmmss)"
  docker compose exec -T db pg_dump -U odoo -Fc lfood -f "/tmp/truoc_khoi_phuc_$pre.dump"
  docker compose cp "db:/tmp/truoc_khoi_phuc_$pre.dump" ".\truoc_khoi_phuc_$pre.dump"
  Write-Host "Đã lưu dữ liệu cũ: truoc_khoi_phuc_$pre.dump"
  docker compose stop odoo backup
}

$ts = Get-Date -Format yyyyMMddHHmmss
docker compose cp "$Backup\database.dump" "db:/tmp/restore_$ts.dump"
docker compose exec -T db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS `"$Target`" WITH (FORCE);"
docker compose exec -T db psql -U odoo -d postgres -c "CREATE DATABASE `"$Target`" OWNER odoo;"
docker compose exec -T db pg_restore -U odoo -d $Target --no-owner "/tmp/restore_$ts.dump"
docker compose exec -T db rm -f "/tmp/restore_$ts.dump"

Write-Host 'Khôi phục tệp đính kèm...'
docker compose cp "$Backup\filestore.tar.gz" "odoo:/tmp/filestore_$ts.tar.gz"
# giải nén vào thư mục tạm rồi mới đặt đúng tên, không bao giờ đè lên tệp của dữ liệu đang dùng
docker compose exec -T -u root odoo sh -c "set -e; mkdir -p /tmp/fs_$ts /var/lib/odoo/filestore; tar -xzf /tmp/filestore_$ts.tar.gz -C /tmp/fs_$ts; rm -rf /var/lib/odoo/filestore/$Target; if [ -d /tmp/fs_$ts/lfood ]; then mv /tmp/fs_$ts/lfood /var/lib/odoo/filestore/$Target; fi; chown -R odoo:odoo /var/lib/odoo/filestore; rm -rf /tmp/fs_$ts /tmp/filestore_$ts.tar.gz"

$manifest = Get-Content "$Backup\manifest.json" -Raw | ConvertFrom-Json
$check = docker compose exec -T db psql -U odoo -d $Target -At -c "SELECT count(*) FROM lfood_service_voucher; SELECT count(*) FROM lfood_audit_log;"
Write-Host ("Đối chiếu: chứng từ {0}/{1}, dòng nhật ký {2}/{3}" -f $check[0], $manifest.counts.vouchers, $check[1], $manifest.counts.audit_logs)

if ($Replace) { docker compose start odoo backup }
Write-Host "Xong. Mở http://localhost:8069/web/login?db=$Target" -ForegroundColor Green


