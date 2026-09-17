# Kiểm thử qua HTTP: đăng nhập, đăng nhập sai, xuất Excel, in báo cáo đều vào nhật ký
$base = 'http://localhost:8069'
function Rpc($session, $url, $params) {
  $body = @{ jsonrpc = '2.0'; method = 'call'; params = $params } | ConvertTo-Json -Depth 10
  Invoke-RestMethod -Uri "$base$url" -Method Post -Body $body -ContentType 'application/json' -WebSession $session
}
$bad = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$r1 = Rpc $bad '/web/session/authenticate' @{ db = 'lfood'; login = 'ketoanvien'; password = 'sai-mat-khau' }
"Dang nhap sai tra loi loi: " + [bool]$r1.error

$s = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$r2 = Rpc $s '/web/session/authenticate' @{ db = 'lfood'; login = 'ketoantruong'; password = 'lfood2026' }
"Dang nhap dung uid: " + $r2.result.uid

# xuất Excel danh sách chứng từ
$data = @{ model = 'lfood.service.voucher'; fields = @(@{name='name';label='Số chứng từ';type='char'}, @{name='amount_total';label='Tổng';type='monetary'}); ids = @(); domain = @(); import_compat = $false; groupby = @() } | ConvertTo-Json -Depth 5 -Compress
$csrf = (Invoke-WebRequest "$base/odoo" -WebSession $s -UseBasicParsing).Content | Select-String -Pattern 'csrf_token["'']?\s*:\s*"([^"]+)"' | ForEach-Object { $_.Matches[0].Groups[1].Value }
$sid = $s.Cookies.GetCookies($base)['session_id'].Value
[IO.File]::WriteAllText("$env:TEMP\lfood-export.json", $data)
$x = curl.exe -s -o "$env:TEMP\lfood-export.xlsx" -w "%{http_code} kich thuoc %{size_download}" -b "session_id=$sid" --data-urlencode "data@$env:TEMP\lfood-export.json" --data-urlencode "csrf_token=$csrf" "$base/web/export/xlsx"
"Xuat Excel HTTP: " + $x

