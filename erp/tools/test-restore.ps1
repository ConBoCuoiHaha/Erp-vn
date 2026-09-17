<#
Thử khôi phục bản sao lưu mới nhất vào cơ sở dữ liệu tạm, đối chiếu số dòng rồi xóa bản tạm.
Nên chạy mỗi tháng một lần: bản sao lưu chưa từng khôi phục thử thì chưa chắc dùng được.
  .\tools\test-restore.ps1
#>
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$dir = (Get-Content .env | Where-Object { $_ -match '^BACKUP_DIR=' }) -replace '^BACKUP_DIR=', ''
$latest = Get-ChildItem "$dir\daily" -Directory | Where-Object { $_.Name -notlike '*.part' } | Sort-Object Name | Select-Object -Last 1
if (-not $latest) { throw "Chưa có bản sao lưu nào trong $dir\daily" }
Write-Host "Bản sao lưu: $($latest.FullName)"

foreach ($line in Get-Content "$($latest.FullName)\SHA256SUMS") {
  $hash, $name = $line -split '\s+', 2
  if ((Get-FileHash -Algorithm SHA256 (Join-Path $latest.FullName $name.Trim('*'))).Hash.ToLower() -ne $hash) { throw "Mã băm $name không khớp" }
}
$m = Get-Content "$($latest.FullName)\manifest.json" -Raw | ConvertFrom-Json
$tmp = 'lfood_kiemtra'
docker compose cp "$($latest.FullName)\database.dump" "db:/tmp/kiemtra.dump"
docker compose exec -T db psql -U odoo -d postgres -q -c "DROP DATABASE IF EXISTS $tmp WITH (FORCE);" -c "CREATE DATABASE $tmp OWNER odoo;"
docker compose exec -T db pg_restore -U odoo -d $tmp --no-owner /tmp/kiemtra.dump
$r = docker compose exec -T db psql -U odoo -d $tmp -At -c "SELECT count(*) FROM lfood_service_voucher" -c "SELECT count(*) FROM lfood_service_voucher_line" -c "SELECT count(*) FROM lfood_audit_log" -c "SELECT hash FROM lfood_audit_log ORDER BY id DESC LIMIT 1"
docker compose exec -T db psql -U odoo -d postgres -q -c "DROP DATABASE $tmp WITH (FORCE);"
docker compose exec -T db rm -f /tmp/kiemtra.dump

$ok = ($r[0] -eq "$($m.counts.vouchers)") -and ($r[1] -eq "$($m.counts.voucher_lines)") -and ($r[2] -eq "$($m.counts.audit_logs)") -and ($r[3] -eq "$($m.counts.last_audit_hash)")
Write-Host ("Chứng từ {0}/{1} · Dòng chứng từ {2}/{3} · Nhật ký {4}/{5} · Mã băm cuối khớp: {6}" -f $r[0], $m.counts.vouchers, $r[1], $m.counts.voucher_lines, $r[2], $m.counts.audit_logs, ($r[3] -eq $m.counts.last_audit_hash))
if ($ok) { Write-Host 'KHÔI PHỤC THỬ THÀNH CÔNG' -ForegroundColor Green } else { Write-Host 'KHÔI PHỤC THỬ CÓ SAI LỆCH' -ForegroundColor Red; exit 1 }