# giao diện form chứng từ, bulk, pivot tải được với quyền kế toán trưởng
foreach ($m in @(@('lfood.service.voucher', @(@($false,'list'),@($false,'form'),@($false,'search'))), @('lfood.voucher.bulk', @(,@($false,'form'))), @('lfood.cost.analysis', @(@($false,'pivot'),@($false,'list'))), @('lfood.audit.log', @(@($false,'list'),@($false,'form'))))) {
  $v = Rpc $s '/web/dataset/call_kw' @{ model = $m[0]; method = 'get_views'; args = @(); kwargs = @{ views = $m[1] } }
  "Man hinh " + $m[0] + ": " + $(if ($v.error) { 'LOI ' + $v.error.data.message } else { 'OK (' + (($v.result.views.PSObject.Properties.Name) -join ',') + ')' })
}
foreach ($m in @(@('lfood.asset', 'list', 'form', 'search'), @('lfood.asset.depreciation', 'list', 'form'), @('lfood.asset.schedule', 'pivot'), @('lfood.asset.category', 'list'), @('lfood.service.voucher', 'form'), @('lfood.cost.analysis', 'list'))) {
  $views = @($m[1..($m.Count - 1)] | ForEach-Object { ,@($false, $_) })
  $v = Rpc $s '/web/dataset/call_kw' @{ model = $m[0]; method = 'get_views'; args = @(); kwargs = @{ views = $views } }
  "Man hinh tai san " + $m[0] + ": " + $(if ($v.error) { 'LOI ' + $v.error.data.message } else { 'OK' })
}foreach ($m in @(@('lfood.account', 'list', 'form', 'search'), @('lfood.move', 'list', 'form', 'search'), @('lfood.move.line', 'list', 'pivot', 'search'), @('lfood.payment', 'list', 'form', 'search'), @('lfood.ledger.report', 'form'), @('lfood.closing', 'form'), @('lfood.lock', 'form'), @('lfood.asset.transfer', 'form'), @('lfood.vat.return', 'list', 'form'), @('lfood.sale.invoice', 'list', 'form', 'search'), @('lfood.aging', 'form'), @('lfood.product', 'list', 'form'), @('lfood.stock.picking', 'list', 'form', 'search'), @('lfood.stock.valuation', 'list', 'search'), @('lfood.stock.report', 'form'), @('lfood.stock.lot', 'list'), @('lfood.employee', 'list', 'form'), @('lfood.payroll.run', 'list', 'form'), @('lfood.payroll.slip', 'list', 'form', 'pivot'), @('lfood.payroll.component', 'list'), @('lfood.budget', 'list', 'form', 'search'), @('lfood.budget.line', 'list'), @('lfood.budget.spread', 'form'), @('lfood.budget.report', 'list', 'search'), @('lfood.purchase.request', 'list', 'form', 'search'), @('lfood.purchase.order', 'list', 'form', 'search'), @('lfood.purchase.quote', 'list', 'form', 'search'), @('lfood.purchase.adjust', 'list', 'form'), @('lfood.purchase.tally', 'list', 'form', 'search'), @('lfood.cit.provisional', 'list', 'form'), @('lfood.cit.finalization', 'list', 'form', 'search'), @('lfood.prepaid', 'list', 'form'), @('lfood.accrued', 'list', 'form'), @('lfood.accrual.run', 'form'), @('lfood.provision', 'list', 'form', 'search'), @('lfood.offset', 'form'), @('lfood.hr.contract', 'list', 'form', 'search'), @('lfood.hr.leave', 'list', 'form'), @('lfood.hr.attendance', 'list', 'search'), @('lfood.employee', 'form'), @('lfood.stock.count', 'list', 'form'), @('lfood.hr.termination', 'list', 'form'), @('lfood.fx.revaluation', 'list', 'form'), @('lfood.move', 'form'), @('lfood.sale.order', 'list', 'form'), @('lfood.pricelist', 'list', 'form'), @('lfood.sale.channel', 'list'), @('lfood.promotion', 'list', 'form'), @('lfood.stock.disposal', 'list', 'form'), @('lfood.stock.lot', 'list'), @('lfood.reminder', 'list'), @('lfood.intercompany.transfer', 'list', 'form'), @('lfood.bank.statement', 'list', 'form'), @('lfood.bank.account', 'list'), @('lfood.advance', 'list', 'form'), @('lfood.tax.obligation', 'list', 'form'), @('lfood.loan', 'list', 'form'), @('lfood.cit.finalization', 'form'), @('lfood.privacy.consent', 'list', 'form'), @('lfood.privacy.request', 'list', 'form'), @('lfood.employee', 'form'), @('lfood.recall', 'list', 'form'), @('lfood.trace', 'form'), @('lfood.qc.check', 'list', 'form'), @('lfood.qc.action', 'list', 'form'), @('lfood.holiday', 'list'), @('lfood.document', 'list', 'form'), @('lfood.hr.transfer', 'list', 'form'), @('lfood.hr.discipline', 'list', 'form'), @('lfood.department', 'list'), @('lfood.labor.report', 'list', 'form'), @('lfood.hr.benefit', 'list', 'form'), @('lfood.product.declaration', 'list', 'form'), @('lfood.lab.test', 'list'), @('lfood.worker.check', 'list'), @('lfood.purchase.contract', 'list', 'form'), @('lfood.supplier.evaluation', 'list', 'form'), @('lfood.distributor.contract', 'list', 'form'), @('lfood.trade.program', 'list', 'form'), @('lfood.param.tools', 'form'), @('lfood.payroll.simulation', 'form'), @('lfood.einvoice.check', 'list', 'form'), @('lfood.salary.advance', 'list'), @('lfood.pit.freelance', 'list', 'form'), @('lfood.pit.settlement', 'list', 'form'), @('lfood.payroll.run', 'form'), @('lfood.insurance.change', 'list', 'form'), @('lfood.hr.shift', 'list'), @('lfood.hr.roster', 'list'), @('lfood.hr.accident', 'list', 'form'), @('lfood.hr.accident.report', 'list', 'form'), @('lfood.hr.safety.training', 'list'))) {
  $views = @($m[1..($m.Count - 1)] | ForEach-Object { ,@($false, $_) })
  $v = Rpc $s '/web/dataset/call_kw' @{ model = $m[0]; method = 'get_views'; args = @(); kwargs = @{ views = $views } }
  "Man hinh so ke toan " + $m[0] + ": " + $(if ($v.error) { 'LOI ' + $v.error.data.message } else { 'OK' })
}
$g = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$null = Rpc $g '/web/session/authenticate' @{ db = 'lfood'; login = 'giamdoc'; password = 'lfood2026' }
$r = Rpc $g '/web/dataset/call_kw' @{ model = 'lfood.ledger.report'; method = 'web_save'; args = @(@(), @{ report = 'trial'; date_from = '2026-01-01'; date_to = '2026-12-31' }); kwargs = @{ specification = @{ html = @{} } } }
$r2 = Rpc $g '/web/dataset/call_kw' @{ model = 'lfood.ledger.report'; method = 'web_save'; args = @(@(), @{ report = 'b01'; date_from = '2026-01-01'; date_to = '2026-09-30' }); kwargs = @{ specification = @{ html = @{} } } }
$r5 = Rpc $g '/web/dataset/call_kw' @{ model = 'lfood.ledger.report'; method = 'web_save'; args = @(@(), @{ report = 'dashboard'; date_from = '2026-01-01'; date_to = '2026-12-31' }); kwargs = @{ specification = @{ html = @{} } } }
"Giam doc xem bang dieu hanh: " + $(if ($r5.error) { 'LOI ' + $r5.error.data.message } else { if ($r5.result[0].html -match 'Ket qua kinh doanh|K.t qu.') { 'OK' } else { 'thieu noi dung' } })
"Giam doc xem B01: " + $(if ($r2.error) { 'LOI ' + $r2.error.data.message } else { if ($r2.result[0].html -match 'TỔNG CỘNG NGUỒN VỐN') { 'OK' } else { 'thieu noi dung' } })
"Giam doc xem bang can doi: " + $(if ($r.error) { 'LOI ' + $r.error.data.message } else { if ($r.result[0].html -match 'sổ cân') { 'OK, so can' } else { 'khong thay dong so can' } })
$logout = curl.exe -s -o NUL -w "%{http_code}" -b "session_id=$sid" "$base/web/session/logout"
"Dang xuat: " + $logout

# quản trị: màn hình quản trị, tải bản sao lưu; kế toán trưởng bị từ chối tải
$bk = Rpc $s '/web/dataset/call_kw' @{ model = 'lfood.backup'; method = 'search_read'; args = @(); kwargs = @{ limit = 1; fields = @('id') } }
"Ke toan truong doc sao luu bi chan: " + [bool]$bk.error
$a = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$r3 = Rpc $a '/web/session/authenticate' @{ db = 'lfood'; login = 'admin'; password = 'admin' }
"Admin dang nhap uid: " + $r3.result.uid
foreach ($m in @(@('res.users', 'lfood_admin.view_users_lfood_form'), @('lfood.backup', 'lfood_admin.view_backup_list'), @('lfood.backup.status', 'lfood_admin.view_backup_status_form'), @('res.partner', 'lfood_admin.view_partner_lfood_form'), @('lfood.role.matrix', 'lfood_admin.view_role_matrix_form'))) {
  $v = Rpc $a '/web/dataset/call_kw' @{ model = $m[0]; method = 'get_views'; args = @(); kwargs = @{ views = @(,@($false, $(if ($m[1] -like '*list') { 'list' } else { 'form' }))) } }
  "Man hinh quan tri " + $m[0] + ": " + $(if ($v.error) { 'LOI ' + $v.error.data.message } else { 'OK' })
}
$null = Rpc $a '/web/dataset/call_kw' @{ model = 'lfood.backup'; method = 'action_sync'; args = @(); kwargs = @{} }
$bk = Rpc $a '/web/dataset/call_kw' @{ model = 'lfood.backup'; method = 'search_read'; args = @(); kwargs = @{ limit = 1; fields = @('id', 'name') } }
$bid = $bk.result[0].id
$asid = $a.Cookies.GetCookies($base)['session_id'].Value
"Admin tai sao luu: " + (curl.exe -s -o "$env:TEMP\lfood-backup.zip" -w "%{http_code} kich thuoc %{size_download}" -b "session_id=$asid" "$base/lfood/backup/$bid/download")
$r4 = Rpc $s '/web/session/authenticate' @{ db = 'lfood'; login = 'ketoantruong'; password = 'lfood2026' }
$ksid = $s.Cookies.GetCookies($base)['session_id'].Value
"Ke toan truong tai sao luu: " + (curl.exe -s -o NUL -w "%{http_code}" -b "session_id=$ksid" "$base/lfood/backup/$bid/download")








