# Kiểm thử luồng chính. Chạy:
#   docker compose run --rm -T odoo odoo shell -c /etc/odoo/odoo.conf -d lfood --no-http < tests/smoke_test.py
from odoo.exceptions import UserError, AccessError
from odoo.addons.lfood_voucher.models.tools import vnd

results = []
def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))

ref = env.ref
V = env['lfood.service.voucher']
Log = env['lfood.audit.log']
factory = ref('lfood_base.company_factory')
log_start = env['lfood.audit.log'].sudo().search([], limit=1).id  # dòng nhật ký cuối trước khi kiểm thử
users = {u.login: u for u in env['res.users'].search([('login', 'in', ['giamdoc', 'ketoantruong', 'ketoanvien', 'nhanvien'])])}
check('Có đủ 4 người dùng mẫu', len(users) == 4, list(users))

v433 = V.search([('memo', 'ilike', 'hóa đơn số 222')], limit=1)
check('Chứng từ MDV00433 có số và đã cất', v433 and v433.state == 'posted', '%s %s' % (v433.name, v433.state))
check('Tổng tiền dịch vụ 97.505.000', v433.amount_untaxed == 97505000, v433.amount_untaxed)
check('Thuế 8% = 7.800.400', v433.amount_tax == 7800400, v433.amount_tax)
check('Tổng thanh toán 105.305.400', v433.amount_total == 105305400, v433.amount_total)

Analysis = env['lfood.cost.analysis'].with_company(factory)
def report_total(voucher):
    return sum(env['lfood.cost.analysis'].sudo().search([('voucher_id', '=', voucher.id)]).mapped('amount'))
rep_before = report_total(v433)
check('Báo cáo đọc 97.505.000 cho MDV00433', rep_before == 97505000, rep_before)

# ---- Kế toán viên không được Sửa chứng từ đã cất
kv = v433.with_user(users['ketoanvien']).with_company(factory)
try:
    kv.action_edit(); check('Kế toán viên bị chặn Sửa', False)
except UserError:
    check('Kế toán viên bị chặn Sửa', True)
try:
    kv.line_ids[0].write({'amount': 1}); check('Không sửa thẳng dòng đã cất', False)
except UserError:
    check('Không sửa thẳng dòng đã cất', True)

# ---- Giám đốc không sửa được số liệu
gd = v433.with_user(users['giamdoc']).with_company(factory)
try:
    gd.write({'memo': 'giám đốc sửa'}); check('Giám đốc bị chặn sửa', False)
except (AccessError, UserError):
    check('Giám đốc bị chặn sửa', True)
env.invalidate_all()

# ---- Nhân viên không xem chứng từ
try:
    V.with_user(users['nhanvien']).search([]).read(['name']); check('Nhân viên không xem chứng từ', False)
except AccessError:
    check('Nhân viên không xem chứng từ', True)

# ---- Kế toán trưởng Sửa: sửa tổng 97.505.000 -> 120.000.001, phân bổ theo tỷ trọng
ktt = v433.with_user(users['ketoantruong']).with_company(factory)
ktt.action_edit()
check('Sau Sửa: trạng thái Đang sửa, có phiên bản 2', ktt.state == 'editing' and ktt.current_version_id.number == 2)
ktt._apply_total(120000001)
amounts = ktt.line_ids.mapped('amount')
check('Phân bổ tổng khớp tuyệt đối', sum(amounts) == 120000001, amounts)
check('Giữ tỷ trọng 71.025.000 : 26.480.000', abs(amounts[0] / sum(amounts) - 71025000 / 97505000) < 1e-6, amounts)
ktt._save_edit('Hóa đơn điều chỉnh tăng số suất ăn tháng 7')
check('Lưu sửa đổi: về Đã cất, phiên bản 2 hiện hành', ktt.state == 'posted' and ktt.current_version_id.number == 2)
check('Phiên bản báo cáo vẫn là 1', ktt.report_version_id.number == 1)
env.invalidate_all()
check('BÁO CÁO KHÔNG ĐỔI sau khi Sửa', report_total(v433) == rep_before, report_total(v433))
check('Có ghi chênh lệch phiên bản', len(ktt.current_version_id.diff_ids) >= 2, len(ktt.current_version_id.diff_ids))

# ---- Điều chỉnh hàng loạt: tăng 10% mọi chứng từ đã cất của Nhà máy
posted = V.with_company(factory).search([('state', '=', 'posted'), ('company_id', '=', factory.id)])
drafts = V.with_company(factory).search([('state', '=', 'draft'), ('company_id', '=', factory.id)])
before = {v.id: v.amount_untaxed for v in posted | drafts}
rep_all_before = {v.id: report_total(v) for v in posted}
Bulk = env['lfood.voucher.bulk'].with_user(users['ketoantruong']).with_company(factory)
w = Bulk.create({'voucher_ids': [(6, 0, (posted | drafts).ids)], 'operation': 'scale_percent', 'percent': 10,
                 'reason': 'Kiểm thử tăng 10%'})
w.action_preview()
check('Xem trước có dòng thay đổi', len(w.preview_ids) > 0, len(w.preview_ids))
res = w.action_apply()
batch = env['lfood.voucher.bulk.batch'].browse(res['res_id'])
env.invalidate_all()
ok = all(abs(v.amount_untaxed - round(before[v.id] * 1.1)) <= len(v.line_ids) for v in posted | drafts)
check('Hàng loạt: mọi chứng từ tăng ~10%% (%s chứng từ)' % len(posted | drafts), ok,
      [(v.name, before[v.id], v.amount_untaxed) for v in (posted | drafts)])
check('Hàng loạt: báo cáo không đổi', all(report_total(v) == rep_all_before[v.id] for v in posted))
check('Lô ghi đủ số chứng từ', batch.voucher_count == len(posted | drafts), batch.voucher_count)

# ---- Kế toán viên không được điều chỉnh hàng loạt
try:
    env['lfood.voucher.bulk'].with_user(users['ketoanvien']).create({'voucher_ids': [(6, 0, posted.ids)], 'reason': 'x'}).action_apply()
    check('Kế toán viên bị chặn hàng loạt', False)
except (UserError, AccessError):
    check('Kế toán viên bị chặn hàng loạt', True)

# ---- Hoàn tác lô
batch.with_user(users['ketoantruong']).action_undo()
env.invalidate_all()
check('Hoàn tác: chứng từ đã cất về số trước lô', all(v.amount_untaxed == before[v.id] for v in posted),
      [(v.name, before[v.id], v.amount_untaxed) for v in posted])

# ---- Khôi phục số gốc MDV00433 và đưa vào báo cáo
ktt._restore_original('Kiểm thử khôi phục')
check('Khôi phục gốc: về 97.505.000', ktt.amount_untaxed == 97505000, ktt.amount_untaxed)

# ---- Nhật ký
logs = Log.sudo().search([])
actions = set(logs.mapped('action'))
check('Nhật ký có tạo, sửa, đổi trạng thái, hàng loạt', {'create', 'write', 'state', 'bulk'} <= actions, actions)
edit_log = Log.sudo().search([('action', '=', 'state'), ('summary', 'ilike', 'Lưu sửa đổi chứng từ %s' % v433.name)], limit=1)
check('Nhật ký ghi đích danh người Sửa', edit_log.user_id == users['ketoantruong'], edit_log.user_id.login)
try:
    logs[:1].write({'summary': 'xóa dấu vết'}); check('Không sửa được nhật ký qua app', False)
except UserError:
    check('Không sửa được nhật ký qua app', True)
try:
    with env.cr.savepoint():
        env.cr.execute("UPDATE lfood_audit_log SET summary='x' WHERE id=%s", (logs[0].id,))
    check('Không sửa được nhật ký bằng SQL', False)
except Exception:
    check('Không sửa được nhật ký bằng SQL', True)
brk, _n = Log.sudo()._chain_breaks()
check('Chuỗi mã băm nhật ký: không có sai lệch mới trong lúc kiểm thử', not [b for b in brk if b > log_start], brk)
env.cr.execute("SELECT hash FROM lfood_audit_head")
check('Đầu chuỗi mã băm khớp dòng nhật ký cuối', env.cr.fetchone()[0] == Log.sudo().search([], limit=1).hash)
verify = Log.sudo().action_verify_chain()
check('Kiểm tra toàn vẹn chỉ báo đúng các dòng sai lệch cũ', verify['params']['type'] == ('danger' if brk else 'success')
      and all(str(b) in verify['params']['message'] for b in brk[:20]), verify['params']['message'])

# ---- Quản trị: người dùng, vai trò, CRUD
admin = ref('base.user_admin')
AU = env['res.users'].with_user(admin)
check('Admin có vai trò Quản trị hệ thống', admin.lfood_role == 'sysadmin', admin.lfood_role)
new = AU.create({'name': 'Thử Quản Trị', 'login': 'thu_qt', 'company_id': factory.id,
                 'company_ids': [(6, 0, factory.ids)], 'lfood_role': 'accountant'})
check('Admin tạo người dùng vai trò Kế toán viên', new.has_group('lfood_base.group_accountant')
      and not new.has_group('lfood_base.group_chief_accountant'), new.lfood_role)
new.write({'lfood_role': 'rnd'})
check('Đổi sang R&D thì mất quyền kế toán', new.has_group('lfood_base.group_rnd')
      and not new.has_group('lfood_base.group_employee'), new.lfood_role)
try:
    V.with_user(new).with_company(factory).search_count([]); check('R&D không xem được chứng từ', False)
except AccessError:
    check('R&D không xem được chứng từ', True)
try:
    Log.with_user(new).search_count([]); check('R&D không xem được nhật ký', False)
except AccessError:
    check('R&D không xem được nhật ký', True)
new.action_archive()
check('Admin ngừng hoạt động người dùng', not new.active)
new.action_unarchive()
new.unlink()
check('Admin xóa người dùng chưa có thao tác', not new.exists())
try:
    AU.browse(users['ketoanvien'].id).unlink(); check('Không xóa người dùng đã có nhật ký', False)
except UserError:
    check('Không xóa người dùng đã có nhật ký', True)
try:
    env['lfood.backup'].with_user(users['ketoantruong']).search_count([]); check('Kế toán trưởng không xem sao lưu', False)
except AccessError:
    check('Kế toán trưởng không xem sao lưu', True)

p = env['res.partner'].with_user(users['ketoanvien']).create({'name': 'NCC thử', 'vat': '0100000000', 'is_company': True})
p.write({'phone': '0900000000'})
p.unlink()
check('Kế toán viên thêm, sửa, xóa nhà cung cấp', not p.exists())
c = env['res.company'].with_user(admin).create({'name': 'Công ty thử', 'lfood_code': 'TH'})
check('Admin tạo pháp nhân', c.exists())
env['res.company'].with_user(users['ketoantruong']).browse(factory.id).write({'lfood_edit_after_post_days': 120})
check('Kế toán trưởng sửa quy chế pháp nhân', factory.lfood_edit_after_post_days == 120)
try:
    env['res.company'].with_user(users['ketoantruong']).create({'name': 'X'}); check('Kế toán trưởng không tạo pháp nhân', False)
except AccessError:
    check('Kế toán trưởng không tạo pháp nhân', True)

vd = V.with_user(admin).with_company(factory).search([('state', '=', 'posted')], limit=1)
vd.action_cancel()
try:
    V.with_user(users['ketoantruong']).with_company(factory).browse(vd.id).unlink(); check('Kế toán trưởng không xóa chứng từ đã hủy', False)
except UserError:
    check('Kế toán trưởng không xóa chứng từ đã hủy', True)
try:
    vd.unlink(); check('Không xóa chứng từ đã hủy nếu đã ghi sổ', False)
except UserError:
    check('Không xóa chứng từ đã hủy nếu đã ghi sổ', True)
param = env['lfood.legal.param'].search([('value_ids.state', '=', 'approved')], limit=1)
try:
    param.with_user(admin).unlink(); check('Không xóa tham số đã có mức duyệt', False)
except UserError:
    check('Không xóa tham số đã có mức duyệt', True)
try:
    Log.with_user(admin).search([], limit=1).write({'summary': 'x'}); check('Admin cũng không sửa được nhật ký', False)
except (UserError, AccessError):
    check('Admin cũng không sửa được nhật ký', True)

B = env['lfood.backup'].with_user(admin)
B.action_sync()
bk = B.search([], limit=1)
check('Đồng bộ danh sách bản sao lưu', bk, B.search_count([]))
bk.action_verify()
check('Kiểm tra tệp sao lưu nguyên vẹn', bk.verify_state == 'ok', bk.verify_note)
status = env['lfood.backup.status'].with_user(admin).create({})
check('Màn hình tình trạng sao lưu', 'Nơi lưu' in status.html, status.html[:200])
matrix = env['lfood.role.matrix'].with_user(users['nhanvien']).create({})
check('Ma trận phân quyền có cột R&D', 'R&amp;D' in matrix.html)

# ---- Tài sản cố định và khấu hao
from datetime import date
Asset = env['lfood.asset']
Depr = env['lfood.asset.depreciation']
kv_env = lambda M: env[M].with_user(users['ketoanvien']).with_company(factory)
kt_env = lambda M: env[M].with_user(users['ketoantruong']).with_company(factory)
machine = Asset.search([('code', '=', 'TS00001')])
truck = Asset.search([('code', '=', 'TS00002')])
check('Mẫu: 2 tài sản đang khấu hao', machine.state == 'running' and truck.state == 'running', (machine.state, truck.state))
check('Lịch khấu hao tổng đúng nguyên giá', sum(machine.schedule_ids.mapped('amount')) == 1_000_000_000
      and sum(truck.schedule_ids.mapped('amount')) == 540_000_000)
check('Tháng đầu tính theo ngày: xe từ 16/8 = 3.870.968', truck.schedule_ids[0].amount == 3_870_968, truck.schedule_ids[0].amount)
kh8 = Depr.search([('date', '=', '2026-08-31'), ('state', '=', 'posted')])
check('Chứng từ khấu hao 8/2026 = 20.537.635', kh8.amount_total == 20_537_635, kh8.amount_total)

cat_machine = ref('lfood_asset.cat_machine')
small = kv_env('lfood.asset').create({'name': 'Máy in', 'category_id': cat_machine.id, 'original_value': 20_000_000,
                                      'life_months': 36, 'date_start': date(2026, 9, 1)})
try:
    small.action_confirm(); check('Chặn ghi tăng dưới 30 triệu', False)
except UserError:
    check('Chặn ghi tăng dưới 30 triệu', True)
short = kv_env('lfood.asset').create({'name': 'Máy trộn', 'category_id': cat_machine.id, 'original_value': 90_000_000,
                                      'life_months': 12, 'date_start': date(2026, 9, 1)})
try:
    short.action_confirm(); check('Chặn thời gian ngoài khung', False)
except UserError:
    check('Chặn thời gian ngoài khung', True)
try:
    env['lfood.asset'].with_user(users['nhanvien']).search_count([]); check('Nhân viên không xem tài sản', False)
except AccessError:
    check('Nhân viên không xem tài sản', True)
try:
    env['lfood.asset'].with_user(users['giamdoc']).browse(machine.id).write({'location': 'x'}); check('Giám đốc không sửa tài sản', False)
except AccessError:
    check('Giám đốc không sửa tài sản', True)
try:
    kv_env('lfood.asset').browse(machine.id).write({'original_value': 1}); check('Không sửa nguyên giá khi đang khấu hao', False)
except UserError:
    check('Không sửa nguyên giá khi đang khấu hao', True)
try:
    kv_env('lfood.asset').browse(machine.id).write({'state': 'draft'}); check('Không đổi trạng thái trực tiếp', False)
except UserError:
    check('Không đổi trạng thái trực tiếp', True)

try:
    nov = kv_env('lfood.asset.depreciation').create({'date': date(2026, 11, 10)})
    nov.action_compute(); check('Không nhảy kỳ khấu hao', False)
except UserError:
    check('Không nhảy kỳ khấu hao', True)
sep = kv_env('lfood.asset.depreciation').create({'date': date(2026, 9, 5)})
check('Kỳ khấu hao chuẩn về cuối tháng', sep.date == date(2026, 9, 30), sep.date)
sep.action_compute()
sep.action_post()
check('Khấu hao 9/2026 = 16.666.667 + 7.500.000', sep.amount_total == 24_166_667 and len(sep.line_ids) == 2, sep.amount_total)
rep = sum(env['lfood.cost.analysis'].sudo().search([('depreciation_id', '=', sep.id)]).mapped('amount'))
check('Khấu hao lên báo cáo chi phí', rep == 24_166_667, rep)
check('Hao mòn lũy kế máy sau 2 kỳ', machine.accumulated_value == 33_333_334, machine.accumulated_value)
try:
    kv_env('lfood.asset.depreciation').browse(sep.id).action_cancel(); check('Kế toán viên không hủy khấu hao', False)
except UserError:
    check('Kế toán viên không hủy khấu hao', True)
try:
    kt_env('lfood.asset.depreciation').browse(kh8.id).action_cancel(); check('Không hủy kỳ cũ khi kỳ sau đã ghi', False)
except UserError:
    check('Không hủy kỳ cũ khi kỳ sau đã ghi', True)
log = Log.sudo().search([('model', '=', 'lfood.asset.depreciation'), ('res_id', '=', sep.id), ('action', '=', 'state')], limit=1)
check('Nhật ký ghi đích danh người ghi sổ khấu hao', log.user_id == users['ketoanvien'] and 'Nợ 6274' in log.summary, log.summary)

try:
    kv_env('lfood.asset').browse(machine.id)._dispose(date(2026, 10, 16), 'Hỏng', 0); check('Kế toán viên không thanh lý', False)
except UserError:
    check('Kế toán viên không thanh lý', True)
machine.with_context(lfood_asset_system=True).write({'dispose_counterpart': '111'})
kt_env('lfood.asset').browse(machine.id)._dispose(date(2026, 10, 16), 'Hỏng không sửa được', 50_000_000)
oct_line = machine.schedule_ids.filtered(lambda s: s.date == date(2026, 10, 31))
check('Thanh lý 16/10: tháng 10 tính 15 ngày = 8.064.516', machine.state == 'disposed' and oct_line.amount == 8_064_516
      and len(machine.schedule_ids) == 3, (machine.state, oct_line.amount, len(machine.schedule_ids)))

voucher_action = V.with_user(users['ketoanvien']).with_company(factory).browse(v433.id).action_create_asset()
check('Ghi tăng từ chứng từ mua lấy số báo cáo', voucher_action['context']['default_original_value'] == 97_505_000,
      voucher_action['context']['default_original_value'])

# ---- Sổ kế toán
Acc = env['lfood.account']
Move = env['lfood.move']
ML = env['lfood.move.line']
def net(code_prefix, upto=None, **dom):
    env.flush_all()
    domain = [('state', '=', 'posted'), ('account_code', '=like', code_prefix + '%'), ('company_id', '=', factory.id)]
    if upto:
        domain.append(('date', '<=', upto))
    domain += [(k, '=', v) for k, v in dom.items()]
    return round(sum(ML.sudo().search(domain).mapped('balance')))
check('Hệ thống tài khoản TT99: 71 tài khoản cấp 1', Acc.search_count([('level', '=', 1)]) == 71, Acc.search_count([('level', '=', 1)]))
check('331 có tài khoản con thì không hạch toán thẳng', not Acc.search([('code', '=', '331')]).allow_posting)
env.flush_all()
check('Toàn bộ sổ cân Nợ = Có', round(sum(ML.sudo().search([('state', '=', 'posted')]).mapped('balance'))) == 0)
m433 = Move._active_for(v433)
by_acc = {}
for l in m433.line_ids:
    by_acc[l.account_code] = by_acc.get(l.account_code, 0) + l.debit - l.credit
check('MDV00433 định khoản Nợ 6277 97.505.000, Nợ 1331 7.800.400 / Có 3311 105.305.400',
      by_acc == {'6277': 97505000, '1331': 7800400, '3311': -105305400}, by_acc)
check('Công nợ 3311 ghi theo nhà cung cấp', m433.line_ids.filtered(lambda l: l.account_code == '3311').partner_id == v433.partner_id)
check('Khấu hao 9/2026 đã ghi sổ Nợ 6274, 6414 / Có 2141', Move._active_for(sep).amount == 24_166_667, Move._active_for(sep).amount)
disp = Move.sudo().search([('source_model', '=', 'lfood.asset'), ('source_id', '=', machine.id), ('source_key', '=', 'dispose')])
check('Thanh lý ghi Nợ 2141, Nợ 811 / Có 2112; thu Nợ 111 / Có 711',
      disp and {l.account_code for l in disp.line_ids} == {'2141', '811', '2112', '111', '711'}, [(l.account_code, l.debit, l.credit) for l in disp.line_ids])

# sửa chứng từ rồi đưa vào báo cáo: đảo bút toán cũ, lập bút toán mới
vp = V.with_company(factory).search([('state', '=', 'posted'), ('company_id', '=', factory.id), ('id', '!=', v433.id),
                                     ('id', '!=', vd.id)], limit=1)
kt_v = vp.with_user(users['ketoantruong']).with_company(factory)
kt_v.action_edit()
kt_v._apply_total(round(vp.amount_untaxed) + 1_000_000)
kt_v._save_edit('Kiểm thử đưa sửa đổi vào sổ')
kt_v.action_apply_to_report()
moves_vp = Move.sudo().search([('source_model', '=', vp._name), ('source_id', '=', vp.id)])
check('Đưa sửa đổi vào báo cáo: 3 bút toán gốc, đảo, mới', len(moves_vp) == 3 and len(moves_vp.filtered('reversal_of_id')) == 1, len(moves_vp))
check('Công nợ nhà cung cấp theo số mới', -net('331', partner_id=vp.partner_id.id) >= round(kt_v.amount_total))
check('Chứng từ đã hủy có bút toán đảo, số dư bằng 0',
      round(sum(ML.sudo().search([('move_id.source_model', '=', vd._name), ('move_id.source_id', '=', vd.id)]).mapped('balance'))) == 0
      and len(Move.sudo().search([('source_model', '=', vd._name), ('source_id', '=', vd.id)])) == 2)

# ghi tăng 2 tài sản từ 1 dòng chứng từ mua: tách thẻ, chuyển 6277 sang 2112, thuế 1331 sang 1332 khớp tới đồng
ctx = voucher_action['context']
pair = kv_env('lfood.asset').with_context(**{k: v for k, v in ctx.items() if k.startswith('default_')}).create(
    {'name': 'Tủ đông', 'category_id': cat_machine.id, 'life_months': 60, 'quantity': 3})
pair.action_confirm()
split = Asset.search([('voucher_id', '=', v433.id), ('state', '=', 'running')])
check('Số lượng 3 tách thành 3 thẻ tài sản, tổng nguyên giá khớp', len(split) == 3 and sum(split.mapped('original_value')) == 97_505_000,
      [(a.name, a.original_value) for a in split])
env.flush_all()
inc_lines = ML.sudo().search([('move_id.source_model', '=', 'lfood.asset'), ('move_id.source_id', 'in', split.ids)])
sum_acc = lambda c: round(sum(inc_lines.filtered(lambda l: l.account_code == c).mapped('balance')))
check('Ghi tăng từ chứng từ: Nợ 2112 / Có 6277; Nợ 1332 / Có 1331 đúng 7.800.400',
      (sum_acc('2112'), sum_acc('6277'), sum_acc('1332'), sum_acc('1331')) == (97_505_000, -97_505_000, 7_800_400, -7_800_400),
      (sum_acc('2112'), sum_acc('6277'), sum_acc('1332'), sum_acc('1331')))
try:
    kv_env('lfood.asset').browse(truck.id)._transfer('admin', False, 'x'); check('Kế toán viên không điều chuyển tài sản', False)
except UserError:
    check('Kế toán viên không điều chuyển tài sản', True)
kt_env('lfood.asset').browse(truck.id)._transfer('admin', False, 'Chuyển xe về văn phòng')
check('Điều chuyển xe sang quản lý: TK chi phí 6424', truck.account_expense == '6424', truck.account_expense)

# trả tiền nhà cung cấp
Pay = env['lfood.payment'].with_user(users['ketoanvien']).with_company(factory)
supplier = v433.partner_id
debt_before = net('331', partner_id=supplier.id)
p1 = Pay.create({'kind': 'out', 'method': 'bank', 'purpose': 'supplier', 'partner_id': supplier.id, 'amount': 50_000_000,
                 'memo': 'Trả tiền cơm tháng 7', 'date': date(2026, 9, 10), 'voucher_id': v433.id})
p1.action_post()
check('Ủy nhiệm chi: Nợ 3311 / Có 112, công nợ giảm 50 triệu', net('331', partner_id=supplier.id) - debt_before == 50_000_000
      and p1.name.startswith('UNC'), (p1.name, net('331', partner_id=supplier.id) - debt_before))
cash_before = net('111')
p2 = Pay.create({'kind': 'out', 'method': 'cash', 'purpose': 'supplier', 'partner_id': supplier.id, 'amount': 6_000_000,
                 'memo': 'Trả tiền mặt', 'date': date(2026, 9, 11)})
check('Cảnh báo chi tiền mặt từ 5 triệu', p2.cash_warning)
p2.action_post()
log = Log.sudo().search([('model', '=', 'lfood.payment'), ('res_id', '=', p2.id)], limit=1)
check('Nhật ký ghi rõ chi tiền mặt vượt ngưỡng', 'TIỀN MẶT' in (log.summary or ''), log.summary)
try:
    p2.action_cancel(); check('Kế toán viên không hủy phiếu', False)
except UserError:
    check('Kế toán viên không hủy phiếu', True)
env['lfood.payment'].with_user(users['ketoantruong']).browse(p2.id).action_cancel()
check('Hủy phiếu: tự đảo bút toán', p2.state == 'cancel' and net('111') == cash_before, (net('111'), cash_before))
try:
    Pay.browse(p1.id).write({'amount': 1}); check('Không sửa phiếu đã ghi sổ', False)
except UserError:
    check('Không sửa phiếu đã ghi sổ', True)

# phiếu kế toán: doanh thu, giá vốn để lập B02
KV_Move = Move.with_user(users['ketoanvien']).with_company(factory)
acc = lambda c: Acc.search([('code', '=', c)]).id
bad = KV_Move.create({'journal': 'general', 'date': date(2026, 9, 12), 'memo': 'lệch',
                      'line_ids': [(0, 0, {'account_id': acc('156'), 'debit': 10}), (0, 0, {'account_id': acc('111'), 'credit': 9})]})
try:
    bad.action_post(); check('Chặn bút toán không cân', False)
except UserError:
    check('Chặn bút toán không cân', True)
no_partner = KV_Move.create({'journal': 'general', 'date': date(2026, 9, 12), 'memo': 'thiếu đối tượng',
                             'line_ids': [(0, 0, {'account_id': acc('1311'), 'debit': 10}), (0, 0, {'account_id': acc('511'), 'credit': 10})]})
try:
    no_partner.action_post(); check('Bắt ghi đối tượng cho 1311', False)
except UserError:
    check('Bắt ghi đối tượng cho 1311', True)
customer = env['res.partner'].create({'name': 'Khách hàng kiểm thử', 'is_company': True})
sale = KV_Move.create({'journal': 'general', 'date': date(2026, 9, 12), 'memo': 'Doanh thu bán hàng tháng 9',
                       'line_ids': [(0, 0, {'account_id': acc('1311'), 'partner_id': customer.id, 'debit': 216_000_000}),
                                    (0, 0, {'account_id': acc('511'), 'credit': 200_000_000}),
                                    (0, 0, {'account_id': acc('33311'), 'credit': 16_000_000})]})
sale.action_post()
cogs = KV_Move.create({'journal': 'general', 'date': date(2026, 9, 12), 'memo': 'Giá vốn tháng 9',
                       'line_ids': [(0, 0, {'account_id': acc('632'), 'debit': 120_000_000}), (0, 0, {'account_id': acc('156'), 'credit': 120_000_000})]})
cogs.action_post()
try:
    sale.write({'memo': 'sửa'}); check('Không sửa bút toán đã ghi sổ', False)
except UserError:
    check('Không sửa bút toán đã ghi sổ', True)
try:
    sale.unlink(); check('Không xóa bút toán đã ghi sổ', False)
except UserError:
    check('Không xóa bút toán đã ghi sổ', True)
try:
    Move.with_user(users['giamdoc']).create({'journal': 'general', 'memo': 'x'}); check('Giám đốc không lập bút toán', False)
except AccessError:
    check('Giám đốc không lập bút toán', True)

Report = env['lfood.ledger.report'].with_user(users['ketoantruong']).with_company(factory)
rep = Report.create({'report': 'trial', 'company_id': factory.id, 'date_from': date(2026, 1, 1), 'date_to': date(2026, 12, 31)})
check('Bảng cân đối số phát sinh cân', 'sổ cân' in rep.html, rep.html[-300:])
b02 = Report.create({'report': 'b02', 'company_id': factory.id, 'date_from': date(2026, 1, 1), 'date_to': date(2026, 12, 31)})
vals = b02._b02_values(date(2026, 1, 1), date(2026, 12, 31))
exp_641, exp_642 = net('641'), net('642')
check('B02: 01 = 200 triệu, 11 = 120 triệu, 20 = 80 triệu', (vals['01'], vals['11'], vals['20']) == (200_000_000, 120_000_000, 80_000_000), vals)
check('B02: 30 = 20 - 25 - 26, 50 = 30 + 40', vals['30'] == vals['20'] - exp_641 - exp_642 and vals['50'] == vals['30'] + vals['40'],
      (vals['30'], exp_641, exp_642))
ledger = Report.create({'report': 'ledger', 'company_id': factory.id, 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30),
                        'account_id': acc('3311')})
check('Sổ cái 3311 có TK đối ứng 112', '112' in ledger.html)
partner_rep = Report.create({'report': 'partner', 'company_id': factory.id, 'date_from': date(2026, 1, 1), 'date_to': date(2026, 12, 31)})
check('Sổ chi tiết công nợ có nhà cung cấp', supplier.name in partner_rep.html)

# kết chuyển cuối kỳ
closing = env['lfood.closing'].with_user(users['ketoantruong']).with_company(factory).create({'company_id': factory.id, 'date_to': date(2026, 9, 30)})
closing.action_apply()
sep30 = date(2026, 9, 30)
check('Kết chuyển đến 30/9: đầu 5, 6 (trừ 154), 7, 8 và 911 về 0',
      all(net(p, sep30) == 0 for p in ('511', '632', '641', '642', '711', '811', '911', '627')),
      {p: net(p, sep30) for p in ('511', '632', '641', '642', '811', '911', '627')})
check('Chi phí sản xuất chung 627 chuyển sang 154', net('154') > 0, net('154'))
vals_sep = b02._b02_values(date(2026, 1, 1), sep30)
check('Lợi nhuận chưa phân phối 4212 = B02 đến 30/9', -net('4212', sep30) == vals_sep['60'], (-net('4212', sep30), vals_sep['60']))
b01_rep = Report.create({'report': 'b01', 'company_id': factory.id, 'date_from': date(2026, 1, 1), 'date_to': sep30})
end, pl_left = b01_rep._b01_values(date(2026, 10, 1))
check('B01 đến 30/9 sau kết chuyển: tổng tài sản = tổng nguồn vốn', end['280'] == end['440'] and pl_left == 0, (end['280'], end['440'], pl_left))
check('B01: 222 nguyên giá = số dư 211, 223 hao mòn ghi âm', end['222'] == net('211', sep30) and end['223'] == net('214', sep30),
      (end['222'], net('211', sep30), end['223'], net('214', sep30)))
check('B01: 311 phải trả người bán, 131 phải thu khách hàng', end['311'] > 0 and end['131'] == 216_000_000, (end['311'], end['131']))
check('B01: 420 lợi nhuận chưa phân phối = B02 mã 60', end['420'] == vals_sep['60'], (end['420'], vals_sep['60']))
check('B01 hiển thị cân', 'bằng tổng cộng nguồn vốn' in b01_rep.html)
check('B01 cảnh báo 112, 156 dư Có (chi quá số dư, xuất kho âm)', '112 (dư Có' in b01_rep.html and '156 (dư Có' in b01_rep.html)
b01_dec = Report.create({'report': 'b01', 'company_id': factory.id, 'date_from': date(2026, 1, 1), 'date_to': date(2026, 12, 31)})
check('B01 cuối năm chưa kết chuyển tháng 10: cảnh báo', 'hãy Kết chuyển' in b01_dec.html)
b03_rep = Report.create({'report': 'b03', 'company_id': factory.id, 'date_from': date(2026, 1, 1), 'date_to': date(2026, 12, 31)})
cf, cash_end = b03_rep._b03_values(date(2026, 1, 1), date(2026, 12, 31))
check('B03: tiền cuối kỳ = số dư 111+112+113 trên sổ', cf['70'] == cash_end, (cf['70'], cash_end))
check('B03: trả nhà cung cấp vào 02, thu thanh lý 50 triệu vào 22', cf['02'] <= -50_000_000 and cf['22'] == 50_000_000, (cf['02'], cf['22']))
check('B03 hiển thị khớp sổ', 'khớp số dư tiền' in b03_rep.html)
b02_after = b02._b02_values(date(2026, 1, 1), date(2026, 12, 31))
check('B02 không đổi sau kết chuyển', b02_after == vals)
try:
    env['lfood.closing'].with_user(users['ketoantruong']).create({'company_id': factory.id, 'date_to': date(2026, 9, 30)}).action_apply()
    check('Kết chuyển lần hai báo không còn số dư', False)
except UserError:
    check('Kết chuyển lần hai báo không còn số dư', True)

# ---- Thuế GTGT
VR = env['lfood.vat.return']
v435 = V.search([('name', '=', 'MDV00435')], limit=1)
cash_pay = Pay.create({'kind': 'out', 'method': 'cash', 'purpose': 'supplier', 'partner_id': v435.partner_id.id,
                       'amount': v435.report_amount_total, 'memo': 'Trả tiền mặt MDV00435', 'date': date(2026, 9, 12),
                       'voucher_id': v435.id})
cash_pay.action_post()
jul = VR.with_user(users['ketoanvien']).with_company(factory).create({'company_id': factory.id, 'period_type': 'month', 'year': 2026, 'month': 7})
check('Tờ khai tháng 7: kỳ 01/07-31/07, hạn nộp 20/08', (jul.date_from, jul.date_to, jul.due_date) == (date(2026, 7, 1), date(2026, 7, 31), date(2026, 8, 20)),
      (jul.date_from, jul.date_to, jul.due_date))
jul.action_fetch()
l433 = jul.purchase_line_ids.filtered(lambda l: l.source_id == v433.id)
l435 = jul.purchase_line_ids.filtered(lambda l: l.source_id == v435.id)
check('Bảng kê mua vào có MDV00433 được khấu trừ 7.800.400', sum(l433.mapped('tax')) == 7_800_400 and all(l433.mapped('deductible')),
      [(l.ref, l.tax, l.deductible, l.reason) for l in l433])
check('MDV00435 trả tiền mặt từ 5 triệu: không được khấu trừ', l435 and not any(l435.mapped('deductible')) and 'tiền mặt' in (l435[:1].reason or ''),
      [(l.tax, l.deductible, l.reason) for l in l435])
vj = jul._figures()
check('[25] chỉ gồm thuế được khấu trừ', vj['25'] == sum(jul.purchase_line_ids.filtered('deductible').mapped('tax')) and vj['24'] > vj['25'], (vj['24'], vj['25']))
try:
    jul.action_confirm(); check('Kế toán viên không xác nhận tờ khai', False)
except UserError:
    check('Kế toán viên không xác nhận tờ khai', True)
jul_kt = VR.with_user(users['ketoantruong']).browse(jul.id)
jul_kt.action_confirm()
check('Tháng 7 không có bán ra: chuyển kỳ sau [43] = [25]', jul.state == 'confirmed' and jul.carry_out == vj['25'], (jul.carry_out, vj['25']))
try:
    jul.write({'adj_37': 1}); check('Không sửa tờ khai đã xác nhận', False)
except UserError:
    check('Không sửa tờ khai đã xác nhận', True)

sepr = VR.with_user(users['ketoanvien']).with_company(factory).create({'company_id': factory.id, 'period_type': 'month', 'year': 2026, 'month': 9})
sepr.action_fetch()
check('Tờ khai tháng 9: [22] nhận số chuyển từ tháng 7', sepr.carry_in == jul.carry_out, (sepr.carry_in, jul.carry_out))
sale_line = sepr.sale_line_ids.filtered(lambda l: l.source_id == sale.id)
check('Bảng kê bán ra: doanh thu 200 triệu thuế 8% vào nhóm 10%, đánh dấu giảm thuế',
      sale_line and (sale_line.base, sale_line.tax, sale_line.group, sale_line.reduced) == (200_000_000, 16_000_000, '10', True),
      [(l.base, l.tax, l.group, l.reduced) for l in sale_line])
check('Phụ lục giảm thuế: thuế được giảm 4.000.000', '4.000.000' in sepr.reduction_html)
vs = sepr._figures()
check('[40a] = [35] - [25] - [22] khi dương', vs['40a'] == max(vs['35'] - vs['25'] - vs['22'], 0) and vs['35'] == 16_000_000, vs)
tax_before = net('33311')
VR.with_user(users['ketoantruong']).browse(sepr.id).action_confirm()
check('Xác nhận: bù trừ Nợ 33311 / Có 133, 33311 còn đúng số phải nộp',
      net('33311') - tax_before == vs['35'] - vs['40a'] and -net('33311') == vs['40a'], (net('33311'), vs['35'], vs['40a']))
try:
    VR.with_user(users['ketoantruong']).browse(jul.id).action_reset(); check('Không hủy xác nhận kỳ cũ khi kỳ sau đã xác nhận', False)
except UserError:
    check('Không hủy xác nhận kỳ cũ khi kỳ sau đã xác nhận', True)
VR.with_user(users['ketoantruong']).browse(sepr.id).action_reset()
check('Hủy xác nhận: đảo bút toán bù trừ', sepr.state == 'draft' and net('33311') == tax_before, (net('33311'), tax_before))

# ---- Bán hàng
SI = env['lfood.sale.invoice'].with_user(users['ketoanvien']).with_company(factory)
vat8 = ref('lfood_voucher.vat_8')
kct = ref('lfood_voucher.vat_kct')
inv = SI.create({'partner_id': customer.id, 'date': date(2026, 9, 20), 'invoice_template': '1', 'invoice_symbol': 'C26TLF',
                 'invoice_number': '00000123', 'due_date': date(2026, 9, 30), 'memo': 'Bán cháo hũ tháng 9',
                 'line_ids': [(0, 0, {'name': 'Cháo hũ', 'quantity': 1000, 'price_unit': 50000, 'vat_rate_id': vat8.id}),
                              (0, 0, {'name': 'Rau củ tươi', 'quantity': 10, 'price_unit': 100000, 'vat_rate_id': kct.id})]})
check('Hóa đơn bán ra: tiền hàng 51 triệu, thuế 8% 4 triệu', (inv.amount_untaxed, inv.amount_tax, inv.amount_total) == (51_000_000, 4_000_000, 55_000_000),
      (inv.amount_untaxed, inv.amount_tax, inv.amount_total))
inv.action_post()
m_inv = Move._active_for(inv)
check('Ghi sổ hóa đơn: Nợ 1311 / Có 511, Có 33311', m_inv and {(l.account_code, l.debit, l.credit) for l in m_inv.line_ids} ==
      {('1311', 55_000_000, 0), ('511', 0, 50_000_000), ('511', 0, 1_000_000), ('33311', 0, 4_000_000)},
      [(l.account_code, l.debit, l.credit) for l in m_inv.line_ids])
try:
    with env.cr.savepoint():
        SI.create({'partner_id': customer.id, 'invoice_template': '1', 'invoice_symbol': 'C26TLF', 'invoice_number': '00000123',
                   'line_ids': [(0, 0, {'name': 'x', 'price_unit': 1, 'vat_rate_id': vat8.id})]})
        env.flush_all()
    check('Không ghi nhận trùng số hóa đơn', False)
except Exception:
    check('Không ghi nhận trùng số hóa đơn', True)
refund = SI.create({'kind': 'refund', 'origin_id': inv.id, 'partner_id': customer.id, 'date': date(2026, 9, 25), 'invoice_template': '1',
                    'invoice_symbol': 'C26TLF', 'invoice_number': '00000130', 'memo': 'Giảm giá cháo hũ lỗi bao bì',
                    'line_ids': [(0, 0, {'name': 'Giảm giá cháo hũ', 'quantity': 1, 'price_unit': 5_000_000, 'vat_rate_id': vat8.id})]})
refund.action_post()
check('Giảm giá: Nợ 521, Nợ 33311 / Có 1311', {l.account_code for l in Move._active_for(refund).line_ids} == {'521', '33311', '1311'})
receipt = Pay.create({'kind': 'in', 'method': 'bank', 'purpose': 'customer', 'partner_id': customer.id, 'amount': 30_000_000,
                      'memo': 'Khách trả tiền hóa đơn 123', 'date': date(2026, 9, 28), 'sale_invoice_id': inv.id})
receipt.action_post()
inv.invalidate_recordset()
check('Còn phải thu = 55 triệu - 5,4 triệu giảm giá - 30 triệu đã thu', inv.amount_residual == 55_000_000 - 5_400_000 - 30_000_000, inv.amount_residual)
aging = env['lfood.aging'].with_user(users['ketoantruong']).create({'kind': 'receivable', 'company_id': factory.id, 'as_of': date(2026, 11, 15)})
summary = aging._summary()
check('Tuổi nợ: hóa đơn hạn 30/9 đến 15/11 là 31–60 ngày', summary.get(customer.name, [0] * 5)[2] == 19_600_000, summary.get(customer.name))
aging_pay = env['lfood.aging'].with_user(users['ketoantruong']).create({'kind': 'payable', 'company_id': factory.id, 'as_of': date(2026, 12, 31)})
check('Tuổi nợ phải trả có nhà cung cấp MDV00433', v433.partner_id.name in aging_pay._summary())
try:
    inv.action_cancel(); check('Kế toán viên không hủy hóa đơn', False)
except UserError:
    check('Kế toán viên không hủy hóa đơn', True)
try:
    env['lfood.sale.invoice'].with_user(users['ketoantruong']).browse(inv.id).action_cancel(); check('Không hủy hóa đơn đã có phiếu thu', False)
except UserError:
    check('Không hủy hóa đơn đã có phiếu thu', True)
oct_r = VR.with_user(users['ketoanvien']).with_company(factory).create({'company_id': factory.id, 'period_type': 'month', 'year': 2026, 'month': 9})
try:
    oct_r.action_fetch(); check('Không lập trùng tờ khai cùng kỳ', False)
except UserError:
    check('Không lập trùng tờ khai cùng kỳ', True)
oct_r.unlink()
VR.browse(sepr.id).with_user(users['ketoanvien']).action_fetch()
out = sepr.sale_line_ids
check('Bảng kê bán ra lấy từ hóa đơn: 8% nhóm 10% giảm thuế, KCT nhóm không chịu thuế, giảm giá ghi âm',
      {(round(l.base), l.group, l.reduced) for l in out.filtered(lambda l: l.source_model == 'lfood.sale.invoice')}
      == {(50_000_000, '10', True), (1_000_000, 'none', False), (-5_000_000, '10', True)},
      [(l.base, l.group, l.reduced, l.source_model) for l in out])
check('Phiếu kế toán doanh thu cũ vẫn lên bảng kê', out.filtered(lambda l: l.source_model == 'lfood.move' and l.base == 200_000_000))

# ---- Kho
WH = env['lfood.warehouse'].sudo()
wh_a = WH.create({'code': 'KA', 'name': 'Kho thành phẩm A', 'company_id': factory.id})
wh_b = WH.create({'code': 'KB', 'name': 'Kho B', 'company_id': factory.id})
prod = env['lfood.product'].with_user(users['ketoanvien']).with_company(factory).create(
    {'code': 'CH01', 'name': 'Cháo hũ thịt bằm', 'uom': 'hũ', 'kind': 'goods', 'vat_rate_id': vat8.id, 'company_id': factory.id})
PK = env['lfood.stock.picking'].with_user(users['ketoanvien']).with_company(factory)
vendor2 = v433.partner_id
p_in1 = PK.create({'kind': 'in', 'purpose': 'purchase', 'date': date(2026, 10, 1), 'warehouse_id': wh_a.id, 'partner_id': vendor2.id,
                   'invoice_symbol': 'C26TAA', 'invoice_number': '0000777', 'invoice_date': date(2026, 10, 1), 'memo': 'Mua cháo hũ',
                   'line_ids': [(0, 0, {'product_id': prod.id, 'lot_name': 'L1', 'expiry_date': date(2026, 12, 1), 'quantity': 100,
                                        'price_unit': 10000, 'vat_rate_id': vat8.id})]})
p_in1.action_done()
m_in1 = Move._active_for(p_in1)
check('Nhập mua: Nợ 156 1.000.000, Nợ 1331 80.000 / Có 3311 1.080.000', m_in1 and {(l.account_code, l.debit, l.credit) for l in m_in1.line_ids} ==
      {('156', 1_000_000, 0), ('3311', 0, 1_000_000), ('1331', 80_000, 0), ('3311', 0, 80_000)}, [(l.account_code, l.debit, l.credit) for l in m_in1.line_ids])
p_in2 = PK.create({'kind': 'in', 'purpose': 'purchase', 'date': date(2026, 10, 5), 'warehouse_id': wh_a.id, 'partner_id': vendor2.id,
                   'invoice_symbol': 'C26TAA', 'invoice_number': '0000790', 'line_ids': [(0, 0, {'product_id': prod.id, 'lot_name': 'L2',
                   'expiry_date': date(2026, 11, 10), 'quantity': 100, 'price_unit': 13000})]})
p_in2.action_done()
check('Giá bình quân sau 2 lần nhập = 11.500', prod.avg_cost == 11500 and prod.qty_on_hand == 200, (prod.avg_cost, prod.qty_on_hand))
p_use = PK.create({'kind': 'out', 'purpose': 'internal', 'date': date(2026, 10, 6), 'warehouse_id': wh_a.id, 'memo': 'Xuất dùng thử mẫu',
                   'line_ids': [(0, 0, {'product_id': prod.id, 'quantity': 50})]})
p_use.action_done()
lot1 = env['lfood.stock.lot'].search([('product_id', '=', prod.id), ('name', '=', 'L1')])
lot2 = env['lfood.stock.lot'].search([('product_id', '=', prod.id), ('name', '=', 'L2')])
check('Xuất FEFO lấy lô hết hạn trước (L2), giá vốn 575.000', p_use.amount == 575_000 and lot2.qty_on_hand == 50 and lot1.qty_on_hand == 100,
      (p_use.amount, lot1.qty_on_hand, lot2.qty_on_hand))
try:
    PK.create({'kind': 'out', 'purpose': 'internal', 'date': date(2026, 10, 2), 'warehouse_id': wh_a.id,
               'line_ids': [(0, 0, {'product_id': prod.id, 'quantity': 1})]}).action_done()
    check('Chặn ghi phiếu lùi ngày', False)
except UserError:
    check('Chặn ghi phiếu lùi ngày', True)
try:
    PK.create({'kind': 'out', 'purpose': 'internal', 'date': date(2026, 10, 7), 'warehouse_id': wh_a.id,
               'line_ids': [(0, 0, {'product_id': prod.id, 'quantity': 1000})]}).action_done()
    check('Chặn xuất âm', False)
except UserError:
    check('Chặn xuất âm', True)
inv2 = SI.create({'partner_id': customer.id, 'date': date(2026, 10, 10), 'invoice_template': '1', 'invoice_symbol': 'C26TLF',
                  'invoice_number': '00000200', 'warehouse_id': wh_a.id,
                  'line_ids': [(0, 0, {'product_id': prod.id, 'name': 'Cháo hũ thịt bằm', 'quantity': 120, 'price_unit': 20000, 'vat_rate_id': vat8.id})]})
inv2.action_post()
out_pick = inv2.picking_ids
check('Hóa đơn bán có hàng: tự xuất kho, giá vốn 1.380.000 (Nợ 632 / Có 156)', out_pick.state == 'done' and out_pick.amount == 1_380_000
      and {l.account_code for l in Move._active_for(out_pick).line_ids} == {'632', '156'}, (out_pick.amount, out_pick.state))
tr = PK.create({'kind': 'transfer', 'purpose': 'transfer', 'date': date(2026, 10, 11), 'warehouse_id': wh_a.id, 'dest_warehouse_id': wh_b.id,
                'line_ids': [(0, 0, {'product_id': prod.id, 'quantity': 10})]})
tr.action_done()
check('Chuyển kho: không ghi sổ, tồn chuyển sang kho B', not Move._active_for(tr) and prod._position(wh_b)[0] == 10 and prod._position(wh_a)[0] == 20,
      (prod._position(wh_a), prod._position(wh_b)))
cnt = PK.create({'kind': 'out', 'purpose': 'count', 'date': date(2026, 10, 12), 'warehouse_id': wh_b.id, 'memo': 'Kiểm kê thiếu',
                 'line_ids': [(0, 0, {'product_id': prod.id, 'quantity': 5})]})
cnt.action_done()
check('Kiểm kê thiếu: Nợ 1381 / Có 156', {l.account_code for l in Move._active_for(cnt).line_ids} == {'1381', '156'})
env.flush_all()
stock_gl = round(sum(ML.sudo().search([('move_id.source_model', '=', 'lfood.stock.picking'), ('account_code', '=', '156'),
                                       ('state', '=', 'posted')]).mapped('balance')))
prod.invalidate_recordset()
check('Giá trị tồn trên thẻ kho = số dư 156 từ phiếu kho', prod.value_on_hand == stock_gl and prod.qty_on_hand == 25, (prod.value_on_hand, stock_gl, prod.qty_on_hand))
srep = env['lfood.stock.report'].with_user(users['ketoantruong']).create({'report': 'balance', 'company_id': factory.id,
                                                                         'date_from': date(2026, 10, 1), 'date_to': date(2026, 10, 31)})
check('Nhập xuất tồn có mặt hàng CH01', 'CH01' in srep.html)
erep = env['lfood.stock.report'].with_user(users['ketoantruong']).create({'report': 'expiry', 'company_id': factory.id,
                                                                         'date_from': date(2026, 10, 1), 'date_to': date(2026, 10, 31), 'days': 60})
check('Báo cáo hàng sắp hết hạn có lô L1', 'L1' in erep.html)
try:
    env['lfood.stock.picking'].with_user(users['ketoantruong']).browse(p_in1.id).action_cancel(); check('Không hủy phiếu cũ khi đã có phiếu sau', False)
except UserError:
    check('Không hủy phiếu cũ khi đã có phiếu sau', True)
octr = VR.with_user(users['ketoanvien']).with_company(factory).create({'company_id': factory.id, 'period_type': 'month', 'year': 2026, 'month': 10})
octr.action_fetch()
check('Bảng kê mua vào tháng 10 có hóa đơn hàng hóa 0000777 được khấu trừ 80.000',
      octr.purchase_line_ids.filtered(lambda l: l.source_model == 'lfood.stock.picking' and '0000777' in l.ref and l.deductible and l.tax == 80_000))

# ---- Tiền lương và bảo hiểm
Emp = env['lfood.employee'].with_user(users['ketoanvien']).with_company(factory)
basic, advance = ref('lfood_payroll.comp_basic'), ref('lfood_payroll.comp_advance')
e1 = Emp.create({'code': 'NV001', 'name': 'Nguyễn Văn Lương', 'region': 'I', 'insurance_salary': 40_000_000, 'dependents': 1,
                 'cost_account': '6421', 'company_id': factory.id, 'component_line_ids': [(0, 0, {'component_id': basic.id, 'amount': 40_000_000})]})
e2 = Emp.create({'code': 'NV002', 'name': 'Trần Thị Thấp', 'region': 'I', 'insurance_salary': 4_000_000, 'cost_account': '622',
                 'company_id': factory.id, 'component_line_ids': [(0, 0, {'component_id': basic.id, 'amount': 4_000_000})]})
e3 = Emp.create({'code': 'NV003', 'name': 'Lê Văn Cao', 'region': 'I', 'insurance_salary': 80_000_000, 'cost_account': '6411',
                 'company_id': factory.id, 'component_line_ids': [(0, 0, {'component_id': basic.id, 'amount': 80_000_000})]})
check('Nhân viên có đối tượng công nợ để theo dõi 334', e1.partner_id and e2.partner_id)
adv = Pay.create({'kind': 'out', 'method': 'cash', 'purpose': 'advance', 'partner_id': e3.partner_id.id, 'amount': 5_000_000,
                  'memo': 'Tạm ứng công tác', 'date': date(2026, 9, 5)})
adv.action_post()
run = env['lfood.payroll.run'].with_user(users['ketoanvien']).with_company(factory).create({'company_id': factory.id, 'year': 2026, 'month': 9})
run.action_load_employees()
s1, s2, s3 = [run.slip_ids.filtered(lambda s, e=e: s.employee_id == e) for e in (e1, e2, e3)]
check('Lương 40 triệu, 1 người phụ thuộc: BH 4.200.000, thuế TNCN 910.000, thực lĩnh 34.890.000',
      (s1.emp_si + s1.emp_hi + s1.emp_ui, s1.pit, s1.net) == (4_200_000, 910_000, 34_890_000), (s1.emp_si, s1.emp_hi, s1.emp_ui, s1.pit, s1.net))
check('Doanh nghiệp đóng cho lương 40 triệu: BHXH 7.000.000, BHYT 1.200.000, BHTN 400.000, KPCĐ 800.000',
      (s1.co_si, s1.co_hi, s1.co_ui, s1.co_union) == (7_000_000, 1_200_000, 400_000, 800_000))
check('Lương 4 triệu vùng I: đóng BH trên 5.310.000, có cảnh báo', s2.si_base == 5_310_000 and 'tối thiểu vùng' in (s2.warning or ''), (s2.si_base, s2.warning))
s3.write({'worked_days': 13, 'line_ids': [(0, 0, {'component_id': advance.id, 'amount': 5_000_000})]})
run.action_compute()
check('Làm nửa tháng: lương 40 triệu; BHXH trên trần 50.600.000 (lương cơ sở 2.530.000 từ 7/2026)',
      s3.gross == 40_000_000 and s3.si_base == 50_600_000 and s3.emp_si == 4_048_000, (s3.gross, s3.si_base, s3.emp_si))
exp_pit3 = max(0, 40_000_000 - (s3.emp_si + s3.emp_hi + s3.emp_ui) - 15_500_000)
check('Thuế TNCN nửa tháng tính trên thu nhập thực nhận', s3.assessable == exp_pit3, (s3.assessable, exp_pit3))
check('Trừ tạm ứng 5 triệu vào thực lĩnh', s3.net == 40_000_000 - (s3.emp_si + s3.emp_hi + s3.emp_ui) - s3.pit - 5_000_000, s3.net)
try:
    run.action_post(); check('Kế toán viên không ghi sổ bảng lương', False)
except UserError:
    check('Kế toán viên không ghi sổ bảng lương', True)
try:
    env['lfood.payroll.run'].with_user(users['giamdoc']).create({'company_id': factory.id, 'year': 2026, 'month': 8}); check('Giám đốc không lập bảng lương', False)
except AccessError:
    check('Giám đốc không lập bảng lương', True)
run_kt = env['lfood.payroll.run'].with_user(users['ketoantruong']).browse(run.id)
debt_adv = net('141', partner_id=e3.partner_id.id)
run_kt.action_post()
m_run = Move._active_for(run)
check('Ghi sổ lương: bút toán cân, có 334, 3383, 3384, 3386, 3382, 3335, 622, 6411, 6421, 141',
      m_run and {'334', '3383', '3384', '3386', '3382', '3335', '622', '6411', '6421', '141'} <= set(m_run.line_ids.mapped('account_code')))
check('3335 thuế TNCN = tổng thuế khấu trừ', -net('3335') >= run.total_pit and run.total_pit == s1.pit + s2.pit + s3.pit)
check('334 còn phải trả = tổng thực lĩnh', -sum(net('334', partner_id=e.partner_id.id) for e in (e1, e2, e3)) == run.total_net,
      (sum(net('334', partner_id=e.partner_id.id) for e in (e1, e2, e3)), run.total_net))
check('Trừ tạm ứng làm giảm 141 của nhân viên', net('141', partner_id=e3.partner_id.id) == debt_adv - 5_000_000)
try:
    run.write({'standard_days': 22}); check('Không sửa bảng lương đã ghi sổ', False)
except UserError:
    check('Không sửa bảng lương đã ghi sổ', True)
run.write({'pay_date': date(2026, 9, 30)})
run.action_pay()
check('Chi lương: 334 của nhân viên về 0', all(net('334', partner_id=e.partner_id.id) == 0 for e in (e1, e2, e3)) and run.state == 'paid')
log = Log.sudo().search([('model', '=', 'lfood.payroll.run'), ('res_id', '=', run.id), ('summary', 'ilike', 'Ghi sổ')], limit=1)
check('Nhật ký ghi đích danh Kế toán trưởng ghi sổ lương', log.user_id == users['ketoantruong'], log.user_id.login)
run_kt.action_reset()
check('Hủy ghi sổ: đảo cả bút toán lương và chi lương', run.state == 'draft' and net('3335') == 0 and all(
    net('334', partner_id=e.partner_id.id) == 0 for e in (e1, e2, e3)), (net('3335'),))
check('Căn cứ giảm trừ gia cảnh ghi Nghị quyết 110/2025/UBTVQH15', 'Nghị quyết 110/2025' in ref('lfood_voucher.pv_pit_self').legal_ref)

# ---- ngân sách trên cây khoản mục
Budget = env['lfood.budget'].with_user(users['ketoanvien']).with_company(factory)
Item = env['lfood.cost.item']
parent = Item.search([('child_ids', '!=', False)], limit=1)
leaves = Item.search([('parent_id', 'child_of', parent.id), ('child_ids', '=', False)]) or Item.search(
    [('parent_id', '=', parent.id), ('child_ids', '=', False)])
budget = Budget.create({'name': 'Ngân sách thử', 'year': 2026, 'company_id': factory.id})
budget.action_load_items()
n_leaf_all = Item.search_count(['&', ('child_ids', '=', False), '|', ('company_id', '=', False), ('company_id', '=', factory.id)])
check('Nạp khoản mục: đủ 12 tháng cho mỗi khoản mục chi tiết', len(budget.line_ids) == n_leaf_all * 12,
      (len(budget.line_ids), n_leaf_all))
budget.action_load_items()
check('Nạp lại không tạo dòng trùng', len(budget.line_ids) == n_leaf_all * 12)
b_leaves = budget.line_ids.filtered(lambda l: l.month == '1' and l.cost_item_id in leaves)
for i, line in enumerate(b_leaves):
    line.amount = 10_000_000 * (i + 1)
before = sum(b_leaves.mapped('amount'))
check('Số của khoản mục cha là tổng các khoản con', budget.amount_for(parent, 1) == before, (budget.amount_for(parent, 1), before))
budget.set_amount(parent, 1, before * 2 + 1)
check('Sửa cấp cha chia xuống con, tổng khớp tới đồng', sum(b_leaves.mapped('amount')) == before * 2 + 1,
      b_leaves.mapped('amount'))
if len(b_leaves) > 1:
    keep = b_leaves[0]
    keep.locked = True
    kept = keep.amount
    budget.set_amount(parent, 1, before * 3)
    check('Dòng khóa giữ nguyên khi cha chia lại', keep.amount == kept and sum(b_leaves.mapped('amount')) == before * 3,
          (keep.amount, kept))
    try:
        budget.set_amount(parent, 1, kept - 1); check('Chặn chia nhỏ hơn tổng dòng đang khóa', False)
    except UserError:
        check('Chặn chia nhỏ hơn tổng dòng đang khóa', True)
    keep.locked = False
env.cr.execute('SAVEPOINT budget_leaf')
try:
    env['lfood.budget.line'].with_user(users['ketoanvien']).create(
        {'budget_id': budget.id, 'cost_item_id': parent.id, 'month': '1', 'amount': 1})
    env.flush_all()
    check('Không nhập kế hoạch ở khoản mục cha', False)
except UserError as err:
    check('Không nhập kế hoạch ở khoản mục cha', 'khoản mục chi tiết' in str(err), str(err)[:60])
env.cr.execute('ROLLBACK TO SAVEPOINT budget_leaf')
env.invalidate_all()
try:
    budget.action_approve(); check('Kế toán viên không duyệt ngân sách', False)
except (UserError, AccessError):
    check('Kế toán viên không duyệt ngân sách', True)
budget_kt = env['lfood.budget'].with_user(users['ketoantruong']).with_company(factory).browse(budget.id)
budget_kt.action_approve()
check('Duyệt ngân sách: trạng thái Đã duyệt, có nhật ký', budget_kt.state == 'approved' and Log.sudo().search_count(
    [('model', '=', 'lfood.budget'), ('res_id', '=', budget.id)]) > 0)
try:
    budget.line_ids[0].write({'amount': 1}); check('Không sửa ngân sách đã duyệt', False)
except UserError:
    check('Không sửa ngân sách đã duyệt', True)
act_v2 = budget_kt.action_new_version()
v2 = env['lfood.budget'].browse(act_v2['res_id'])
env.flush_all(); env.invalidate_all()
check('Lập phiên bản mới: bản 2, trạng thái Nháp, giữ nguyên số', v2.version == budget.version + 1 and v2.state == 'draft'
      and sum(v2.line_ids.mapped('amount')) == sum(budget.line_ids.mapped('amount')),
      (v2.version, v2.state, sum(v2.line_ids.mapped('amount')), sum(budget.line_ids.mapped('amount')),
       v2.amount_total, budget.amount_total))
env.flush_all()
line_used = ML.sudo().search([('state', '=', 'posted'), ('cost_item_id', '!=', False),
                              ('cost_item_id.child_ids', '=', False),
                              ('company_id', '=', factory.id), ('date', '>=', '2026-01-01'),
                              ('date', '<=', '2026-12-31'), ('debit', '>', 0)], limit=1)
item_used = line_used.cost_item_id
check('Có bút toán đã ghi sổ gắn khoản mục để đối chiếu ngân sách', bool(item_used))
if item_used:
    y, m = line_used.date.year, line_used.date.month
    Report = env['lfood.budget.report'].sudo().with_company(factory)
    actual = Report.actual_for(item_used, y, m, company=factory)
    check('Thực tế của khoản mục lấy từ bút toán đã ghi sổ', actual != 0, actual)
    plan_line = budget_kt.line_ids.filtered(lambda l: l.cost_item_id == item_used and l.month == str(m))
    check('Ngân sách có dòng cho khoản mục đang phát sinh', bool(plan_line))
    if plan_line:
        Budget_sys = env['lfood.budget'].sudo().with_company(factory)
        plan_line.sudo().with_context(lfood_budget_system=True).write({'amount': max(1, abs(actual) / 2)})
        warn = Budget_sys.check_over(item_used, line_used.date)
        check('Cảnh báo khi thực tế vượt kế hoạch', 'vượt' in warn, warn[:80])
        plan_line.sudo().with_context(lfood_budget_system=True).write({'amount': abs(actual) * 10})
        check('Không cảnh báo khi còn trong kế hoạch', Budget_sys.check_over(item_used, line_used.date) == '')
rep = env['lfood.budget.report'].sudo().search([('year', '=', 2026)], limit=1)
check('Báo cáo ngân sách và thực tế chạy được', bool(rep) and rep.diff_amount == rep.actual_amount - rep.plan_amount)

# ---- mua hàng: yêu cầu mua, đơn mua, nhận hàng, đối chiếu 3 bên
REQ = env['lfood.purchase.request'].with_user(users['ketoanvien']).with_company(factory)
PO = env['lfood.purchase.order'].with_user(users['ketoanvien']).with_company(factory)
nl = env['lfood.product'].with_user(users['ketoanvien']).with_company(factory).create(
    {'code': 'NL01', 'name': 'Gạo lứt', 'uom': 'kg', 'kind': 'material', 'vat_rate_id': vat8.id, 'company_id': factory.id})
item_buy = Item.search([('child_ids', '=', False)], limit=1)
req = REQ.create({'date': date(2026, 11, 1), 'date_needed': date(2026, 11, 10), 'department': 'Nhà máy',
                  'reason': 'Bổ sung nguyên liệu',
                  'line_ids': [(0, 0, {'product_id': nl.id, 'name': 'Gạo lứt', 'quantity': 100, 'price_unit': 20_000,
                                       'cost_item_id': item_buy.id})]})
check('Yêu cầu mua được cấp số YCM và tính giá trị dự kiến', req.name.startswith('YCM') and req.amount == 2_000_000,
      (req.name, req.amount))
req.action_confirm()
check('Trình duyệt yêu cầu mua: chờ duyệt', req.state == 'waiting')
try:
    req.action_approve(); check('Kế toán viên không duyệt yêu cầu mua', False)
except (UserError, AccessError):
    check('Kế toán viên không duyệt yêu cầu mua', True)
try:
    req.write({'reason': 'sửa khi đang chờ duyệt'}); check('Không sửa yêu cầu đã trình duyệt', False)
except UserError:
    check('Không sửa yêu cầu đã trình duyệt', True)
req_kt = env['lfood.purchase.request'].with_user(users['ketoantruong']).with_company(factory).browse(req.id)
req_kt.action_approve()
check('Kế toán trưởng duyệt yêu cầu mua', req.state == 'approved' and req.approved_by == users['ketoantruong'])
act_po = req.action_make_order()
order = env['lfood.purchase.order'].with_user(users['ketoanvien']).with_company(factory).browse(act_po['res_id'])
check('Lập đơn mua từ yêu cầu: chép dòng, yêu cầu chuyển sang Đã đặt hàng',
      order.name.startswith('DM') and len(order.line_ids) == 1 and order.line_ids.quantity == 100
      and req.state == 'ordered', (order.name, req.state))
order.write({'partner_id': supplier.id, 'date': date(2026, 11, 2), 'warehouse_id': wh_a.id,
             'line_ids': [(1, order.line_ids.id, {'vat_rate_id': vat8.id})]})
check('Đơn mua tính thuế GTGT 8%', order.amount == 2_000_000 and order.amount_tax == 160_000
      and order.amount_total == 2_160_000, (order.amount, order.amount_tax))
order.action_confirm()
check('Đơn mua dưới hạn mức: xác nhận ngay', order.state == 'confirmed')
try:
    order.write({'memo': 'sửa sau xác nhận'}); check('Không sửa đơn mua đã xác nhận', False)
except UserError:
    check('Không sửa đơn mua đã xác nhận', True)
big = PO.create({'partner_id': supplier.id, 'date': date(2026, 11, 2), 'warehouse_id': wh_a.id,
                 'line_ids': [(0, 0, {'product_id': nl.id, 'name': 'Gạo lứt', 'quantity': 10_000, 'price_unit': 20_000})]})
big.action_confirm()
check('Đơn mua vượt hạn mức duyệt: chờ duyệt', big.state == 'waiting', (big.amount_total, big.state))
env['lfood.purchase.order'].with_user(users['ketoantruong']).with_company(factory).browse(big.id).action_confirm()
check('Kế toán trưởng duyệt đơn vượt hạn mức', big.state == 'confirmed')
big.action_cancel()
act_pick = order.action_receive()
pick = env['lfood.stock.picking'].with_user(users['ketoanvien']).with_company(factory).browse(act_pick['res_id'])
check('Nhận hàng tạo phiếu nhập nháp đúng số lượng và đơn giá theo đơn',
      pick.state == 'draft' and pick.purchase_order_id == order and pick.line_ids.quantity == 100
      and pick.line_ids.price_unit == 20_000, (pick.state, pick.line_ids.quantity))
pick.write({'date': date(2026, 11, 3), 'invoice_symbol': 'C26TAA', 'invoice_number': '0000801',
            'invoice_date': date(2026, 11, 3)})
pick.line_ids.write({'quantity': 130, 'lot_name': 'GL1', 'expiry_date': date(2027, 5, 1)})
try:
    pick.action_done(); check('Chặn ghi phiếu khi nhận nhiều hơn đơn mua', False)
except UserError as err:
    check('Chặn ghi phiếu khi nhận nhiều hơn đơn mua', 'dung sai' in str(err), str(err)[:70])
pick.line_ids.write({'quantity': 100, 'price_unit': 30_000})
try:
    pick.action_done(); check('Chặn ghi phiếu khi đơn giá hóa đơn lệch đơn mua', False)
except UserError as err:
    check('Chặn ghi phiếu khi đơn giá hóa đơn lệch đơn mua', 'đơn giá' in str(err), str(err)[:70])
pick.line_ids.write({'price_unit': 20_000})
pick.action_done()
env.flush_all(); env.invalidate_all()
check('Ghi phiếu nhập theo đơn: cập nhật đã nhận và đã có hóa đơn',
      order.line_ids.qty_received == 100 and order.line_ids.qty_billed == 100,
      (order.line_ids.qty_received, order.line_ids.qty_billed))
check('Đơn mua nhận đủ chuyển sang Đã nhận đủ', order.state == 'done', order.state)
check('Đối chiếu 3 bên khớp', 'khớp nhau' in order.match_note, order.match_note[:60])
m_pick = Move._active_for(pick)
check('Nhập mua theo đơn vẫn ghi sổ Nợ 152, Nợ 1331 / Có 3311',
      m_pick and {'152', '1331', '3311'} <= set(m_pick.line_ids.mapped('account_code')))
try:
    order.action_cancel(); check('Không hủy đơn mua đã có phiếu nhập đã ghi', False)
except UserError:
    check('Không hủy đơn mua đã có phiếu nhập đã ghi', True)
tol_before = factory.lfood_purchase_tolerance
factory.sudo().with_context(lfood_audit_skip=True).write({'lfood_purchase_tolerance': 10})
order2 = PO.create({'partner_id': supplier.id, 'date': date(2026, 11, 4), 'warehouse_id': wh_a.id,
                    'line_ids': [(0, 0, {'product_id': nl.id, 'name': 'Gạo lứt', 'quantity': 100, 'price_unit': 20_000,
                                         'vat_rate_id': vat8.id})]})
order2.action_confirm()
pick2 = env['lfood.stock.picking'].with_user(users['ketoanvien']).with_company(factory).browse(
    order2.action_receive()['res_id'])
pick2.write({'date': date(2026, 11, 5)})
pick2.line_ids.write({'quantity': 105, 'lot_name': 'GL2', 'expiry_date': date(2027, 6, 1)})
pick2.action_done()
check('Dung sai 10%: nhận thừa 5% vẫn ghi được phiếu', pick2.state == 'done')
factory.sudo().with_context(lfood_audit_skip=True).write({'lfood_purchase_tolerance': tol_before})

# ---- báo giá và so sánh báo giá
QUOTE = env['lfood.purchase.quote'].with_user(users['ketoanvien']).with_company(factory)
vendor_b = env['res.partner'].sudo().create({'name': 'NCC báo giá B', 'is_company': True})
req2 = REQ.create({'date': date(2026, 11, 6), 'date_needed': date(2026, 11, 20), 'department': 'Nhà máy',
                   'line_ids': [(0, 0, {'product_id': nl.id, 'name': 'Gạo lứt', 'quantity': 5_000,
                                        'price_unit': 25_000, 'cost_item_id': item_buy.id})]})
req2.action_confirm()
env['lfood.purchase.request'].with_user(users['ketoantruong']).with_company(factory).browse(req2.id).action_approve()
check('Yêu cầu mua lớn: 125 triệu', req2.amount == 125_000_000, req2.amount)
try:
    req2.action_make_order(); check('Chặn lập đơn khi chưa đủ báo giá tối thiểu', False)
except UserError as err:
    check('Chặn lập đơn khi chưa đủ báo giá tối thiểu', 'báo giá' in str(err), str(err)[:70])
q1 = QUOTE.create({'request_id': req2.id, 'partner_id': supplier.id, 'date': date(2026, 11, 7), 'lead_days': 7,
                   'line_ids': [(0, 0, {'product_id': nl.id, 'name': 'Gạo lứt', 'quantity': 5_000,
                                        'price_unit': 24_000, 'vat_rate_id': vat8.id})]})
q2 = QUOTE.create({'request_id': req2.id, 'partner_id': vendor_b.id, 'date': date(2026, 11, 7), 'lead_days': 3,
                   'line_ids': [(0, 0, {'product_id': nl.id, 'name': 'Gạo lứt', 'quantity': 5_000,
                                        'price_unit': 23_000, 'vat_rate_id': vat8.id})]})
check('Báo giá tính tiền hàng và thuế', q2.amount == 115_000_000 and q2.amount_tax == 9_200_000
      and q2.amount_total == 124_200_000, (q2.amount, q2.amount_tax))
try:
    req2.action_make_order(); check('Vẫn chặn khi mới có 2 trong 3 báo giá', False)
except UserError:
    check('Vẫn chặn khi mới có 2 trong 3 báo giá', True)
q3 = QUOTE.create({'request_id': req2.id, 'partner_id': vendor2.id, 'date': date(2026, 11, 8), 'lead_days': 10,
                   'line_ids': [(0, 0, {'product_id': nl.id, 'name': 'Gạo lứt', 'quantity': 5_000,
                                        'price_unit': 26_000, 'vat_rate_id': vat8.id})]})
check('Đủ 3 báo giá, sắp xếp theo tổng tiền tăng dần',
      req2.quote_count == 3 and min(req2.quote_ids, key=lambda q: q.amount_total) == q2,
      (req2.quote_count, [(q.partner_id.name, q.amount_total) for q in req2.quote_ids]))
order3 = env['lfood.purchase.order'].browse(q2.action_choose()['res_id'])
check('Chọn báo giá rẻ nhất: đơn mua theo đúng giá đã báo, giao sau 3 ngày',
      order3.partner_id == vendor_b and order3.line_ids.price_unit == 23_000 and q2.chosen
      and req2.state == 'ordered', (order3.partner_id.name, order3.line_ids.price_unit))
check('Nhật ký ghi lại báo giá đã chọn và báo giá thấp nhất', Log.sudo().search_count(
    [('model', '=', 'lfood.purchase.request'), ('res_id', '=', req2.id), ('summary', 'ilike', 'Chọn báo giá')]) == 1)

# ---- trả lại hàng mua
qty_before = order.line_ids.qty_received
ret = env['lfood.stock.picking'].with_user(users['ketoanvien']).with_company(factory).create(
    {'kind': 'out', 'purpose': 'return_out', 'date': date(2026, 11, 6), 'warehouse_id': wh_a.id,
     'partner_id': supplier.id, 'purchase_order_id': order.id, 'memo': 'Trả lại gạo không đạt',
     'line_ids': [(0, 0, {'product_id': nl.id, 'quantity': 20, 'price_unit': 20_000, 'vat_rate_id': vat8.id})]})
try:
    ret.line_ids.write({'quantity': 500})
    ret.action_done(); check('Chặn trả lại nhiều hơn số đã nhận theo đơn', False)
except UserError as err:
    check('Chặn trả lại nhiều hơn số đã nhận theo đơn', 'không trả lại' in str(err), str(err)[:70])
ret.line_ids.write({'quantity': 20})
debt_ret = net('331', partner_id=supplier.id)
ret.action_done()
env.flush_all(); env.invalidate_all()
check('Trả lại hàng mua trừ vào số đã nhận của đơn', order.line_ids.qty_received == qty_before - 20,
      (order.line_ids.qty_received, qty_before))
m_ret = Move._active_for(ret)
check('Trả lại hàng mua: Nợ 3311 / Có 152 và Có 1331 giảm thuế đầu vào',
      m_ret and {'3311', '152', '1331'} <= set(m_ret.line_ids.mapped('account_code')),
      m_ret and m_ret.line_ids.mapped('account_code'))
check('Công nợ nhà cung cấp giảm sau khi trả hàng', net('331', partner_id=supplier.id) > debt_ret)

# ---- chi phí mua hàng và giảm giá hàng mua cộng, trừ vào giá nhập
ADJ = env['lfood.purchase.adjust'].with_user(users['ketoanvien']).with_company(factory)
qty_nl, val_nl = nl._position()
freight = ADJ.create({'kind': 'landed', 'date': date(2026, 11, 7), 'picking_id': pick.id, 'partner_id': vendor2.id,
                      'method': 'value', 'amount': 1_000_000, 'vat_rate_id': vat8.id,
                      'memo': 'Cước vận chuyển gạo', 'cost_item_id': item_buy.id})
check('Chứng từ điều chỉnh giá nhập được cấp số và tính thuế 8%',
      freight.name.startswith('DCG') and freight.tax == 80_000, (freight.name, freight.tax))
freight.action_post()
env.flush_all(); env.invalidate_all()
qty_after, val_after = nl._position()
check('Chi phí mua hàng cộng vào giá trị tồn, không đổi số lượng',
      qty_after == qty_nl and val_after == val_nl + 1_000_000, (qty_nl, qty_after, val_nl, val_after))
check('Phân bổ hết 1.000.000 theo giá trị hàng', sum(freight.line_ids.mapped('amount')) == 1_000_000,
      freight.line_ids.mapped('amount'))
m_fr = Move._active_for(freight)
check('Chi phí mua hàng: Nợ 152, Nợ 1331 / Có 3311',
      m_fr and {('152', 1_000_000, 0), ('1331', 80_000, 0)} <= {(l.account_code, l.debit, l.credit) for l in m_fr.line_ids}
      and round(sum(m_fr.line_ids.mapped('balance'))) == 0,
      m_fr and [(l.account_code, l.debit, l.credit) for l in m_fr.line_ids])
rebate = ADJ.create({'kind': 'rebate', 'date': date(2026, 11, 8), 'picking_id': pick.id, 'partner_id': supplier.id,
                     'method': 'qty', 'amount': 300_000, 'memo': 'Giảm giá hàng kém phẩm chất'})
rebate.action_post()
env.flush_all(); env.invalidate_all()
check('Giảm giá hàng mua trừ vào giá trị tồn', nl._position()[1] == val_after - 300_000,
      (nl._position()[1], val_after))
m_rb = Move._active_for(rebate)
check('Giảm giá hàng mua: Nợ 3311 / Có 152', m_rb and ('3311', 300_000, 0) in
      {(l.account_code, l.debit, l.credit) for l in m_rb.line_ids} and ('152', 0, 300_000) in
      {(l.account_code, l.debit, l.credit) for l in m_rb.line_ids},
      m_rb and [(l.account_code, l.debit, l.credit) for l in m_rb.line_ids])
try:
    rebate.write({'amount': 1}); check('Không sửa chứng từ điều chỉnh đã ghi sổ', False)
except UserError:
    check('Không sửa chứng từ điều chỉnh đã ghi sổ', True)
try:
    rebate.action_cancel(); check('Kế toán viên không hủy chứng từ đã ghi sổ', False)
except (UserError, AccessError):
    check('Kế toán viên không hủy chứng từ đã ghi sổ', True)
val_before_cancel = nl._position()[1]
env['lfood.purchase.adjust'].with_user(users['ketoantruong']).with_company(factory).browse(rebate.id).action_cancel()
env.flush_all(); env.invalidate_all()
check('Hủy chứng từ điều chỉnh: đảo bút toán và trả lại giá trị tồn',
      rebate.state == 'cancel' and nl._position()[1] == val_before_cancel + 300_000,
      (rebate.state, nl._position()[1], val_before_cancel))
try:
    ADJ.create({'kind': 'landed', 'date': date(2026, 10, 1), 'picking_id': pick.id, 'partner_id': vendor2.id,
                'amount': 100_000}).action_post()
    check('Chặn điều chỉnh có ngày trước ngày phiếu nhập', False)
except UserError as err:
    check('Chặn điều chỉnh có ngày trước ngày phiếu nhập', 'trước ngày phiếu nhập' in str(err), str(err)[:70])


# ---- bảng kê thu mua không có hóa đơn, mẫu 02/TNDN
TALLY = env['lfood.purchase.tally'].with_user(users['ketoanvien']).with_company(factory)
tally = TALLY.create({'date': date(2026, 11, 10), 'place': 'Xã Mỹ Hạnh, Tây Ninh', 'memo': 'Thu mua gạo lứt của nông dân',
                      'line_ids': [
                          (0, 0, {'date': date(2026, 11, 9), 'case': 'farm', 'seller_name': 'Nguyễn Văn A',
                                  'seller_id_number': '080190001234', 'seller_address': 'Xã Mỹ Hạnh, Tây Ninh',
                                  'name': 'Gạo lứt', 'quantity': 100, 'price_unit': 20_000, 'payment_method': 'cash'}),
                          (0, 0, {'date': date(2026, 11, 9), 'case': 'farm', 'seller_name': 'Trần Thị B',
                                  'seller_id_number': '080190005678', 'seller_address': 'Xã Mỹ Hạnh, Tây Ninh',
                                  'name': 'Đậu xanh', 'quantity': 50, 'price_unit': 30_000, 'payment_method': 'bank'}),
                          (0, 0, {'date': date(2026, 11, 9), 'case': 'farm', 'seller_name': 'Lê Văn C',
                                  'seller_id_number': '080190009999', 'seller_address': 'Xã Mỹ Hạnh, Tây Ninh',
                                  'name': 'Mè đen', 'quantity': 10, 'price_unit': 40_000, 'payment_method': 'cash'})]})
check('Bảng kê được cấp số BK và cộng tổng giá thanh toán', tally.name.startswith('BK') and tally.amount == 3_900_000,
      (tally.name, tally.amount))
l_a, l_b, l_c = tally.line_ids[0], tally.line_ids[1], tally.line_ids[2]
check('Trả tiền mặt 2 triệu trong ngày: vẫn được tính chi phí được trừ', l_a.deductible and l_c.deductible,
      (l_a.amount, l_a.deductible, l_c.amount, l_c.deductible))
check('Ngưỡng tiền mặt lấy từ tham số pháp lý theo TT 20/2026', tally.cash_limit() == 5_000_000, tally.cash_limit())
check('Căn cứ tham số ghi Thông tư 20/2026/TT-BTC',
      'Thông tư 20/2026' in ref('lfood_purchase.pv_tally_cash_limit').legal_ref)
l_a.write({'quantity': 300})
env.flush_all(); env.invalidate_all()
check('Tiền mặt 6 triệu trong ngày của một người bán: không được tính chi phí được trừ',
      not l_a.deductible and tally.amount_nondeductible == 6_000_000,
      (l_a.amount, l_a.deductible, tally.amount_nondeductible))
check('Chuyển khoản thì vẫn được trừ dù trên 5 triệu', l_b.deductible and l_b.amount == 1_500_000)
l_a.write({'payment_method': 'bank'})
env.flush_all(); env.invalidate_all()
check('Đổi sang không dùng tiền mặt thì được trừ trở lại', l_a.deductible and tally.amount_nondeductible == 0)
l_a.write({'payment_method': 'cash'})
env.flush_all(); env.invalidate_all()
tally.action_confirm()
check('Ký duyệt bảng kê', tally.state == 'confirmed' and tally.confirmed_by == users['ketoanvien'])
check('Nhật ký ghi rõ phần không được trừ do trả tiền mặt', Log.sudo().search_count(
    [('model', '=', 'lfood.purchase.tally'), ('res_id', '=', tally.id), ('summary', 'ilike', 'không đủ điều kiện')]) == 1)
try:
    tally.write({'memo': 'sửa sau khi ký'}); check('Không sửa bảng kê đã ký', False)
except UserError:
    check('Không sửa bảng kê đã ký', True)
html = tally.form_html
check('Mẫu in 02/TNDN đủ cột và ghi đúng căn cứ ban hành',
      'Mẫu số 02/TNDN' in html and 'Thông tư số 20/2026/TT-BTC' in html and 'Mã số định danh cá nhân' in html
      and 'Tổng giá thanh toán' in html and 'Nguyễn Văn A' in html, html[:80])
tally2 = TALLY.create({'date': date(2026, 11, 11), 'place': 'Xã Mỹ Hạnh, Tây Ninh',
                       'line_ids': [(0, 0, {'date': date(2026, 11, 11), 'case': 'scrap', 'seller_name': 'Phạm Văn D',
                                            'seller_id_number': ' ', 'seller_address': 'Tây Ninh', 'name': 'Phế liệu giấy',
                                            'quantity': 1, 'price_unit': 500_000})]})
try:
    tally2.action_confirm(); check('Chặn ký bảng kê thiếu mã số định danh người bán', False)
except UserError as err:
    check('Chặn ký bảng kê thiếu mã số định danh người bán', 'định danh' in str(err), str(err)[:70])

# ---- bảng điều hành ban giám đốc
LedgerReport = env['lfood.ledger.report'].with_user(users['ketoantruong']).with_company(factory)
dash = LedgerReport.create({'report': 'dashboard', 'company_id': factory.id,
                      'date_from': date(2026, 9, 1), 'date_to': date(2026, 11, 30)})
b02_same = LedgerReport.create({'report': 'b02', 'company_id': factory.id,
                          'date_from': date(2026, 9, 1), 'date_to': date(2026, 11, 30)})
vals_cur = b02_same._b02_values(date(2026, 9, 1), date(2026, 11, 30))
check('Bảng điều hành có đủ 5 khối: kinh doanh, tài chính, khoản mục, phải thu, phải trả',
      all(k in dash.html for k in ['Kết quả kinh doanh', 'Tình hình tài chính', 'khoản mục chi phí lớn nhất',
                                   'khách hàng còn nợ nhiều nhất', 'nhà cung cấp còn phải trả nhiều nhất']))
check('Doanh thu thuần trên bảng điều hành khớp B02 cùng kỳ',
      vnd(round(vals_cur['10'])) in dash.html, vnd(round(vals_cur['10'])))
check('Kỳ so sánh là kỳ liền trước cùng độ dài', '02/06/2026' in dash.html and '31/08/2026' in dash.html,
      dash.html[:400])
dash_gd = env['lfood.ledger.report'].with_user(users['giamdoc']).with_company(factory).create(
    {'report': 'dashboard', 'company_id': factory.id, 'date_from': date(2026, 1, 1), 'date_to': date(2026, 12, 31)})
check('Giám đốc xem được bảng điều hành', 'Tiền hiện có' in (dash_gd.html or ''))
try:
    env['lfood.ledger.report'].with_user(users['nhanvien']).create(
        {'report': 'dashboard', 'company_id': factory.id, 'date_from': date(2026, 1, 1), 'date_to': date(2026, 12, 31)}).html
    check('Nhân viên không xem bảng điều hành', False)
except AccessError:
    check('Nhân viên không xem bảng điều hành', True)

# ---- thuế TNDN: tạm nộp quý và quyết toán năm
PROV = env['lfood.cit.provisional'].with_user(users['ketoanvien']).with_company(factory)
FINAL = env['lfood.cit.finalization'].with_user(users['ketoanvien']).with_company(factory)
q3 = PROV.create({'year': 2026, 'quarter': '3'})
check('Tạm nộp quý: cấp số TNQ, kỳ 01/7 đến 30/9, hạn nộp 30/10',
      q3.name.startswith('TNQ') and q3.date_from == date(2026, 7, 1) and q3.date_to == date(2026, 9, 30)
      and q3.date_due == date(2026, 10, 30), (q3.name, q3.date_from, q3.date_to, q3.date_due))
check('Thuế suất chọn theo tổng doanh thu năm liền kề trước', q3.rate in (15, 17, 20), (q3.rate, q3.profit))
q3.write({'profit': 500_000_000, 'adjust': 0})
check('Thuế tạm nộp bằng lợi nhuận nhân thuế suất', q3.tax == round(500_000_000 * q3.rate / 100), (q3.tax, q3.rate))
try:
    q3.action_post(); check('Kế toán viên không ghi sổ thuế TNDN', False)
except (UserError, AccessError):
    check('Kế toán viên không ghi sổ thuế TNDN', True)
q3_kt = env['lfood.cit.provisional'].with_user(users['ketoantruong']).with_company(factory).browse(q3.id)
q3_kt.action_post()
m_q3 = Move._active_for(q3)
check('Tạm nộp ghi Nợ 82111 / Có 3334', m_q3 and {('82111', q3.tax, 0), ('3334', 0, q3.tax)} ==
      {(l.account_code, l.debit, l.credit) for l in m_q3.line_ids},
      m_q3 and [(l.account_code, l.debit, l.credit) for l in m_q3.line_ids])
try:
    q3.write({'profit': 1}); check('Không sửa chứng từ tạm nộp đã ghi sổ', False)
except UserError:
    check('Không sửa chứng từ tạm nộp đã ghi sổ', True)
env.cr.execute('SAVEPOINT cit_dup')
try:
    PROV.create({'year': 2026, 'quarter': '3'})
    env.flush_all()
    check('Mỗi quý chỉ một chứng từ tạm nộp', False)
except Exception as err:
    check('Mỗi quý chỉ một chứng từ tạm nộp', 'đã có chứng từ' in str(err) or 'unique' in str(err).lower(), str(err)[:60])
env.cr.execute('ROLLBACK TO SAVEPOINT cit_dup')
env.invalidate_all()

fin = FINAL.create({'year': 2026})
check('Quyết toán năm: cấp số QTN, kỳ 01/01 đến 31/12, hạn nộp 31/3 năm sau',
      fin.name.startswith('QTN') and fin.date_from == date(2026, 1, 1) and fin.date_to == date(2026, 12, 31)
      and fin.date_due == date(2027, 3, 31), (fin.name, fin.date_due))
check('Lợi nhuận kế toán lấy đúng chỉ tiêu 50 của B02 cùng kỳ',
      round(fin.accounting_profit) == round(LedgerReport.create(
          {'report': 'b02', 'company_id': factory.id, 'date_from': date(2026, 1, 1), 'date_to': date(2026, 12, 31)}
      )._b02_values(date(2026, 1, 1), date(2026, 12, 31))['50']), fin.accounting_profit)
fin.action_load()
tally_nondeduct = sum(env['lfood.purchase.tally'].sudo().search(
    [('company_id', '=', factory.id), ('state', '=', 'confirmed'),
     ('date', '>=', date(2026, 1, 1)), ('date', '<=', date(2026, 12, 31))]).mapped('amount_nondeductible'))
check('Lấy số gợi ý: đưa khoản thu mua tiền mặt không được trừ vào điều chỉnh tăng',
      tally_nondeduct and fin.adjust_increase == tally_nondeduct, (fin.adjust_increase, tally_nondeduct))
env['lfood.cit.adjust'].with_user(users['ketoanvien']).create(
    {'finalization_id': fin.id, 'kind': 'decrease', 'name': 'Thu nhập miễn thuế theo quy định', 'amount': 1_000_000})
env.flush_all(); env.invalidate_all()
check('Thu nhập chịu thuế bằng lợi nhuận cộng tăng trừ giảm',
      round(fin.taxable_income) == round(fin.accounting_profit + fin.adjust_increase - 1_000_000),
      (fin.taxable_income, fin.accounting_profit, fin.adjust_increase))
check('Thuế phải nộp bằng thu nhập tính thuế nhân thuế suất',
      fin.tax == round(fin.assessable_income * fin.rate / 100) and fin.assessable_income == max(0, fin.taxable_income - fin.loss_used),
      (fin.tax, fin.assessable_income, fin.rate))
check('Đã tạm nộp lấy từ các quý đã ghi sổ và tính được số còn phải nộp',
      fin.provisional_tax == q3.tax and fin.tax_remaining == fin.tax - q3.tax, (fin.provisional_tax, q3.tax))
expected_short = max(0, round(fin.tax * 80 / 100) - fin.provisional_tax)
check('Cảnh báo tạm nộp thiếu so với tỷ lệ tối thiểu 80%', fin.shortfall_amount == expected_short,
      (fin.shortfall_amount, expected_short))
check('Bảng tính thuế in được, ghi rõ nộp tờ khai 03/TNDN qua phần mềm cơ quan thuế',
      'Bảng tính thuế TNDN năm 2026' in fin.summary_html and '03/TNDN' in fin.summary_html)
fin_kt = env['lfood.cit.finalization'].with_user(users['ketoantruong']).with_company(factory).browse(fin.id)
fin_kt.action_post()
m_fin = Move._active_for(fin)
check('Quyết toán ghi bổ sung phần chênh lệch vào 82111 và 3334',
      m_fin and {'82111', '3334'} == set(m_fin.line_ids.mapped('account_code'))
      and round(sum(m_fin.line_ids.mapped('balance'))) == 0,
      m_fin and [(l.account_code, l.debit, l.credit) for l in m_fin.line_ids])
check('Nhật ký quyết toán ghi rõ số phải nộp và số đã tạm nộp', Log.sudo().search_count(
    [('model', '=', 'lfood.cit.finalization'), ('res_id', '=', fin.id), ('summary', 'ilike', 'đã tạm nộp')]) == 1)
check('Căn cứ thuế suất ghi Luật 67/2025/QH15',
      'Luật Thuế thu nhập doanh nghiệp 67/2025' in ref('lfood_cit.pv_cit_rate_std').legal_ref)
check('Tham số chuyển lỗ ghi rõ không quá 05 năm',
      '05 năm' in ref('lfood_cit.pv_cit_loss_years').legal_ref and ref('lfood_cit.pv_cit_loss_years').value == 5)
try:
    fin.write({'note': 'sửa sau khi ghi sổ'}); check('Không sửa bản quyết toán đã ghi sổ', False)
except UserError:
    check('Không sửa bản quyết toán đã ghi sổ', True)
fin_kt.action_cancel()
check('Hủy quyết toán: đảo bút toán, 3334 trả về số trước quyết toán',
      fin.state == 'cancel' and Move._active_for(fin) == Move.browse(), fin.state)

# ---- chi phí trả trước 242 và trích trước 335
PREPAID = env['lfood.prepaid'].with_user(users['ketoanvien']).with_company(factory)
ACCRUED = env['lfood.accrued'].with_user(users['ketoanvien']).with_company(factory)
pre = PREPAID.create({'label': 'Thuê kho trả trước 12 tháng', 'partner_id': supplier.id, 'date': date(2026, 7, 1),
                      'amount': 120_000_000, 'months': 12, 'date_start': date(2026, 7, 1),
                      'expense_account': '6427', 'cost_item_id': item_buy.id, 'post_initial': True,
                      'counterpart_account': '3311'})
check('Chi phí trả trước được cấp số TT', pre.name.startswith('TT'), pre.name)
debt_pre = net('331', partner_id=supplier.id)
pre.action_confirm()
check('Lập lịch 12 kỳ, mỗi kỳ 10 triệu, tổng đúng bằng số gốc',
      len(pre.line_ids) == 12 and sum(pre.line_ids.mapped('amount')) == 120_000_000
      and pre.line_ids[0].amount == 10_000_000, (len(pre.line_ids), sum(pre.line_ids.mapped('amount'))))
m_pre = Move._active_for(pre)
check('Ghi nhận ban đầu Nợ 242 / Có 3311', m_pre and {('242', 120_000_000, 0), ('3311', 0, 120_000_000)} ==
      {(l.account_code, l.debit, l.credit) for l in m_pre.line_ids},
      m_pre and [(l.account_code, l.debit, l.credit) for l in m_pre.line_ids])
check('Công nợ nhà cung cấp tăng đúng số trả trước', net('331', partner_id=supplier.id) == debt_pre - 120_000_000)
accr = ACCRUED.create({'label': 'Trích trước chi phí sửa chữa lớn', 'partner_id': supplier.id, 'date': date(2026, 7, 1),
                      'amount': 60_000_000, 'months': 6, 'date_start': date(2026, 7, 1), 'expense_account': '6427'})
accr.action_confirm()
check('Trích trước lập lịch 6 kỳ mỗi kỳ 10 triệu',
      len(accr.line_ids) == 6 and sum(accr.line_ids.mapped('amount')) == 60_000_000)
RUN = env['lfood.accrual.run'].with_user(users['ketoanvien']).with_company(factory)
run_w = RUN.create({'company_id': factory.id, 'date_to': date(2026, 9, 30)})
check('Đếm đúng số kỳ đến hạn tính tới 30/9', run_w.prepaid_count == 3 and run_w.accrued_count == 3
      and run_w.prepaid_amount == 30_000_000, (run_w.prepaid_count, run_w.accrued_count))
before_242, before_335 = net('242'), net('335')
run_w.action_run()
env.flush_all(); env.invalidate_all()
check('Ghi 3 kỳ: 242 giảm 30 triệu, 335 tăng 30 triệu',
      net('242') == before_242 - 30_000_000 and net('335') == before_335 - 30_000_000,
      (net('242') - before_242, net('335') - before_335))
check('Các kỳ đã ghi chuyển sang Đã ghi sổ, còn lại vẫn dự kiến',
      len(pre.line_ids.filtered(lambda l: l.state == 'posted')) == 3 and pre.allocated == 30_000_000
      and pre.remaining == 90_000_000, (pre.allocated, pre.remaining))
m_line = Move._active_for(pre.line_ids[0])
check('Phân bổ ghi Nợ 6427 / Có 242 theo từng kỳ',
      m_line and {('6427', 10_000_000, 0), ('242', 0, 10_000_000)} ==
      {(l.account_code, l.debit, l.credit) for l in m_line.line_ids},
      m_line and [(l.account_code, l.debit, l.credit) for l in m_line.line_ids])
check('Bút toán phân bổ gắn khoản mục chi phí',
      m_line and m_line.line_ids.filtered(lambda l: l.account_code == '6427').cost_item_id == item_buy)
try:
    pre.write({'amount': 1}); check('Không sửa chứng từ đã lập lịch phân bổ', False)
except UserError:
    check('Không sửa chứng từ đã lập lịch phân bổ', True)
try:
    env['lfood.prepaid'].with_user(users['ketoantruong']).with_company(factory).browse(pre.id).action_cancel()
    check('Không hủy khoản đã phân bổ một phần', False)
except UserError as err:
    check('Không hủy khoản đã phân bổ một phần', 'không hủy được' in str(err), str(err)[:60])
try:
    RUN.create({'company_id': factory.id, 'date_to': date(2026, 9, 30)}).action_run()
    check('Chạy lại cùng kỳ thì không ghi trùng', False)
except UserError as err:
    check('Chạy lại cùng kỳ thì không ghi trùng', 'Không có kỳ nào' in str(err), str(err)[:60])
accr.sudo().with_context(lfood_accrual_system=True).write({'actual_amount': 34_000_000})
env.invalidate_all()
acc_run = env['lfood.accrued'].with_user(users['ketoanvien']).with_company(factory).browse(accr.id)
acc_run.action_settle()
env.flush_all(); env.invalidate_all()
m_settle = Move.sudo().search([('source_model', '=', 'lfood.accrued'), ('source_id', '=', accr.id),
                               ('source_key', '=', 'settle'), ('state', '=', 'posted')], limit=1)
check('Quyết toán trích trước: thực tế 34 triệu, đã trích 30 triệu, ghi thêm 4 triệu vào 6427 và 335',
      accr.state == 'settled' and accr.difference == 4_000_000 and m_settle and
      {('6427', 4_000_000, 0), ('335', 0, 4_000_000)} == {(l.account_code, l.debit, l.credit) for l in m_settle.line_ids},
      (accr.difference, m_settle and [(l.account_code, l.debit, l.credit) for l in m_settle.line_ids]))
check('Nhật ký quyết toán trích trước ghi rõ đã trích và thực tế', Log.sudo().search_count(
    [('model', '=', 'lfood.accrued'), ('res_id', '=', accr.id), ('summary', 'ilike', 'chênh lệch')]) == 1)

# ---- trích lập dự phòng nợ phải thu khó đòi và giảm giá hàng tồn kho
PROVI = env['lfood.provision'].with_user(users['ketoanvien']).with_company(factory)
old_inv = SI.create({'partner_id': customer.id, 'date': date(2025, 6, 30), 'invoice_template': '1',
                     'invoice_symbol': 'C25TLF', 'invoice_number': '00000999', 'invoice_date': date(2025, 6, 30),
                     'due_date': date(2025, 7, 30),
                     'line_ids': [(0, 0, {'name': 'Bán hàng năm trước chưa thu', 'quantity': 1,
                                          'price_unit': 200_000_000, 'vat_rate_id': kct.id})]})
old_inv.action_post()
dp = PROVI.create({'kind': 'receivable', 'date': date(2026, 12, 31), 'memo': 'Dự phòng phải thu cuối năm 2026'})
dp.action_load()
line_old = dp.line_ids.filtered(lambda l: l.partner_id == customer and l.base_amount == 200_000_000)
check('Lấy được nợ quá hạn của hóa đơn cũ, quá hạn 17 tháng nên trích 50%',
      line_old and line_old.months_overdue == 17 and line_old.rate == 50
      and line_old.provision == 100_000_000, line_old and (line_old.months_overdue, line_old.rate, line_old.provision))
check('Hóa đơn trong hạn hoặc quá hạn dưới 6 tháng không bị trích',
      all(l.months_overdue >= 6 for l in dp.line_ids), dp.line_ids.mapped('months_overdue'))
check('Bậc tỷ lệ lấy từ tham số pháp lý, căn cứ Thông tư 48/2019',
      'Thông tư 48/2019' in ref('lfood_provision.pv_rate_2').legal_ref and ref('lfood_provision.pv_bracket_2').value == 12)
try:
    dp.action_post(); check('Kế toán viên không ghi sổ dự phòng', False)
except (UserError, AccessError):
    check('Kế toán viên không ghi sổ dự phòng', True)
dp_kt = env['lfood.provision'].with_user(users['ketoantruong']).with_company(factory).browse(dp.id)
before_2293, before_6426 = net('2293'), net('6426')
required = dp.required_amount
dp_kt.action_post()
env.flush_all(); env.invalidate_all()
check('Trích lập lần đầu: Nợ 6426 / Có 2293 đúng số phải trích',
      net('2293') == before_2293 - required and net('6426') == before_6426 + required,
      (required, net('2293') - before_2293, net('6426') - before_6426))
dp2 = PROVI.create({'kind': 'receivable', 'date': date(2026, 12, 31), 'memo': 'Trích lập lại cùng kỳ'})
dp2.action_load()
check('Chứng từ sau thấy số đã trích trên sổ nên chỉ ghi phần chênh lệch',
      dp2.existing_amount == required and dp2.adjust_amount == dp2.required_amount - required,
      (dp2.existing_amount, dp2.adjust_amount))
dp2.line_ids.filtered(lambda l: l.base_amount == 200_000_000).write({'provision': 40_000_000})
env.flush_all(); env.invalidate_all()
check('Giảm số phải trích thì chênh lệch âm, tức hoàn nhập', dp2.adjust_amount < 0, dp2.adjust_amount)
hoan = -dp2.adjust_amount
env['lfood.provision'].with_user(users['ketoantruong']).with_company(factory).browse(dp2.id).action_post()
env.flush_all(); env.invalidate_all()
check('Hoàn nhập ghi Nợ 2293 / Có 6426', net('2293') == before_2293 - required + hoan
      and net('6426') == before_6426 + required - hoan, (hoan, net('2293') - before_2293))
m_dp2 = Move._active_for(dp2)
check('Bút toán hoàn nhập cân và đúng hai tài khoản',
      m_dp2 and set(m_dp2.line_ids.mapped('account_code')) == {'2293', '6426'}
      and round(sum(m_dp2.line_ids.mapped('balance'))) == 0)
dpk = PROVI.create({'kind': 'inventory', 'date': date(2026, 12, 31), 'memo': 'Dự phòng giảm giá hàng tồn kho'})
dpk.action_load()
line_prod = dpk.line_ids.filtered(lambda l: l.product_id == prod)
check('Lấy hàng tồn kho theo giá gốc trên sổ, mặc định chưa trích',
      line_prod and line_prod.quantity > 0 and line_prod.provision == 0
      and line_prod.net_realisable == line_prod.unit_cost, line_prod and (line_prod.quantity, line_prod.unit_cost))
line_prod.write({'net_realisable': line_prod.unit_cost - 1_000})
env.flush_all(); env.invalidate_all()
check('Giá trị thuần thấp hơn giá gốc 1.000 đồng một đơn vị thì trích đúng số lượng nhân chênh lệch',
      line_prod.provision == round(line_prod.quantity * 1_000), (line_prod.provision, line_prod.quantity))
before_2294, before_632 = net('2294'), net('632')
need_k = dpk.required_amount
env['lfood.provision'].with_user(users['ketoantruong']).with_company(factory).browse(dpk.id).action_post()
env.flush_all(); env.invalidate_all()
check('Dự phòng giảm giá hàng tồn kho ghi Nợ 632 / Có 2294',
      net('2294') == before_2294 - need_k and net('632') == before_632 + need_k,
      (need_k, net('2294') - before_2294, net('632') - before_632))
check('Nhật ký ghi rõ số phải trích và số đã trích', Log.sudo().search_count(
    [('model', '=', 'lfood.provision'), ('res_id', '=', dpk.id), ('summary', 'ilike', 'phải trích')]) == 1)
try:
    dpk.write({'memo': 'sửa sau ghi sổ'}); check('Không sửa chứng từ dự phòng đã ghi sổ', False)
except UserError:
    check('Không sửa chứng từ dự phòng đã ghi sổ', True)

# ---- bù trừ công nợ đối tác vừa mua vừa bán
OFFSET = env['lfood.offset'].with_user(users['ketoanvien']).with_company(factory)
both = env['res.partner'].sudo().create({'name': 'Đối tác vừa mua vừa bán', 'is_company': True})
inv_both = SI.create({'partner_id': both.id, 'date': date(2026, 11, 20), 'invoice_template': '1',
                      'invoice_symbol': 'C26TLF', 'invoice_number': '00001234', 'invoice_date': date(2026, 11, 20),
                      'line_ids': [(0, 0, {'name': 'Bán hàng cho đối tác', 'quantity': 1,
                                           'price_unit': 50_000_000, 'vat_rate_id': kct.id})]})
inv_both.action_post()
buy_both = KV_Move.create({'journal': 'general', 'date': date(2026, 11, 21), 'memo': 'Mua dịch vụ của chính đối tác',
                           'line_ids': [(0, 0, {'account_id': acc('6427'), 'debit': 30_000_000}),
                                        (0, 0, {'account_id': acc('3311'), 'partner_id': both.id, 'credit': 30_000_000})]})
buy_both.action_post()
env.flush_all(); env.invalidate_all()
off = OFFSET.create({'company_id': factory.id, 'partner_id': both.id, 'date': date(2026, 11, 30), 'amount': 30_000_000})
check('Bù trừ đọc đúng phải thu, phải trả và mức tối đa',
      off.receivable == 50_000_000 and off.payable == 30_000_000 and off.max_amount == 30_000_000,
      (off.receivable, off.payable, off.max_amount))
check('Xem trước ghi rõ số còn lại sau bù trừ', 'Sau bù trừ' in (off.preview or ''))
off_over = OFFSET.create({'company_id': factory.id, 'partner_id': both.id, 'date': date(2026, 11, 30),
                          'amount': 40_000_000})
try:
    off_over.action_apply(); check('Chặn bù trừ quá số nhỏ hơn giữa phải thu và phải trả', False)
except UserError as err:
    check('Chặn bù trừ quá số nhỏ hơn giữa phải thu và phải trả', 'tối đa' in str(err), str(err)[:70])
recv_before, pay_before = net('131', partner_id=both.id), net('331', partner_id=both.id)
off.action_apply()
env.flush_all(); env.invalidate_all()
check('Bù trừ ghi Nợ 3311 / Có 1311 đúng 30 triệu theo từng đối tượng',
      net('131', partner_id=both.id) == recv_before - 30_000_000
      and net('331', partner_id=both.id) == pay_before + 30_000_000,
      (net('131', partner_id=both.id) - recv_before, net('331', partner_id=both.id) - pay_before))
check('Sau bù trừ đối tác hết phải trả, còn phải thu 20 triệu',
      net('331', partner_id=both.id) == 0 and net('131', partner_id=both.id) == 20_000_000,
      (net('331', partner_id=both.id), net('131', partner_id=both.id)))
check('Nhật ký bù trừ ghi rõ số phải thu và phải trả tại ngày bù trừ', Log.sudo().search_count(
    [('summary', 'ilike', 'Bù trừ công nợ Đối tác vừa mua vừa bán')]) == 1)
off_none = OFFSET.create({'company_id': factory.id, 'partner_id': both.id, 'date': date(2026, 11, 30),
                          'amount': 1_000_000})
try:
    off_none.action_apply(); check('Hết phải trả thì không bù trừ thêm được', False)
except UserError:
    check('Hết phải trả thì không bù trừ thêm được', True)

# ---- nhân sự: hợp đồng lao động, nghỉ phép, chấm công, nối bảng lương
from odoo.exceptions import ValidationError
EMP = env['lfood.employee'].with_user(users['ketoanvien']).with_company(factory)
CONTRACT = env['lfood.hr.contract'].with_user(users['ketoanvien']).with_company(factory)
LEAVE = env['lfood.hr.leave'].with_user(users['ketoanvien']).with_company(factory)
ATT = env['lfood.hr.attendance'].with_user(users['ketoanvien']).with_company(factory)
e_hr = EMP.create({'code': 'NVHR01', 'name': 'Nhân viên nhân sự thử', 'company_id': factory.id,
                   'date_start': date(2020, 1, 1), 'region': 'I', 'insurance_salary': 5_310_000})
c1 = CONTRACT.create({'employee_id': e_hr.id, 'kind': 'definite', 'date_start': date(2026, 1, 1),
                      'date_end': date(2029, 1, 1), 'salary': 10_400_000, 'insurance_salary': 10_400_000})
check('Hợp đồng được cấp số HDLD', c1.name.startswith('HDLD'), c1.name)
try:
    c1.action_activate(); check('Chặn hợp đồng xác định thời hạn quá 36 tháng', False)
except ValidationError as err:
    check('Chặn hợp đồng xác định thời hạn quá 36 tháng', '36 tháng' in str(err), str(err)[:70])
c1.write({'date_end': date(2028, 12, 31)})
c1.action_activate()
env.invalidate_all()
basic_line = e_hr.component_line_ids.filtered(lambda l: l.component_id == ref('lfood_payroll.comp_basic'))
check('Hợp đồng hiệu lực cập nhật lương chính và lương đóng bảo hiểm vào hồ sơ',
      c1.state == 'running' and e_hr.contract_id == c1 and basic_line.amount == 10_400_000
      and e_hr.insurance_salary == 10_400_000 and e_hr.contract_type == 'definite',
      (c1.state, basic_line.amount, e_hr.insurance_salary))
try:
    c1.write({'salary': 1}); check('Không sửa hợp đồng đã hiệu lực', False)
except UserError:
    check('Không sửa hợp đồng đã hiệu lực', True)
e_pro = EMP.create({'code': 'NVHR02', 'name': 'Nhân viên thử việc', 'company_id': factory.id, 'region': 'I'})
pro = CONTRACT.create({'employee_id': e_pro.id, 'kind': 'probation', 'probation_level': 'college',
                       'date_start': date(2026, 10, 1), 'date_end': date(2026, 12, 9),
                       'salary': 9_000_000, 'official_salary': 10_000_000})
try:
    pro.action_activate(); check('Chặn thử việc quá 60 ngày với công việc cần cao đẳng', False)
except ValidationError as err:
    check('Chặn thử việc quá 60 ngày với công việc cần cao đẳng', '60 ngày' in str(err), str(err)[:70])
pro.write({'date_end': date(2026, 11, 29), 'salary': 8_000_000})
try:
    pro.action_activate(); check('Chặn lương thử việc dưới 85% lương chính thức', False)
except ValidationError as err:
    check('Chặn lương thử việc dưới 85% lương chính thức', '85%' in str(err), str(err)[:70])
pro.write({'salary': 8_500_000})
pro.action_activate()
check('Thử việc 60 ngày, lương đúng 85% thì cho hiệu lực', pro.state == 'running')
check('Căn cứ hợp đồng và thử việc ghi Bộ luật Lao động 2019',
      'Điều 20' in ref('lfood_hr.pv_hd_36').legal_ref and 'Điều 26' in ref('lfood_hr.pv_tv_luong').legal_ref)

entitled, taken = e_hr._leave_balance(2026)
check('Phép năm 2026: vào làm từ 2020 nên 12 ngày cộng 1 ngày thâm niên', entitled == 13 and taken == 0,
      (entitled, taken))
lv1 = LEAVE.create({'employee_id': e_hr.id, 'kind': 'annual', 'date_from': date(2026, 10, 5),
                    'date_to': date(2026, 10, 7), 'days': 3, 'reason': 'Việc gia đình'})
try:
    lv1.action_approve(); check('Kế toán viên không duyệt đơn nghỉ', False)
except UserError:
    check('Kế toán viên không duyệt đơn nghỉ', True)
env['lfood.hr.leave'].with_user(users['ketoantruong']).with_company(factory).browse(lv1.id).action_approve()
env.invalidate_all()
check('Duyệt 3 ngày phép, còn lại 10 ngày', lv1.state == 'approved' and e_hr._leave_balance(2026) == (13, 3),
      e_hr._leave_balance(2026))
lv2 = LEAVE.create({'employee_id': e_hr.id, 'kind': 'annual', 'date_from': date(2026, 11, 2),
                    'date_to': date(2026, 11, 16), 'days': 11})
try:
    env['lfood.hr.leave'].with_user(users['giamdoc']).with_company(factory).browse(lv2.id).action_approve()
    check('Chặn duyệt phép vượt số ngày còn lại', False)
except UserError as err:
    check('Chặn duyệt phép vượt số ngày còn lại', 'còn 10 ngày' in str(err), str(err)[:70])
env.flush_all()
env.cr.execute('SAVEPOINT leave_days')
try:
    LEAVE.create({'employee_id': e_hr.id, 'kind': 'unpaid', 'date_from': date(2026, 10, 1),
                  'date_to': date(2026, 10, 2), 'days': 5})
    env.flush_all()
    check('Chặn số ngày nghỉ lớn hơn khoảng ngày của đơn', False)
except ValidationError:
    check('Chặn số ngày nghỉ lớn hơn khoảng ngày của đơn', True)
env.cr.execute('ROLLBACK TO SAVEPOINT leave_days')
env.invalidate_all()

ATT.create({'employee_id': e_hr.id, 'date': date(2026, 10, 1), 'hours_normal': 8, 'ot_normal': 2})
ATT.create({'employee_id': e_hr.id, 'date': date(2026, 10, 2), 'hours_normal': 8})
ATT.create({'employee_id': e_hr.id, 'date': date(2026, 10, 3), 'hours_normal': 0, 'ot_weekend': 8})
ATT.create({'employee_id': e_hr.id, 'date': date(2026, 10, 8), 'hours_normal': 8})
env.flush_all()
env.cr.execute('SAVEPOINT att_day')
try:
    ATT.create({'employee_id': e_hr.id, 'date': date(2026, 10, 9), 'hours_normal': 8, 'ot_normal': 5})
    env.flush_all()
    check('Chặn làm thêm quá 50% giờ bình thường trong ngày', False)
except ValidationError as err:
    check('Chặn làm thêm quá 50% giờ bình thường trong ngày', 'Điều 107' in str(err), str(err)[:70])
env.cr.execute('ROLLBACK TO SAVEPOINT att_day')
env.invalidate_all()
env.cr.execute('SAVEPOINT att_month')
try:
    for d in range(12, 20):
        ATT.create({'employee_id': e_hr.id, 'date': date(2026, 10, d), 'hours_normal': 8, 'ot_normal': 4})
        env.flush_all()
    check('Chặn tổng làm thêm trong tháng quá 40 giờ', False)
except ValidationError as err:
    check('Chặn tổng làm thêm trong tháng quá 40 giờ', 'tổng tháng' in str(err), str(err)[:80])
env.cr.execute('ROLLBACK TO SAVEPOINT att_month')
env.invalidate_all()
check('Chấm công bị chặn không lưu lại dòng nào', ATT.search_count([('employee_id', '=', e_hr.id)]) == 4,
      ATT.search_count([('employee_id', '=', e_hr.id)]))
try:
    env['lfood.hr.attendance'].with_user(users['nhanvien']).search([]).read(['date'])
    check('Nhân viên thường không xem bảng chấm công', False)
except AccessError:
    check('Nhân viên thường không xem bảng chấm công', True)

run_oct = env['lfood.payroll.run'].with_user(users['ketoanvien']).with_company(factory).create(
    {'company_id': factory.id, 'year': 2026, 'month': 10, 'standard_days': 26})
run_oct.action_load_employees()
slip_hr = run_oct.slip_ids.filtered(lambda s: s.employee_id == e_hr)
ot_line = slip_hr.line_ids.filtered(lambda l: l.component_id == ref('lfood_payroll.comp_ot'))
check('Ngày công lấy từ chấm công: 3 ngày làm việc cộng 3 ngày phép có lương',
      slip_hr.worked_days == 6, slip_hr.worked_days)
check('Tiền làm thêm: 50.000 đồng/giờ x (2 giờ x 150% + 8 giờ x 200%) = 950.000',
      ot_line and ot_line.amount == 950_000, ot_line and ot_line.amount)
slip_old = run_oct.slip_ids.filtered(lambda s: s.employee_id == e1)
check('Nhân viên chưa chấm công giữ ngày công chuẩn', slip_old.worked_days == 26, slip_old.worked_days)
check('Bảng lương tính lại thu nhập có cả tiền làm thêm',
      slip_hr.gross == round(10_400_000 * 6 / 26) + 950_000, (slip_hr.gross, round(10_400_000 * 6 / 26)))
comp_ot = ref('lfood_payroll.comp_ot')
check('Tiền làm thêm, làm đêm được miễn thuế TNCN từ kỳ tính thuế 2026, trước đó vẫn tính thuế',
      comp_ot.pit_exempt_code == 'TNCN_MIEN_LAM_THEM_BAN_DEM' and not comp_ot._is_taxable(date(2026, 10, 31))
      and comp_ot._is_taxable(date(2025, 12, 31)))
check('Thu nhập chịu thuế của phiếu lương không gồm 950.000 tiền làm thêm',
      slip_hr.taxable_income == slip_hr.gross - 950_000, (slip_hr.taxable_income, slip_hr.gross))
check('Căn cứ miễn thuế ghi Luật Thuế TNCN 109/2025/QH15',
      '109/2025' in ref('lfood_payroll.pv_pit_exempt_ot').legal_ref)
check('Có khoản tiền lương những ngày không nghỉ phép, cũng được miễn thuế',
      ref('lfood_payroll.comp_untaken_leave').pit_exempt_code == 'TNCN_MIEN_LAM_THEM_BAN_DEM')

# ---- chấm dứt hợp đồng, trợ cấp thôi việc
TERM = env['lfood.hr.termination'].with_user(users['ketoanvien']).with_company(factory)
term = TERM.create({'employee_id': e_hr.id, 'date_end': date(2026, 12, 31), 'kind': 'resign',
                    'reason': 'Người lao động đơn phương chấm dứt đúng thời hạn báo trước'})
check('Gợi ý thời gian làm việc thực tế 83 tháng và lương bình quân 6 tháng từ hợp đồng',
      term.months_worked == 83 and term.avg_salary == 10_400_000, (term.months_worked, term.avg_salary))
check('Gợi ý ngày phép chưa nghỉ để trả qua bảng lương cuối', term.leave_remaining == 10, term.leave_remaining)
term.write({'months_ui': 72})
check('Trừ 72 tháng đã đóng BHTN: tính 11 tháng, làm tròn thành 1 năm',
      term.months_counted == 11 and term.years_counted == 1, (term.months_counted, term.years_counted))
check('Trợ cấp thôi việc = 1 năm x 1/2 tháng lương = 5.200.000', term.amount == 5_200_000, term.amount)
term_red = TERM.create({'employee_id': e_hr.id, 'date_end': date(2026, 12, 31), 'kind': 'redundancy',
                        'reason': 'Tổ chức lại, không bố trí được việc làm', 'months_ui': 72})
check('Mất việc làm: 1 năm nhưng tối thiểu 2 tháng lương = 20.800.000', term_red.amount == 20_800_000,
      term_red.amount)
term_red.sudo().unlink()
term_short = TERM.create({'employee_id': e_pro.id, 'date_end': date(2026, 11, 29), 'kind': 'resign',
                          'reason': 'Kết thúc thử việc'})
check('Làm việc chưa đủ 12 tháng thì không có trợ cấp', term_short.amount == 0, term_short.amount)
term_short.sudo().unlink()
try:
    term.action_post(); check('Kế toán viên không ghi sổ chấm dứt hợp đồng', False)
except UserError:
    check('Kế toán viên không ghi sổ chấm dứt hợp đồng', True)
p334 = net('334', partner_id=e_hr.partner_id.id)
env['lfood.hr.termination'].with_user(users['ketoantruong']).with_company(factory).browse(term.id).action_post()
env.flush_all(); env.invalidate_all()
m_term = Move._active_for(term)
check('Ghi sổ trợ cấp Nợ chi phí lương của nhân viên / Có 334',
      m_term and {(e_hr.cost_account, 5_200_000, 0), ('334', 0, 5_200_000)} ==
      {(l.account_code, l.debit, l.credit) for l in m_term.line_ids}
      and net('334', partner_id=e_hr.partner_id.id) == p334 - 5_200_000,
      m_term and [(l.account_code, l.debit, l.credit) for l in m_term.line_ids])
check('Chấm dứt thì kết thúc hợp đồng và ghi ngày nghỉ việc',
      c1.state == 'closed' and e_hr.date_end == date(2026, 12, 31) and not e_hr.contract_id,
      (c1.state, e_hr.date_end))

# ---- kiểm kê kho theo đợt
COUNT = env['lfood.stock.count'].with_user(users['ketoanvien']).with_company(factory)
cnt = COUNT.create({'warehouse_id': wh_a.id, 'date': date(2026, 11, 30),
                    'members': 'Thủ kho A, Kế toán kho B, Quản đốc C'})
cnt.action_load()
l_prod = cnt.line_ids.filtered(lambda l: l.product_id == prod and l.lot_id == lot1)
l_nl = cnt.line_ids.filtered(lambda l: l.product_id == nl)[:1]
check('Đợt kiểm kê cấp số KK và chốt số sổ sách theo từng lô',
      cnt.name.startswith('KK') and l_prod and l_prod.book_qty == prod._position(wh_a, lot1)[0] and l_nl
      and all(l.real_qty == l.book_qty for l in cnt.line_ids), (cnt.name, l_prod.book_qty, prod._position(wh_a, lot1)))
lot1_all = lot1.qty_on_hand
book_l1 = l_prod.book_qty
l_prod.write({'real_qty': book_l1 - 5, 'note': 'Hũ vỡ'})
l_nl.write({'real_qty': l_nl.book_qty + 3, 'note': 'Cân thừa'})
env.flush_all(); env.invalidate_all()
check('Chênh lệch: thiếu 5 hũ, thừa 3 kg', l_prod.diff_qty == -5 and l_nl.diff_qty == 3
      and cnt.shortage_value > 0 and cnt.surplus_value > 0, (l_prod.diff_qty, l_nl.diff_qty))
check('Biên bản kiểm kê có đủ tổ kiểm kê, sổ sách, thực tế, chênh lệch',
      'BIÊN BẢN KIỂM KÊ' in cnt.report_html and 'Thủ kho A' in cnt.report_html and 'Thừa' in cnt.report_html)
try:
    cnt.action_approve(); check('Kế toán viên không duyệt kiểm kê', False)
except UserError:
    check('Kế toán viên không duyệt kiểm kê', True)
b1381, b3381 = net('1381'), net('3381')
env['lfood.stock.count'].with_user(users['ketoantruong']).with_company(factory).browse(cnt.id).action_approve()
env.flush_all(); env.invalidate_all()
pk_in = cnt.picking_ids.filtered(lambda p: p.kind == 'in')
pk_out = cnt.picking_ids.filtered(lambda p: p.kind == 'out')
check('Duyệt kiểm kê lập và ghi 2 phiếu mục đích Kiểm kê',
      cnt.state == 'done' and len(cnt.picking_ids) == 2 and set(cnt.picking_ids.mapped('state')) == {'done'}
      and set(cnt.picking_ids.mapped('purpose')) == {'count'}, cnt.picking_ids.mapped('state'))
check('Hàng thiếu ghi Nợ 1381 đúng giá trị phiếu xuất', net('1381') - b1381 == pk_out.amount
      and abs(pk_out.amount - cnt.shortage_value) <= 5, (net('1381') - b1381, pk_out.amount, cnt.shortage_value))
check('Hàng thừa ghi Có 3381 đúng giá trị phiếu nhập', b3381 - net('3381') == pk_in.amount
      and abs(pk_in.amount - cnt.surplus_value) <= 5, (b3381 - net('3381'), pk_in.amount, cnt.surplus_value))
check('Tồn lô L1 tại kho A giảm đúng 5 hũ, kho khác không đổi',
      prod._position(wh_a, lot1)[0] == book_l1 - 5 and lot1.qty_on_hand == lot1_all - 5,
      (prod._position(wh_a, lot1), lot1.qty_on_hand, lot1_all))
try:
    l_prod.write({'real_qty': 1}); check('Không sửa số đếm sau khi duyệt', False)
except UserError:
    check('Không sửa số đếm sau khi duyệt', True)
check('Nhật ký ghi duyệt kiểm kê kèm giá trị thừa thiếu', Log.sudo().search_count(
    [('model', '=', 'lfood.stock.count'), ('res_id', '=', cnt.id), ('summary', 'ilike', 'thừa')]) == 1)

# ---- ngoại tệ và đánh giá lại tỷ giá cuối kỳ
usd = ref('base.USD')
usd.sudo().write({'active': True})
fx_in = KV_Move.create({'journal': 'general', 'date': date(2026, 11, 20), 'memo': 'Nhận 1.000 USD',
                        'line_ids': [(0, 0, {'account_id': acc('112'), 'debit': 25_000_000,
                                             'currency_id': usd.id, 'amount_currency': 1_000}),
                                     (0, 0, {'account_id': acc('711'), 'credit': 25_000_000})]})
fx_in.action_post()
fx_pay = KV_Move.create({'journal': 'general', 'date': date(2026, 11, 20), 'memo': 'Nợ nhà cung cấp 2.000 USD',
                         'line_ids': [(0, 0, {'account_id': acc('6427'), 'debit': 50_000_000}),
                                      (0, 0, {'account_id': acc('3311'), 'partner_id': supplier.id, 'credit': 50_000_000,
                                              'currency_id': usd.id, 'amount_currency': -2_000})]})
fx_pay.action_post()
env.flush_all()
env.cr.execute('SAVEPOINT fx_sign')
try:
    KV_Move.create({'journal': 'general', 'date': date(2026, 11, 20), 'memo': 'sai chiều nguyên tệ',
                    'line_ids': [(0, 0, {'account_id': acc('112'), 'debit': 1_000, 'currency_id': usd.id,
                                         'amount_currency': -1}),
                                 (0, 0, {'account_id': acc('711'), 'credit': 1_000})]})
    env.flush_all()
    check('Chặn số nguyên tệ ngược chiều Nợ, Có', False)
except ValidationError:
    check('Chặn số nguyên tệ ngược chiều Nợ, Có', True)
env.cr.execute('ROLLBACK TO SAVEPOINT fx_sign')
env.invalidate_all()
FXR = env['lfood.fx.revaluation'].with_user(users['ketoanvien']).with_company(factory)
fx_norate = FXR.create({'date': date(2026, 11, 30), 'bank': 'Ngân hàng thử'})
try:
    fx_norate.action_load(); check('Chặn khi chưa nhập tỷ giá của ngoại tệ đang có số dư', False)
except UserError as err:
    check('Chặn khi chưa nhập tỷ giá của ngoại tệ đang có số dư', 'USD' in str(err), str(err)[:60])
fx_norate.sudo().unlink()
fxr = FXR.create({'date': date(2026, 11, 30), 'bank': 'Ngân hàng thử',
                  'rate_ids': [(0, 0, {'currency_id': usd.id, 'buy_rate': 25_100, 'sell_rate': 25_300})]})
check('Tỷ giá đánh giá lại là trung bình mua bán chuyển khoản', fxr.rate_ids.rate == 25_200, fxr.rate_ids.rate)
fxr.action_load()
l_bank = fxr.line_ids.filtered(lambda l: l.account_id.code == '112')
l_sup = fxr.line_ids.filtered(lambda l: l.account_id.code == '3311' and l.partner_id == supplier)
check('Tiền gửi 1.000 USD sổ 25.000.000, tỷ giá 25.200: lãi 200.000',
      l_bank.amount_currency == 1_000 and l_bank.book_value == 25_000_000 and l_bank.diff == 200_000,
      (l_bank.amount_currency, l_bank.book_value, l_bank.diff))
check('Phải trả 2.000 USD sổ 50.000.000, tỷ giá 25.200: lỗ 400.000',
      l_sup.amount_currency == -2_000 and l_sup.book_value == -50_000_000 and l_sup.diff == -400_000,
      (l_sup.amount_currency, l_sup.book_value, l_sup.diff))
check('Số thuần: lãi 200.000, lỗ 400.000, thuần lỗ 200.000',
      (fxr.gain, fxr.loss, fxr.net) == (200_000, 400_000, -200_000), (fxr.gain, fxr.loss, fxr.net))
try:
    fxr.action_post(); check('Kế toán viên không ghi sổ đánh giá lại ngoại tệ', False)
except UserError:
    check('Kế toán viên không ghi sổ đánh giá lại ngoại tệ', True)
b515, b635 = net('515'), net('635')
sup331 = net('331', partner_id=supplier.id)
env['lfood.fx.revaluation'].with_user(users['ketoantruong']).with_company(factory).browse(fxr.id).action_post()
env.flush_all(); env.invalidate_all()
check('Ghi số thuần vào 635, không ghi 515', net('635') == b635 + 200_000 and net('515') == b515,
      (net('635') - b635, net('515') - b515))
check('Phải trả nhà cung cấp tăng 400.000 theo đúng đối tượng', net('331', partner_id=supplier.id) == sup331 - 400_000,
      net('331', partner_id=supplier.id) - sup331)
fxr2 = FXR.create({'date': date(2026, 12, 31), 'bank': 'Ngân hàng thử',
                   'rate_ids': [(0, 0, {'currency_id': usd.id, 'buy_rate': 25_100, 'sell_rate': 25_300})]})
fxr2.action_load()
check('Đánh giá lần sau cùng tỷ giá thì không còn chênh lệch (đã cộng lần trước)',
      fxr2.line_ids and all(l.diff == 0 for l in fxr2.line_ids), fxr2.line_ids.mapped('diff'))
fxr2.sudo().unlink()
env['lfood.fx.revaluation'].with_user(users['ketoantruong']).with_company(factory).browse(fxr.id).action_cancel()
env.flush_all(); env.invalidate_all()
check('Hủy đánh giá lại: đảo bút toán, 635 trở về như trước', fxr.state == 'cancel' and net('635') == b635,
      (fxr.state, net('635') - b635))
pre_bank = env['lfood.prepaid'].with_user(users['ketoanvien']).with_company(factory).create(
    {'label': 'Trả trước bằng chuyển khoản', 'date': date(2026, 11, 1), 'amount': 12_000_000, 'months': 12,
     'date_start': date(2026, 11, 1), 'expense_account': '6427', 'post_initial': True, 'counterpart_account': '112'})
pre_bank.action_confirm()
check('Chi phí trả trước ghi nhận ban đầu Có 112 (TK cấp 1 theo Thông tư 99)',
      '112' in Move._active_for(pre_bank).line_ids.mapped('account_code'))

# ---- đơn bán hàng: bảng giá, hạn mức công nợ, lập hóa đơn từ đơn, giao theo hạn dùng tối thiểu
from datetime import timedelta
wh_so = WH.create({'code': 'KDB', 'name': 'Kho bán hàng', 'company_id': factory.id})
so_prod = env['lfood.product'].with_user(users['ketoanvien']).with_company(factory).create(
    {'code': 'SO01', 'name': 'Súp hũ gà', 'uom': 'hũ', 'kind': 'goods', 'vat_rate_id': vat8.id, 'company_id': factory.id})
PK.create({'kind': 'in', 'purpose': 'purchase', 'date': date(2026, 12, 1), 'warehouse_id': wh_so.id, 'partner_id': vendor2.id,
           'invoice_symbol': 'C26TAA', 'invoice_number': '0009901',
           'line_ids': [(0, 0, {'product_id': so_prod.id, 'lot_name': 'SA', 'expiry_date': date(2026, 12, 31),
                                'quantity': 50, 'price_unit': 10000}),
                        (0, 0, {'product_id': so_prod.id, 'lot_name': 'SB', 'expiry_date': date(2027, 6, 30),
                                'quantity': 100, 'price_unit': 10000})]}).action_done()
lot_sa = env['lfood.stock.lot'].search([('product_id', '=', so_prod.id), ('name', '=', 'SA')])
lot_sb = env['lfood.stock.lot'].search([('product_id', '=', so_prod.id), ('name', '=', 'SB')])
channel_mt = env['lfood.sale.channel'].with_user(users['ketoanvien']).create({'code': 'MT', 'name': 'Siêu thị'})
plist = env['lfood.pricelist'].with_user(users['ketoanvien']).with_company(factory).create(
    {'name': 'Giá siêu thị 2026', 'channel_id': channel_mt.id, 'date_from': date(2026, 1, 1), 'company_id': factory.id,
     'line_ids': [(0, 0, {'product_id': so_prod.id, 'min_qty': 1, 'price': 30000}),
                  (0, 0, {'product_id': so_prod.id, 'min_qty': 50, 'price': 28000, 'discount': 5})]})
cust_mt = env['res.partner'].create({'name': 'Siêu thị kiểm thử', 'is_company': True, 'lfood_channel_id': channel_mt.id,
                                     'lfood_pricelist_id': plist.id, 'lfood_credit_limit': 5_000_000,
                                     'lfood_payment_days': 30, 'lfood_min_shelf_days': 60})
SO = env['lfood.sale.order'].with_user(users['ketoanvien']).with_company(factory)
so1 = SO.create({'partner_id': cust_mt.id, 'date': date(2026, 12, 10), 'warehouse_id': wh_so.id, 'company_id': factory.id,
                 'line_ids': [(0, 0, {'product_id': so_prod.id, 'quantity': 60, 'vat_rate_id': vat8.id})]})
check('Đơn bán lấy kênh, bảng giá theo khách', so1.channel_id == channel_mt and so1.pricelist_id == plist)
so1.action_apply_prices()
check('Áp bảng giá theo bậc số lượng: 60 hũ giá 28.000, chiết khấu 5%, thành tiền 1.596.000, thuế 127.680',
      (so1.line_ids.price_unit, so1.line_ids.discount, so1.amount_untaxed, so1.amount_tax) == (28000, 5, 1_596_000, 127_680),
      (so1.line_ids.price_unit, so1.line_ids.discount, so1.amount_untaxed, so1.amount_tax))
so1.action_confirm()
check('Đơn trong hạn mức công nợ: xác nhận ngay', so1.state == 'confirmed', so1.state)
try:
    so1.line_ids.write({'quantity': 70}); check('Không sửa dòng đơn đã xác nhận', False)
except UserError:
    check('Không sửa dòng đơn đã xác nhận', True)
act = so1.action_create_invoice()
inv_so = SI.browse(act['res_id'])
check('Hóa đơn nháp từ đơn: 60 hũ đơn giá sau chiết khấu 26.600, hạn thanh toán sau 30 ngày',
      inv_so.state == 'draft' and inv_so.line_ids.quantity == 60 and inv_so.line_ids.price_unit == 26600
      and inv_so.due_date == inv_so.date + timedelta(days=30) and inv_so.warehouse_id == wh_so,
      (inv_so.line_ids.quantity, inv_so.line_ids.price_unit, inv_so.due_date))
try:
    so1.action_create_invoice(); check('Chặn lập hóa đơn thứ hai khi còn hóa đơn nháp', False)
except UserError:
    check('Chặn lập hóa đơn thứ hai khi còn hóa đơn nháp', True)
inv_so.write({'date': date(2026, 12, 10), 'invoice_date': date(2026, 12, 10), 'due_date': date(2027, 1, 9),
              'invoice_template': '1', 'invoice_symbol': 'C26TLF', 'invoice_number': '00009001'})
inv_so.line_ids.write({'quantity': 40})
inv_so.action_post()
env.flush_all(); env.invalidate_all()
check('Giao 40 hũ: bỏ lô SA còn hạn dưới 60 ngày, lấy lô SB',
      so_prod._position(wh_so, lot_sa)[0] == 50 and so_prod._position(wh_so, lot_sb)[0] == 60,
      (so_prod._position(wh_so, lot_sa)[0], so_prod._position(wh_so, lot_sb)[0]))
check('Đơn còn 20 hũ chưa lập hóa đơn, vẫn ở trạng thái đã xác nhận',
      so1.line_ids.qty_invoiced == 40 and so1.line_ids.qty_to_invoice == 20 and so1.state == 'confirmed',
      (so1.line_ids.qty_invoiced, so1.line_ids.qty_to_invoice, so1.state))
try:
    so1.action_cancel(); check('Không hủy đơn đã có hóa đơn ghi sổ', False)
except UserError:
    check('Không hủy đơn đã có hóa đơn ghi sổ', True)
so2 = SO.create({'partner_id': cust_mt.id, 'date': date(2026, 12, 11), 'warehouse_id': wh_so.id, 'company_id': factory.id,
                 'line_ids': [(0, 0, {'product_id': so_prod.id, 'quantity': 120, 'vat_rate_id': vat8.id})]})
so2.action_apply_prices()
so2.action_confirm()
recv, pend = so2._exposure()
check('Kiểm tra hạn mức: công nợ 1.149.120 + đơn mở 574.560 + đơn này 3.447.360 vượt 5.000.000 thì chờ duyệt',
      so2.state == 'waiting' and recv == 1_149_120 and pend == 574_560 and so2.amount_total == 3_447_360,
      (so2.state, recv, pend, so2.amount_total))
try:
    so2.action_approve_credit(); check('Kế toán viên không duyệt vượt hạn mức', False)
except UserError:
    check('Kế toán viên không duyệt vượt hạn mức', True)
env['lfood.sale.order'].with_user(users['giamdoc']).with_company(factory).browse(so2.id).action_approve_credit()
check('Giám đốc duyệt vượt hạn mức: đơn được xác nhận, ghi người duyệt',
      so2.state == 'confirmed' and so2.approved_by == users['giamdoc'], (so2.state, so2.approved_by.login))
check('Nhật ký ghi sự kiện vượt hạn mức', env['lfood.audit.log'].sudo().search_count(
    [('model', '=', 'lfood.sale.order'), ('res_id', '=', so2.id), ('summary', 'ilike', 'hạn mức')]) >= 2)
act = so1.action_create_invoice()
inv_so2 = SI.browse(act['res_id'])
inv_so2.write({'date': date(2026, 12, 12), 'invoice_date': date(2026, 12, 12),
               'invoice_template': '1', 'invoice_symbol': 'C26TLF', 'invoice_number': '00009002'})
inv_so2.line_ids.write({'quantity': 30})
env.flush_all()
env.cr.execute('SAVEPOINT so_over')
try:
    inv_so2.action_post(); check('Chặn lập hóa đơn vượt số lượng còn lại của đơn', False)
except UserError:
    check('Chặn lập hóa đơn vượt số lượng còn lại của đơn', True)
env.cr.execute('ROLLBACK TO SAVEPOINT so_over')
env.clear()
inv_so2.line_ids.write({'quantity': 20})
inv_so2.action_post()
env.flush_all(); env.invalidate_all()
check('Lập đủ hóa đơn: đơn chuyển sang Đã lập đủ hóa đơn', so1.state == 'done' and so1.invoice_count == 2, (so1.state, so1.invoice_count))
inv_short = SI.create({'partner_id': cust_mt.id, 'date': date(2026, 12, 13), 'invoice_template': '1', 'invoice_symbol': 'C26TLF',
                       'invoice_number': '00009003', 'warehouse_id': wh_so.id,
                       'line_ids': [(0, 0, {'product_id': so_prod.id, 'name': 'Súp hũ gà', 'quantity': 60,
                                            'price_unit': 30000, 'vat_rate_id': vat8.id})]})
env.flush_all()
env.cr.execute('SAVEPOINT so_shelf')
try:
    inv_short.action_post(); check('Không đủ lô còn hạn theo yêu cầu của khách thì chặn xuất (lô SA không được dùng)', False)
except UserError:
    check('Không đủ lô còn hạn theo yêu cầu của khách thì chặn xuất (lô SA không được dùng)', True)
env.cr.execute('ROLLBACK TO SAVEPOINT so_shelf')
env.clear()
inv_short.sudo().unlink()
so2.action_cancel()
check('Hủy đơn chưa lập hóa đơn', so2.state == 'cancel')

# ---- khuyến mại: hạn mức 50%, thông báo Sở Công Thương, hàng tặng trên đơn, xuất hàng mẫu
gift_prod = env['lfood.product'].with_user(users['ketoanvien']).with_company(factory).create(
    {'code': 'KM01', 'name': 'Muỗng ăn cháo', 'uom': 'cái', 'kind': 'goods', 'vat_rate_id': vat8.id, 'company_id': factory.id})
PK.create({'kind': 'in', 'purpose': 'purchase', 'date': date(2026, 12, 1), 'warehouse_id': wh_so.id, 'partner_id': vendor2.id,
           'invoice_symbol': 'C26TAA', 'invoice_number': '0009950',
           'line_ids': [(0, 0, {'product_id': gift_prod.id, 'lot_name': 'M1', 'expiry_date': date(2029, 12, 31),
                                'quantity': 100, 'price_unit': 5000})]}).action_done()
PR = env['lfood.promotion'].with_user(users['ketoanvien']).with_company(factory)
pr_gift = PR.create({'title': 'Mua 3 hũ tặng muỗng', 'kind': 'gift', 'date_from': date(2026, 12, 14), 'date_to': date(2026, 12, 31),
                     'company_id': factory.id,
                     'line_ids': [(0, 0, {'product_id': so_prod.id, 'price_before': 30000, 'buy_qty': 1,
                                          'gift_product_id': gift_prod.id, 'gift_price_before': 20000, 'gift_qty': 1})]})
check('Tỷ lệ hàng tặng: muỗng 20.000 cho 1 hũ 30.000 = 66,67%', pr_gift.line_ids.ratio == 66.67, pr_gift.line_ids.ratio)
try:
    pr_gift.action_activate(); check('Chặn áp dụng khi thiếu thông báo và vượt hạn mức 50%', False)
except UserError as err:
    check('Chặn áp dụng khi thiếu thông báo và vượt hạn mức 50%', 'Sở Công Thương' in str(err) and 'vượt hạn mức 50' in str(err), str(err)[:120])
pr_gift.line_ids.write({'buy_qty': 3})
pr_gift.write({'notice_ref': 'TBKM-001', 'notice_date': date(2026, 12, 10)})
try:
    pr_gift.action_activate(); check('Chặn thông báo nộp chưa đủ 3 ngày làm việc trước ngày bắt đầu', False)
except UserError as err:
    check('Chặn thông báo nộp chưa đủ 3 ngày làm việc trước ngày bắt đầu', '3 ngày làm việc' in str(err), str(err)[:80])
pr_gift.write({'notice_date': date(2026, 12, 8)})
pr_gift.action_activate()
check('Mua 3 tặng 1 (22,22%), thông báo trước 3 ngày làm việc: áp dụng được',
      pr_gift.state == 'active' and pr_gift.line_ids.ratio == 22.22, (pr_gift.state, pr_gift.line_ids.ratio))
try:
    pr_gift.write({'date_to': date(2027, 1, 31)}); check('Không sửa chương trình đang áp dụng', False)
except UserError:
    check('Không sửa chương trình đang áp dụng', True)
pr_disc = PR.create({'title': 'Giảm giá siêu thị', 'kind': 'discount', 'channel_id': channel_mt.id, 'company_id': factory.id,
                     'date_from': date(2026, 12, 14), 'date_to': date(2026, 12, 31),
                     'line_ids': [(0, 0, {'product_id': so_prod.id, 'price_before': 30000, 'discount': 60})]})
try:
    pr_disc.action_activate(); check('Chặn giảm giá quá 50%', False)
except UserError as err:
    check('Chặn giảm giá quá 50%', '60' in str(err), str(err)[:80])
pr_disc.line_ids.write({'discount': 10})
pr_disc.action_activate()
check('Giảm giá không cần thông báo Sở Công Thương', pr_disc.state == 'active' and not pr_disc.needs_notice)
so3 = SO.create({'partner_id': cust_mt.id, 'date': date(2026, 12, 14), 'warehouse_id': wh_so.id, 'company_id': factory.id,
                 'line_ids': [(0, 0, {'product_id': so_prod.id, 'quantity': 7, 'vat_rate_id': vat8.id})]})
so3.action_apply_promotions()
so3.action_apply_promotions()
g_line = so3.line_ids.filtered('is_promo_gift')
m_line = so3.line_ids - g_line
check('Áp khuyến mại (bấm 2 lần): giảm 10%, mua 7 tặng 2 muỗng giá 0, không nhân đôi',
      len(g_line) == 1 and g_line.product_id == gift_prod and g_line.quantity == 2 and g_line.amount == 0
      and m_line.discount == 10 and m_line.promotion_id == pr_disc,
      [(l.product_id.code, l.quantity, l.price_unit, l.discount) for l in so3.line_ids])
check('Tiền hàng 7 x 27.000 = 189.000, thuế 15.120 (hàng tặng giá tính thuế 0)',
      (so3.amount_untaxed, so3.amount_tax) == (189_000, 15_120), (so3.amount_untaxed, so3.amount_tax))
env.flush_all()
env.cr.execute('SAVEPOINT promo_price')
try:
    g_line.write({'price_unit': 1000}); env.flush_all(); check('Hàng tặng không được có đơn giá', False)
except ValidationError:
    check('Hàng tặng không được có đơn giá', True)
env.cr.execute('ROLLBACK TO SAVEPOINT promo_price')
env.clear()
cust_plain = env['res.partner'].create({'name': 'Khách lẻ kiểm thử khuyến mại'})
so4 = SO.create({'partner_id': cust_plain.id, 'date': date(2026, 12, 14), 'warehouse_id': wh_so.id, 'company_id': factory.id,
                 'line_ids': [(0, 0, {'product_id': so_prod.id, 'quantity': 3, 'price_unit': 30000, 'vat_rate_id': vat8.id})]})
so4.action_apply_promotions()
check('Khách ngoài kênh siêu thị: không giảm giá, vẫn được tặng theo chương trình chung',
      so4.line_ids.filtered(lambda l: not l.is_promo_gift).discount == 0 and sum(so4.line_ids.filtered('is_promo_gift').mapped('quantity')) == 1)
so4.action_cancel()
so3.action_confirm()
inv_km = SI.browse(so3.action_create_invoice()['res_id'])
g_inv = inv_km.line_ids.filtered(lambda l: l.product_id == gift_prod)
check('Hóa đơn ghi hàng tặng: tên có chữ hàng khuyến mại, thành tiền 0, thuế 0',
      'hàng khuyến mại' in g_inv.name and g_inv.amount == 0 and g_inv.tax == 0 and g_inv.quantity == 2, (g_inv.name, g_inv.amount))
inv_km.write({'date': date(2026, 12, 14), 'invoice_date': date(2026, 12, 14),
              'invoice_template': '1', 'invoice_symbol': 'C26TLF', 'invoice_number': '00009010'})
inv_km.action_post()
env.flush_all(); env.invalidate_all()
km_pick = inv_km.picking_ids
check('Xuất kho cả hàng tặng cùng hàng bán, giá vốn muỗng 10.000 vào 632',
      km_pick.state == 'done' and gift_prod.qty_on_hand == 98 and
      sum(km_pick.line_ids.filtered(lambda l: l.product_id == gift_prod).mapped('cost')) == 10_000
      and {l.account_code for l in Move._active_for(km_pick).line_ids} == {'632', '156'},
      (km_pick.state, gift_prod.qty_on_hand))
pr_sample = PR.create({'title': 'Phát muỗng dùng thử', 'kind': 'sample', 'company_id': factory.id,
                       'date_from': date(2026, 12, 15), 'date_to': date(2026, 12, 20),
                       'line_ids': [(0, 0, {'product_id': gift_prod.id, 'gift_qty': 5})]})
pr_sample.action_activate()
act = pr_sample.action_issue()
check('Nút xuất kho hàng mẫu điền sẵn nội dung Xuất khuyến mại', act['context']['default_purpose'] == 'promotion')
try:
    PK.create({'kind': 'out', 'purpose': 'promotion', 'date': date(2026, 12, 15), 'warehouse_id': wh_so.id,
               'line_ids': [(0, 0, {'product_id': gift_prod.id, 'quantity': 5})]}).action_done()
    check('Phiếu xuất khuyến mại phải chọn chương trình', False)
except UserError:
    check('Phiếu xuất khuyến mại phải chọn chương trình', True)
try:
    PK.create({'kind': 'out', 'purpose': 'promotion', 'date': date(2026, 12, 25), 'warehouse_id': wh_so.id,
               'promotion_id': pr_sample.id, 'line_ids': [(0, 0, {'product_id': gift_prod.id, 'quantity': 5})]}).action_done()
    check('Chặn xuất ngoài thời gian chương trình', False)
except UserError:
    check('Chặn xuất ngoài thời gian chương trình', True)
p_sample = PK.create({'kind': 'out', 'purpose': 'promotion', 'date': date(2026, 12, 15), 'warehouse_id': wh_so.id,
                      'promotion_id': pr_sample.id, 'line_ids': [(0, 0, {'product_id': gift_prod.id, 'quantity': 5})]})
p_sample.action_done()
m_sample = Move._active_for(p_sample)
check('Xuất hàng mẫu: Nợ 6418 / Có 156 giá vốn 25.000',
      m_sample and {(l.account_code, l.debit, l.credit) for l in m_sample.line_ids} == {('6418', 25_000, 0), ('156', 0, 25_000)},
      m_sample and [(l.account_code, l.debit, l.credit) for l in m_sample.line_ids])
pr_gift.action_close()
so5 = SO.create({'partner_id': cust_plain.id, 'date': date(2026, 12, 16), 'warehouse_id': wh_so.id, 'company_id': factory.id,
                 'line_ids': [(0, 0, {'product_id': so_prod.id, 'quantity': 3, 'price_unit': 30000, 'vat_rate_id': vat8.id})]})
so5.action_apply_promotions()
check('Chương trình đã kết thúc không còn áp dụng', pr_gift.state == 'closed' and not so5.line_ids.filtered('is_promo_gift'))
so5.action_cancel()

# ---- kiểm soát kho: cách ly lô, hủy hàng, tồn tối thiểu
wh_kc = WH.create({'code': 'KKC', 'name': 'Kho kiểm soát', 'company_id': factory.id})
kc_prod = env['lfood.product'].with_user(users['ketoanvien']).with_company(factory).create(
    {'code': 'KC01', 'name': 'Bánh quy bơ', 'uom': 'hộp', 'kind': 'goods', 'vat_rate_id': vat8.id, 'company_id': factory.id,
     'min_qty': 50, 'max_qty': 100})
PK.create({'kind': 'in', 'purpose': 'purchase', 'date': date(2026, 12, 1), 'warehouse_id': wh_kc.id, 'partner_id': vendor2.id,
           'invoice_symbol': 'C26TAA', 'invoice_number': '0009970',
           'line_ids': [(0, 0, {'product_id': kc_prod.id, 'lot_name': 'K1', 'expiry_date': date(2026, 12, 20),
                                'quantity': 20, 'price_unit': 8000}),
                        (0, 0, {'product_id': kc_prod.id, 'lot_name': 'K2', 'expiry_date': date(2027, 6, 30),
                                'quantity': 20, 'price_unit': 8000})]}).action_done()
Lot = env['lfood.stock.lot'].with_user(users['ketoanvien'])
k1 = Lot.search([('product_id', '=', kc_prod.id), ('name', '=', 'K1')])
k2 = Lot.search([('product_id', '=', kc_prod.id), ('name', '=', 'K2')])
wiz = env['lfood.stock.hold.wizard'].with_user(users['ketoanvien']).create(
    {'lot_ids': [(6, 0, k2.ids)], 'reason': 'Kiểm nghiệm vi sinh không đạt'})
wiz.action_apply()
check('Cách ly lô K2 ghi lý do, người cách ly', k2.hold and k2.hold_by == users['ketoanvien'] and 'vi sinh' in k2.hold_reason)
try:
    PK.create({'kind': 'out', 'purpose': 'internal', 'date': date(2026, 12, 10), 'warehouse_id': wh_kc.id,
               'line_ids': [(0, 0, {'product_id': kc_prod.id, 'quantity': 25})]}).action_done()
    check('Xuất tự động bỏ qua lô cách ly nên không đủ 25 hộp', False)
except UserError:
    check('Xuất tự động bỏ qua lô cách ly nên không đủ 25 hộp', True)
try:
    PK.create({'kind': 'out', 'purpose': 'internal', 'date': date(2026, 12, 10), 'warehouse_id': wh_kc.id,
               'line_ids': [(0, 0, {'product_id': kc_prod.id, 'lot_id': k2.id, 'quantity': 1})]}).action_done()
    check('Chặn chọn tay lô cách ly để xuất dùng', False)
except UserError as err:
    check('Chặn chọn tay lô cách ly để xuất dùng', 'cách ly' in str(err), str(err)[:60])
try:
    k2.action_release(); check('Kế toán viên không giải phóng lô cách ly', False)
except UserError:
    check('Kế toán viên không giải phóng lô cách ly', True)
env['lfood.stock.lot'].with_user(users['ketoantruong']).browse(k2.id).action_release()
check('Kế toán trưởng giải phóng lô, nhật ký ghi lại', not k2.hold and env['lfood.audit.log'].sudo().search_count(
    [('model', '=', 'lfood.stock.lot'), ('res_id', '=', k2.id)]) >= 2)
p_kc = PK.create({'kind': 'out', 'purpose': 'internal', 'date': date(2026, 12, 10), 'warehouse_id': wh_kc.id,
                  'line_ids': [(0, 0, {'product_id': kc_prod.id, 'quantity': 5})]})
p_kc.action_done()
check('Xuất dùng 5 hộp lấy lô K1 hết hạn trước', kc_prod._position(wh_kc, k1)[0] == 15, kc_prod._position(wh_kc, k1)[0])
k2.action_hold('Bao bì móp méo')
DSP = env['lfood.stock.disposal'].with_user(users['ketoanvien']).with_company(factory)
dsp = DSP.create({'date': date(2026, 12, 21), 'warehouse_id': wh_kc.id, 'company_id': factory.id, 'reason': 'expired'})
dsp.action_load_holds()
check('Lấy lô hết hạn (K1 15 hộp) và lô cách ly (K2 20 hộp)',
      sorted((l.lot_id.name, l.quantity) for l in dsp.line_ids) == [('K1', 15), ('K2', 20)],
      [(l.lot_id.name, l.quantity) for l in dsp.line_ids])
dsp.line_ids.filtered(lambda l: l.lot_id == k2).write({'quantity': 5})
check('Cảnh báo thiếu hồ sơ theo Thông tư 20/2026', 'quyết định hủy' in dsp.missing_docs and 'hội đồng' in dsp.missing_docs,
      dsp.missing_docs)
DIR = env['lfood.stock.disposal'].with_user(users['giamdoc']).with_company(factory)
try:
    DIR.browse(dsp.id).action_approve(); check('Chặn duyệt hủy khi thiếu hồ sơ', False)
except UserError:
    check('Chặn duyệt hủy khi thiếu hồ sơ', True)
dsp.write({'decision_ref': '15/QĐ-LF', 'decision_date': date(2026, 12, 20), 'committee_ref': '14/QĐ-LF',
           'members': 'Giám đốc - Chủ tịch hội đồng\nKế toán trưởng\nThủ kho',
           'compensation': 20_000, 'compensation_partner_id': cust_plain.id})
try:
    dsp.action_approve(); check('Kế toán viên không duyệt hủy hàng', False)
except UserError:
    check('Kế toán viên không duyệt hủy hàng', True)
DIR.browse(dsp.id).action_approve()
check('Giám đốc duyệt hủy', dsp.state == 'approved' and dsp.approved_by == users['giamdoc'])
try:
    dsp.write({'compensation': 0}); check('Không sửa biên bản đã duyệt', False)
except UserError:
    check('Không sửa biên bản đã duyệt', True)
try:
    PK.create({'kind': 'out', 'purpose': 'disposal', 'date': date(2026, 12, 21), 'warehouse_id': wh_kc.id,
               'line_ids': [(0, 0, {'product_id': kc_prod.id, 'lot_id': k1.id, 'quantity': 1})]}).action_done()
    check('Chặn phiếu xuất hủy không có biên bản', False)
except UserError:
    check('Chặn phiếu xuất hủy không có biên bản', True)
b632, b1388 = net('632'), net('1388', partner_id=cust_plain.id)
dsp.action_post()
env.flush_all(); env.invalidate_all()
check('Xuất hủy 20 hộp: giá trị 160.000, lô K1 hết, K2 còn 15',
      dsp.state == 'done' and dsp.amount == 160_000 and kc_prod._position(wh_kc, k1)[0] == 0
      and kc_prod._position(wh_kc, k2)[0] == 15, (dsp.state, dsp.amount))
check('Hạch toán: Nợ 632 160.000, bồi thường Nợ 1388 / Có 632 20.000',
      net('632') - b632 == 140_000 and net('1388', partner_id=cust_plain.id) - b1388 == 20_000
      and {l.account_code for l in Move._active_for(dsp.picking_id).line_ids} == {'632', '156'},
      (net('632') - b632, net('1388', partner_id=cust_plain.id) - b1388))
check('Biên bản in có căn cứ quyết định, thành viên, lô hủy',
      'BIÊN BẢN' in dsp.report_html and '15/QĐ-LF' in dsp.report_html and 'Thủ kho' in dsp.report_html and 'K1' in dsp.report_html)
reo = env['lfood.stock.reorder'].with_user(users['ketoanvien']).with_company(factory).create({'company_id': factory.id})
reo.action_compute()
r_line = reo.line_ids.filtered(lambda l: l.product_id == kc_prod)
check('Đề xuất đặt hàng: tồn 15 dưới mức 50, mua bù lên tối đa 100 = 85',
      r_line.on_hand == 15 and r_line.quantity == 85, (r_line.on_hand, r_line.quantity))
act = reo.action_make_request()
req_kc = env['lfood.purchase.request'].browse(act['res_id'])
check('Lập yêu cầu mua từ đề xuất', req_kc.line_ids.filtered(lambda l: l.product_id == kc_prod).quantity == 85)

# ---- nhắc hạn
REM = env['lfood.reminder']
REM._cron_refresh(today=date(2026, 11, 10))
env.flush_all()
rem_f = REM.with_user(users['ketoanvien']).search([('company_id', '=', factory.id), ('state', '=', 'open')])
check('Nhắc hợp đồng thử việc hết hạn 29/11, không nhắc hợp đồng đến 2028',
      rem_f.filtered(lambda r: r.key == 'hdld-%s-2026-11-29' % pro.id) and not rem_f.filtered(lambda r: r.res_id == c1.id and r.category == 'hr'),
      rem_f.filtered(lambda r: r.category == 'hr').mapped('title'))
vat_rem = rem_f.filtered(lambda r: r.key.startswith('vat-%s-' % factory.id))
oct_done = VR.sudo().search_count([('company_id', '=', factory.id), ('state', '=', 'confirmed'), ('date_to', '=', date(2026, 10, 31))]) \
    if factory.lfood_vat_period == 'month' else 1
check('Nhắc tờ khai thuế GTGT kỳ trước chưa xác nhận, hạn lấy từ phân hệ thuế',
      bool(vat_rem) != bool(oct_done) and (not vat_rem or vat_rem.due_date in (date(2026, 11, 20), date(2026, 10, 31))),
      (vat_rem.mapped('title'), vat_rem.mapped('due_date'), oct_done))
q3 = env['lfood.cit.provisional'].sudo().search([('company_id', '=', factory.id), ('year', '=', 2026), ('quarter', '=', '3')])
cit_rem = rem_f.filtered(lambda r: r.key == 'cit-%s-2026-3' % factory.id)
check('Nhắc tạm nộp TNDN quý 3 khi chưa ghi sổ, hạn 30/10',
      (q3.state == 'posted' and not cit_rem) or (q3.state != 'posted' and cit_rem.due_date == date(2026, 10, 30)),
      (q3.state, cit_rem.mapped('due_date')))
REM._cron_refresh(today=date(2026, 12, 22))
env.flush_all()
lot_rem = REM.search([('key', '=', 'lot-%s-%s' % (factory.id, lot_sa.id))])
check('Nhắc lô SA còn 50 hũ hết hạn 31/12', lot_rem.state == 'open' and '50' in lot_rem.title and lot_rem.due_date == date(2026, 12, 31),
      lot_rem.mapped('title'))
check('Hợp đồng thử việc đã quá hạn vẫn được nhắc', REM.search_count([('key', '=', 'hdld-%s-2026-11-29' % pro.id), ('state', '=', 'open')]) == 1)
n_before = REM.search_count([])
REM._cron_refresh(today=date(2026, 12, 22))
check('Quét lại không tạo trùng', REM.search_count([]) == n_before)
factory.sudo().write({'lfood_remind_days': 5})
REM._cron_refresh(today=date(2026, 12, 22))
check('Lô ra ngoài khoảng nhắc thì tự đóng', lot_rem.state == 'done' and 'Tự đóng' in lot_rem.done_note, lot_rem.state)
factory.sudo().write({'lfood_remind_days': 30})
hr_rem = REM.with_user(users['ketoanvien']).search([('key', '=', 'hdld-%s-2026-11-29' % pro.id)])
hr_rem.action_done()
REM._cron_refresh(today=date(2026, 12, 22))
check('Việc đã đánh dấu xử lý không bị mở lại', hr_rem.state == 'done')
check('Việc nhắc có nút mở chứng từ gốc', hr_rem.action_open()['res_id'] == pro.id)

# ---- bán hàng giữa hai pháp nhân
office = ref('base.main_company')
check('Kế toán viên mẫu được làm ở cả hai pháp nhân', office in users['ketoanvien'].company_ids and factory in users['ketoanvien'].company_ids)
def gl(company, code, **dom):
    env.flush_all()
    domain = [('state', '=', 'posted'), ('account_code', '=like', code + '%'), ('company_id', '=', company.id)]
    domain += [(k, '=', v) for k, v in dom.items()]
    return round(sum(ML.sudo().search(domain).mapped('balance')))
wh_icn = WH.create({'code': 'NMX', 'name': 'Kho thành phẩm nhà máy', 'company_id': factory.id})
wh_icv = WH.create({'code': 'VPN', 'name': 'Kho văn phòng', 'company_id': office.id})
ic_prod = env['lfood.product'].sudo().create({'code': 'IC01', 'name': 'Yến chưng hũ', 'uom': 'hũ', 'kind': 'finished',
                                              'track_lot': True, 'vat_rate_id': vat8.id, 'company_id': False})
PK.create({'kind': 'in', 'purpose': 'factory', 'date': date(2026, 12, 1), 'warehouse_id': wh_icn.id,
           'line_ids': [(0, 0, {'product_id': ic_prod.id, 'lot_name': 'IC1', 'expiry_date': date(2027, 12, 31),
                                'quantity': 30, 'price_unit': 10000})]}).action_done()
lot_ic = env['lfood.stock.lot'].search([('product_id', '=', ic_prod.id), ('name', '=', 'IC1')])
IC = env['lfood.intercompany.transfer'].with_user(users['ketoanvien']).with_company(factory)
env.flush_all()
env.cr.execute('SAVEPOINT ic_same')
try:
    IC.create({'company_id': factory.id, 'dest_company_id': factory.id, 'warehouse_id': wh_icn.id,
               'dest_warehouse_id': wh_icn.id}); env.flush_all()
    check('Chặn bán cho chính pháp nhân mình', False)
except ValidationError:
    check('Chặn bán cho chính pháp nhân mình', True)
env.cr.execute('ROLLBACK TO SAVEPOINT ic_same')
env.clear()
ic = IC.create({'company_id': factory.id, 'dest_company_id': office.id, 'warehouse_id': wh_icn.id,
                'dest_warehouse_id': wh_icv.id, 'date': date(2026, 12, 23),
                'line_ids': [(0, 0, {'product_id': ic_prod.id, 'quantity': 20, 'price_unit': 9000, 'vat_rate_id': vat8.id})]})
check('Cấp số BNB, cảnh báo giá chuyển thấp hơn giá vốn', ic.name.startswith('BNB') and ic.below_cost and 'IC01' in ic.below_cost,
      (ic.name, ic.below_cost))
env.flush_all()
env.cr.execute('SAVEPOINT ic_prod')
try:
    ic.write({'line_ids': [(0, 0, {'product_id': kc_prod.id, 'quantity': 1, 'price_unit': 1, 'vat_rate_id': vat8.id})]})
    env.flush_all()
    check('Chặn mặt hàng chỉ thuộc một pháp nhân', False)
except ValidationError:
    check('Chặn mặt hàng chỉ thuộc một pháp nhân', True)
env.cr.execute('ROLLBACK TO SAVEPOINT ic_prod')
env.clear()
ic.line_ids.write({'price_unit': 12000})
check('Giá chuyển 12.000 cao hơn giá vốn thì hết cảnh báo', not ic.below_cost)
try:
    ic.action_post(); check('Chặn ghi sổ khi thiếu số hóa đơn, căn cứ giá', False)
except UserError:
    check('Chặn ghi sổ khi thiếu số hóa đơn, căn cứ giá', True)
ic.write({'invoice_symbol': 'C26TNM', 'invoice_number': '00000501',
          'price_basis': 'Giá bán cho nhà phân phối độc lập tháng 12/2026'})
f_rev, f_cogs, o_156, o_1331 = gl(factory, '511'), gl(factory, '632'), gl(office, '156'), gl(office, '1331')
o_pay = gl(office, '331', partner_id=factory.partner_id.id)
f_rec = gl(factory, '131', partner_id=office.partner_id.id)
ic.action_post()
env.invalidate_all()
inv_ic = ic.sale_invoice_id
check('Bên bán: hóa đơn cho Văn phòng, doanh thu 240.000, thuế 19.200, phải thu 259.200',
      inv_ic.state == 'posted' and inv_ic.company_id == factory and inv_ic.partner_id == office.partner_id
      and gl(factory, '511') - f_rev == -240_000 and gl(factory, '131', partner_id=office.partner_id.id) - f_rec == 259_200,
      (inv_ic.state, gl(factory, '511') - f_rev))
check('Bên bán: giá vốn 200.000, kho nhà máy còn 10 hũ lô IC1',
      gl(factory, '632') - f_cogs == 200_000 and ic_prod._position(wh_icn, lot_ic)[0] == 10,
      (gl(factory, '632') - f_cogs, ic_prod._position(wh_icn, lot_ic)))
pin = ic.in_picking_id.sudo()
check('Bên mua: phiếu nhập mua cùng số hóa đơn, giữ lô IC1, 20 hũ vào kho văn phòng',
      pin.state == 'done' and pin.company_id == office and pin.invoice_number == '00000501'
      and ic_prod._position(wh_icv, lot_ic) == (20, 240_000), (pin.state, ic_prod._position(wh_icv, lot_ic)))
check('Bên mua: Nợ 156 240.000, Nợ 1331 19.200, phải trả Nhà máy 259.200',
      gl(office, '156') - o_156 == 240_000 and gl(office, '1331') - o_1331 == 19_200
      and gl(office, '331', partner_id=factory.partner_id.id) - o_pay == -259_200,
      (gl(office, '156') - o_156, gl(office, '1331') - o_1331, gl(office, '331', partner_id=factory.partner_id.id) - o_pay))
try:
    ic.write({'memo': 'sửa'}); check('Không sửa chứng từ đã ghi sổ hai bên', False)
except UserError:
    check('Không sửa chứng từ đã ghi sổ hai bên', True)

# ---- đối soát ngân hàng
import base64
BA = env['lfood.bank.account']
try:
    BA.with_user(users['ketoanvien']).create({'bank': 'Thử', 'number': '1', 'company_id': factory.id})
    check('Kế toán viên không khai báo tài khoản ngân hàng', False)
except AccessError:
    check('Kế toán viên không khai báo tài khoản ngân hàng', True)
ba = BA.with_user(users['ketoantruong']).with_company(factory).create(
    {'bank': 'Vietcombank', 'branch': 'Tây Ninh', 'number': '0071000123456', 'company_id': factory.id,
     'reconcile_from': date(2027, 1, 4)})
b0 = round(sum(ML.sudo().search(
    [('state', '=', 'posted'), ('account_code', '=like', '112%'), ('company_id', '=', factory.id),
     ('date', '<', date(2027, 1, 4))]).mapped('balance')))
PayF = env['lfood.payment'].with_user(users['ketoanvien']).with_company(factory)
bp1 = PayF.create({'kind': 'out', 'method': 'bank', 'purpose': 'supplier', 'partner_id': supplier.id, 'amount': 3_000_000,
                   'memo': 'Trả tiền hàng tháng 12', 'date': date(2027, 1, 4), 'company_id': factory.id})
bp1.action_post()
bp2 = PayF.create({'kind': 'in', 'method': 'bank', 'purpose': 'customer', 'partner_id': customer.id, 'amount': 5_000_000,
                   'memo': 'Khách trả tiền', 'date': date(2027, 1, 6), 'company_id': factory.id})
bp2.action_post()
bp3 = PayF.create({'kind': 'out', 'method': 'bank', 'purpose': 'supplier', 'partner_id': supplier.id, 'amount': 1_000_000,
                   'memo': 'Chuyển khoản cuối tuần', 'date': date(2027, 1, 10), 'company_id': factory.id})
bp3.action_post()
check('Phiếu chuyển khoản tự gán tài khoản ngân hàng duy nhất vào dòng 112',
      bp1.bank_account_id == ba and Move._active_for(bp1).line_ids.filtered(lambda l: l.account_code == '112').bank_account_id == ba)
ST = env['lfood.bank.statement'].with_user(users['ketoanvien']).with_company(factory)
end = b0 - 3_000_000 + 5_000_000 - 22_000
st = ST.create({'bank_account_id': ba.id, 'date_from': date(2027, 1, 4), 'date_to': date(2027, 1, 10),
                'balance_start': b0, 'balance_end': end})
bad = 'ngay,so_tham_chieu,noi_dung,tien_ra,tien_vao\n2027-01-05,X,sai ngay,1,0\n'
st.write({'import_file': base64.b64encode(bad.encode())})
try:
    st.action_import(); check('Báo lỗi dòng CSV sai định dạng ngày', False)
except UserError as err:
    check('Báo lỗi dòng CSV sai định dạng ngày', 'Dòng 2' in str(err), str(err)[:50])
csv_text = ('ngay;so_tham_chieu;noi_dung;tien_ra;tien_vao\n'
            '05/01/2027;%s;Trả tiền hàng;3000000;0\n'
            '06/01/2027;FT123;CTY KHACH CK;0;5000000\n'
            '10/01/2027;;Phí SMS banking;22000;0\n') % bp1.name
st.write({'import_file': base64.b64encode(csv_text.encode('utf-8'))})
st.action_import()
check('Nhập sổ phụ CSV 3 giao dịch, sổ phụ tự khớp số dư', len(st.line_ids) == 3 and not st.statement_error,
      (len(st.line_ids), st.statement_error))
st.action_match()
check('Khớp tự động 2 giao dịch cùng số tiền, lệch 1 ngày',
      st.line_ids.filtered(lambda l: l.amount == -3_000_000).move_line_id.move_id == Move._active_for(bp1)
      and st.line_ids.filtered(lambda l: l.amount == 5_000_000).move_line_id.move_id == Move._active_for(bp2)
      and not st.line_ids.filtered(lambda l: l.amount == -22_000).move_line_id,
      [(l.amount, l.move_line_id.move_id.ref) for l in st.line_ids])
check('Bảng đối chiếu: sổ đã ghi ngân hàng chưa ghi -1.000.000, ngân hàng đã ghi sổ chưa có -22.000, chênh lệch 0',
      (st.book_only, st.bank_only, st.difference) == (-1_000_000, -22_000, 0), (st.book_only, st.bank_only, st.difference))
try:
    st.action_done(); check('Chặn hoàn tất khi còn giao dịch ngân hàng chưa khớp', False)
except UserError:
    check('Chặn hoàn tất khi còn giao dịch ngân hàng chưa khớp', True)
fee_line = st.line_ids.filtered(lambda l: l.amount == -22_000)
env.flush_all()
env.cr.execute('SAVEPOINT bank_wrong')
try:
    fee_line.write({'move_line_id': Move._active_for(bp3).line_ids.filtered(lambda l: l.account_code == '112').id})
    env.flush_all()
    check('Chặn khớp tay khác số tiền', False)
except ValidationError:
    check('Chặn khớp tay khác số tiền', True)
env.cr.execute('ROLLBACK TO SAVEPOINT bank_wrong')
env.clear()
fee_pay = env['lfood.payment'].browse(fee_line.action_make_payment()['res_id'])
check('Lập phiếu chi phí ngân hàng nháp: 22.000, Có 112, Nợ 6427',
      (fee_pay.state, fee_pay.kind, fee_pay.amount, fee_pay.cash_account, fee_pay.counterpart_account)
      == ('draft', 'out', 22_000, '112', '6427'),
      (fee_pay.state, fee_pay.kind, fee_pay.amount, fee_pay.cash_account, fee_pay.counterpart_account))
fee_pay.with_user(users['ketoanvien']).action_post()
st.action_match()
st.invalidate_recordset()
check('Sau khi ghi phiếu phí: khớp đủ, chênh lệch 0',
      all(st.line_ids.mapped('move_line_id')) and st.difference == 0 and st.bank_only == 0, (st.bank_only, st.difference))
st.action_done()
check('Hoàn tất đối soát, bảng đối chiếu có khoản chưa ghi', st.state == 'done' and 'Chuyển khoản cuối tuần' in st.report_html)
try:
    st.write({'balance_end': 1}); check('Không sửa sổ phụ đã đối soát xong', False)
except UserError:
    check('Không sửa sổ phụ đã đối soát xong', True)
st2 = ST.create({'bank_account_id': ba.id, 'date_from': date(2027, 1, 11), 'date_to': date(2027, 1, 17),
                 'balance_start': end, 'balance_end': end - 1_000_000,
                 'line_ids': [(0, 0, {'date': date(2027, 1, 12), 'description': 'CK cuối tuần', 'amount': -1_000_000})]})
st2.action_match()
check('Kỳ sau khớp được khoản còn treo của kỳ trước', st2.line_ids.move_line_id.move_id == Move._active_for(bp3)
      and st2.difference == 0, (st2.line_ids.move_line_id.move_id.ref, st2.difference))
ba2 = BA.with_user(users['ketoantruong']).with_company(factory).create(
    {'bank': 'BIDV', 'number': '222', 'company_id': factory.id, 'reconcile_from': date(2027, 1, 1)})
bp4 = PayF.create({'kind': 'out', 'method': 'bank', 'purpose': 'supplier', 'partner_id': supplier.id, 'amount': 1,
                   'memo': 'thử', 'date': date(2027, 1, 12), 'company_id': factory.id})
try:
    bp4.action_post(); check('Có hai tài khoản ngân hàng thì bắt chọn tài khoản trên phiếu', False)
except UserError:
    check('Có hai tài khoản ngân hàng thì bắt chọn tài khoản trên phiếu', True)
bp4.unlink()
ba2.with_user(users['ketoantruong']).write({'active': False})

# ---- tạm ứng, thanh toán tạm ứng
ADV = env['lfood.advance'].with_user(users['ketoanvien']).with_company(factory)
ADV_DIR = env['lfood.advance'].with_user(users['giamdoc']).with_company(factory)
e_adv = EMP.create({'code': 'NVTU01', 'name': 'Nhân viên đi công tác', 'company_id': factory.id, 'region': 'I'})
adv0 = ADV.create({'employee_id': e_adv.id, 'company_id': factory.id, 'date': date(2026, 9, 1), 'due_date': date(2026, 9, 10),
                   'reason': 'Tạm ứng cũ', 'amount': 1_000_000})
try:
    adv0.action_approve(); check('Kế toán viên không duyệt tạm ứng', False)
except UserError:
    check('Kế toán viên không duyệt tạm ứng', True)
ADV_DIR.browse(adv0.id).action_approve()
adv1 = ADV.create({'employee_id': e_adv.id, 'company_id': factory.id, 'date': date(2027, 2, 1), 'due_date': date(2027, 2, 15),
                   'reason': 'Công tác Hà Nội', 'amount': 10_000_000})
try:
    ADV_DIR.browse(adv1.id).action_approve(); check('Chặn tạm ứng mới khi còn tạm ứng quá hạn (quy chế công ty)', False)
except UserError as err:
    check('Chặn tạm ứng mới khi còn tạm ứng quá hạn (quy chế công ty)', adv0.name in str(err), str(err)[:80])
factory.sudo().write({'lfood_advance_block_overdue': False})
ADV_DIR.browse(adv1.id).action_approve()
check('Tắt quy chế thì Giám đốc duyệt được', adv1.state == 'approved' and adv1.approved_by == users['giamdoc'])
factory.sudo().write({'lfood_advance_block_overdue': True})
try:
    adv1.write({'amount': 20_000_000}); check('Không sửa số tiền tạm ứng đã duyệt', False)
except UserError:
    check('Không sửa số tiền tạm ứng đã duyệt', True)
p_adv = env['lfood.payment'].browse(adv1.action_pay()['res_id'])
check('Phiếu chi tạm ứng nháp: Nợ 141 theo người tạm ứng', p_adv.state == 'draft' and p_adv.counterpart_account == '141'
      and p_adv.partner_id == e_adv.partner_id and p_adv.amount == 10_000_000)
p_adv.with_user(users['ketoanvien']).write({'date': date(2027, 2, 1)})
p_adv.with_user(users['ketoanvien']).action_post()
check('Ghi phiếu chi thì tạm ứng chuyển sang Đã chi, 141 của người này 10.000.000',
      adv1.state == 'paid' and adv1.paid == 10_000_000 and net('141', partner_id=e_adv.partner_id.id) == 10_000_000,
      (adv1.state, adv1.paid, net('141', partner_id=e_adv.partner_id.id)))
env.flush_all()
env.cr.execute('SAVEPOINT adv_noinv')
try:
    adv1.write({'line_ids': [(0, 0, {'date': date(2027, 2, 3), 'name': 'Khách sạn', 'account': '6427', 'amount': 1,
                                     'vat_rate_id': vat8.id, 'tax': 1})]})
    env.flush_all()
    check('Dòng có thuế GTGT phải có số hóa đơn, người bán', False)
except ValidationError:
    check('Dòng có thuế GTGT phải có số hóa đơn, người bán', True)
env.cr.execute('ROLLBACK TO SAVEPOINT adv_noinv')
env.clear()
adv1.write({'settle_date': date(2027, 2, 10), 'line_ids': [
    (0, 0, {'date': date(2027, 2, 3), 'name': 'Khách sạn 3 đêm', 'account': '6427', 'amount': 6_000_000,
            'vat_rate_id': vat8.id, 'invoice_ref': 'C27TKS 0000123', 'seller_id': supplier.id, 'pay_method': 'cash'}),
    (0, 0, {'date': date(2027, 2, 4), 'name': 'Vé máy bay', 'account': '6427', 'amount': 2_000_000,
            'vat_rate_id': vat8.id, 'invoice_ref': 'C27TVN 0000456', 'seller_id': supplier.id, 'pay_method': 'bank'}),
    (0, 0, {'date': date(2027, 2, 4), 'name': 'Taxi không hóa đơn', 'account': '6428', 'amount': 1_000_000})]})
b6427, b1331 = net('6427'), net('1331')
adv1.action_settle()
env.invalidate_all()
check('Thanh toán tạm ứng: Nợ 6427 8.000.000, 6428 1.000.000, 1331 640.000, Có 141 9.640.000',
      net('6427') - b6427 == 8_000_000 and net('1331') - b1331 == 640_000
      and net('141', partner_id=e_adv.partner_id.id) == 360_000 and adv1.spent == 9_640_000,
      (net('6427') - b6427, net('1331') - b1331, net('141', partner_id=e_adv.partner_id.id)))
refund = adv1.payment_ids.filtered(lambda p: p.kind == 'in')
check('Chi không hết 360.000: lập phiếu thu nháp nộp lại quỹ, tạm ứng chờ hoàn tất',
      adv1.state == 'settled' and refund.state == 'draft' and refund.amount == 360_000 and refund.method == 'cash',
      (adv1.state, refund.mapped('amount')))
refund.with_user(users['ketoanvien']).write({'date': date(2027, 2, 10)})
refund.with_user(users['ketoanvien']).action_post()
check('Nộp lại đủ thì hoàn tất, 141 của người này về 0',
      adv1.state == 'closed' and adv1.remaining == 0 and net('141', partner_id=e_adv.partner_id.id) == 0,
      (adv1.state, adv1.remaining))
try:
    adv1.line_ids[:1].write({'amount': 1}); check('Không sửa bảng thanh toán đã ghi sổ', False)
except UserError:
    check('Không sửa bảng thanh toán đã ghi sổ', True)
feb = VR.sudo().new({'company_id': factory.id, 'period_type': 'month', 'year': 2027, 'month': 2})
adv_vat = [v for v in feb._purchase_lines() if v['source_model'] == 'lfood.advance' and v['source_id'] == adv1.id]
check('Bảng kê mua vào có 2 hóa đơn trong bảng thanh toán; hóa đơn 6.480.000 trả tiền mặt không được khấu trừ',
      sorted((v['tax'], v['deductible']) for v in adv_vat) == [(160_000, True), (480_000, False)],
      [(v['tax'], v['deductible']) for v in adv_vat])
adv2 = ADV.create({'employee_id': e_adv.id, 'company_id': factory.id, 'date': date(2027, 2, 11), 'due_date': date(2027, 2, 20),
                   'reason': 'Mua văn phòng phẩm', 'amount': 2_000_000})
factory.sudo().write({'lfood_advance_block_overdue': False})
ADV_DIR.browse(adv2.id).action_approve()
p2 = env['lfood.payment'].browse(adv2.action_pay()['res_id'])
p2.with_user(users['ketoanvien']).write({'date': date(2027, 2, 11)})
p2.with_user(users['ketoanvien']).action_post()
adv2.write({'settle_date': date(2027, 2, 12), 'salary_deduct': True,
            'line_ids': [(0, 0, {'date': date(2027, 2, 12), 'name': 'Giấy in', 'account': '6428', 'amount': 1_500_000})]})
b334 = net('334', partner_id=e_adv.partner_id.id)
adv2.action_settle()
env.invalidate_all()
check('Chi không hết 500.000 trừ lương: Nợ 334 / Có 141, hoàn tất ngay',
      adv2.state == 'closed' and net('334', partner_id=e_adv.partner_id.id) - b334 == 500_000
      and adv2.returned == 500_000 and adv2.remaining == 0 and net('141', partner_id=e_adv.partner_id.id) == 0,
      (adv2.state, net('334', partner_id=e_adv.partner_id.id) - b334, adv2.remaining))
adv3 = ADV.create({'employee_id': e_adv.id, 'company_id': factory.id, 'date': date(2027, 2, 13), 'due_date': date(2027, 2, 20),
                   'reason': 'Tiếp khách', 'amount': 1_000_000})
ADV_DIR.browse(adv3.id).action_approve()
p3 = env['lfood.payment'].browse(adv3.action_pay()['res_id'])
p3.with_user(users['ketoanvien']).write({'date': date(2027, 2, 13)})
p3.with_user(users['ketoanvien']).action_post()
adv3.write({'settle_date': date(2027, 2, 14),
            'line_ids': [(0, 0, {'date': date(2027, 2, 14), 'name': 'Tiếp khách', 'account': '6428', 'amount': 1_200_000})]})
adv3.action_settle()
extra = adv3.payment_ids.filtered(lambda p: p.kind == 'out' and p.state == 'draft')
check('Chi quá 200.000: lập phiếu chi bổ sung nháp', adv3.state == 'settled' and extra.amount == 200_000, extra.mapped('amount'))
extra.with_user(users['ketoanvien']).write({'date': date(2027, 2, 14)})
extra.with_user(users['ketoanvien']).action_post()
check('Chi bổ sung xong thì hoàn tất, 141 về 0', adv3.state == 'closed' and net('141', partner_id=e_adv.partner_id.id) == 0,
      (adv3.state, net('141', partner_id=e_adv.partner_id.id)))
factory.sudo().write({'lfood_advance_block_overdue': True})

# ---- nghĩa vụ thuế, tiền chậm nộp
OBL = env['lfood.tax.obligation'].with_user(users['ketoanvien']).with_company(factory)
obl_vat = OBL.search([('source_key', '=', 'lfood.vat.return-%s-tax' % sepr.id)])
check('Hủy xác nhận tờ khai GTGT tháng 9 thì nghĩa vụ nộp (nếu có) chuyển sang Đã hủy',
      not obl_vat or obl_vat.state == 'cancel', obl_vat.mapped('state'))
obl_q3 = OBL.search([('source_key', '=', 'lfood.cit.provisional-%s-tax' % q3.id)])
check('Ghi sổ tạm nộp TNDN quý 3 sinh nghĩa vụ hạn 30/10, TK 3334',
      obl_q3.amount == q3.tax and obl_q3.due_date == date(2026, 10, 30) and obl_q3.account == '3334' and obl_q3.state == 'open',
      (obl_q3.amount, obl_q3.due_date, obl_q3.state))
obl_fin = OBL.search([('source_model', '=', 'lfood.cit.finalization'), ('source_id', '=', fin.id)])
check('Hủy quyết toán thì nghĩa vụ quyết toán (nếu có) chuyển sang Đã hủy',
      (not obl_fin and fin.tax_remaining <= 0) or set(obl_fin.mapped('state')) == {'cancel'},
      obl_fin.mapped('state'))
try:
    obl_q3.write({'amount': 1}); check('Không sửa số tiền nghĩa vụ sinh từ tờ khai', False)
except UserError:
    check('Không sửa số tiền nghĩa vụ sinh từ tờ khai', True)
check('Tỷ lệ tiền chậm nộp 0,03%/ngày ghi căn cứ Luật 108/2025',
      env['lfood.legal.param'].get_value('TIEN_CHAM_NOP_TY_LE_NGAY', date(2026, 11, 1)) == 0.03
      and '108/2025' in ref('lfood_taxdue.pv_late_rate_2026').legal_ref)
half = round(obl_q3.amount / 2)
pay_q3 = env['lfood.payment'].browse(obl_q3.action_pay()['res_id'])
check('Phiếu nộp thuế: Nợ 3334, số còn phải nộp', pay_q3.counterpart_account == '3334' and pay_q3.amount == obl_q3.amount
      and pay_q3.purpose == 'tax', (pay_q3.counterpart_account, pay_q3.amount))
pay_q3.with_user(users['ketoanvien']).write({'amount': obl_q3.amount + 1, 'date': date(2026, 11, 5)})
try:
    pay_q3.with_user(users['ketoanvien']).action_post(); check('Chặn nộp nhiều hơn số còn phải nộp', False)
except UserError:
    check('Chặn nộp nhiều hơn số còn phải nộp', True)
pay_q3.with_user(users['ketoanvien']).write({'amount': half})
b3334 = net('3334')
pay_q3.with_user(users['ketoanvien']).action_post()
check('Nộp một nửa ngày 05/11: 3334 giảm, còn nợ một nửa', net('3334') - b3334 == half and obl_q3.remaining == obl_q3.amount - half
      and obl_q3.state == 'open', (net('3334') - b3334, obl_q3.remaining))
rest = obl_q3.amount - half
total, rows = obl_q3.interest_at(date(2026, 11, 9))
check('Chậm nộp: phần nộp 05/11 tính 5 ngày (31/10-04/11), phần chưa nộp đến 09/11 tính 9 ngày',
      rows == [(half, 5, round(half * 5 * 0.03 / 100)), (rest, 9, round(rest * 9 * 0.03 / 100))]
      and total == rows[0][2] + rows[1][2], rows)
b811 = net('811')
obl_q3.action_post_interest(date(2026, 11, 9))
obl_q3.action_post_interest(date(2026, 11, 9))
env.invalidate_all()
check('Ghi sổ tiền chậm nộp Nợ 811 / Có 3339 một lần, bấm lại không ghi trùng',
      net('811') - b811 == total and obl_q3.interest_posted == total, (net('811') - b811, total))
pay_int = env['lfood.payment'].browse(obl_q3.action_pay_interest()['res_id'])
check('Phiếu nộp tiền chậm nộp: Nợ 3339', pay_int.counterpart_account == '3339' and pay_int.amount == total,
      (pay_int.counterpart_account, pay_int.amount))
pay_int.with_user(users['ketoanvien']).write({'date': date(2026, 11, 9)})
pay_int.with_user(users['ketoanvien']).action_post()
pay_rest = env['lfood.payment'].browse(obl_q3.action_pay()['res_id'])
pay_rest.with_user(users['ketoanvien']).write({'date': date(2026, 11, 9)})
pay_rest.with_user(users['ketoanvien']).action_post()
env.invalidate_all()
check('Nộp đủ thì nghĩa vụ Đã nộp đủ, tiền chậm nộp đã nộp bằng số đã ghi sổ',
      obl_q3.state == 'paid' and obl_q3.remaining == 0 and obl_q3.interest_paid == total and net('3339') == 0,
      (obl_q3.state, obl_q3.remaining, obl_q3.interest_paid, net('3339')))
bad_pay = env['lfood.payment'].with_user(users['ketoanvien']).with_company(factory).create(
    {'kind': 'out', 'method': 'bank', 'purpose': 'tax', 'amount': 1, 'memo': 'thiếu nghĩa vụ', 'date': date(2026, 11, 9),
     'company_id': factory.id})
try:
    bad_pay.action_post(); check('Phiếu nộp thuế phải chọn nghĩa vụ', False)
except UserError:
    check('Phiếu nộp thuế phải chọn nghĩa vụ', True)
bad_pay.unlink()
manual = OBL.create({'name': 'Thuế TNCN tháng 10/2026', 'tax_type': 'pit', 'amount': 1_000_000, 'due_date': date(2026, 11, 20),
                     'company_id': factory.id})
manual.write({'amount': 1_200_000})
check('Nghĩa vụ nhập tay sửa được, TK 3335', manual.amount == 1_200_000 and manual.account == '3335')

# ---- vay và lãi vay
bank_lender = env['res.partner'].create({'name': 'Ngân hàng cho vay thử', 'is_company': True})
person_lender = env['res.partner'].create({'name': 'Cá nhân cho vay thử'})
LOAN = env['lfood.loan'].with_user(users['ketoanvien']).with_company(factory)
LOAN_KT = env['lfood.loan'].with_user(users['ketoantruong']).with_company(factory)
loan1 = LOAN.create({'partner_id': bank_lender.id, 'lender_type': 'bank', 'contract_ref': 'HDTD-01', 'principal': 365_000_000,
                     'rate': 10, 'date_start': date(2027, 3, 10), 'date_end': date(2028, 3, 9), 'company_id': factory.id})
loan2 = LOAN.create({'partner_id': person_lender.id, 'lender_type': 'other', 'contract_ref': 'HDV-CN-01', 'principal': 36_500_000,
                     'rate': 24, 'date_start': date(2027, 3, 1), 'date_end': date(2027, 12, 31), 'company_id': factory.id})
try:
    loan1.action_disburse(); check('Kế toán viên không ghi nhận khoản vay', False)
except UserError:
    check('Kế toán viên không ghi nhận khoản vay', True)
b112, b3411 = net('112'), net('3411')
LOAN_KT.browse((loan1 | loan2).ids).action_disburse()
check('Giải ngân: Nợ 112 / Có 3411 401.500.000, đang vay',
      net('112') - b112 == 401_500_000 and net('3411') - b3411 == -401_500_000 and loan1.state == 'running'
      and loan1.outstanding == 365_000_000, (net('112') - b112, net('3411') - b3411, loan1.state))
b01_loan = LedgerReport.create({'report': 'b01', 'company_id': factory.id, 'date_from': date(2027, 1, 1),
                                'date_to': date(2027, 3, 31)})
v_before, _pl = b01_loan._b01_values(date(2027, 4, 1))
loan3 = LOAN.create({'partner_id': bank_lender.id, 'lender_type': 'bank', 'contract_ref': 'HDTD-DH-01', 'principal': 100_000_000,
                     'rate': 8, 'date_start': date(2027, 3, 1), 'date_end': date(2029, 6, 30), 'company_id': factory.id})
LOAN_KT.browse(loan3.id).action_disburse()
v_after, _pl = b01_loan._b01_values(date(2027, 4, 1))
check('B01 31/03/2027: khoản vay đáo hạn trong 12 tháng vào 321 ngắn hạn, khoản đáo hạn 2029 vào 339 dài hạn',
      v_after['321'] - v_before['321'] == 0 and v_after['339'] - v_before['339'] == 100_000_000
      and v_before['321'] >= 401_500_000,
      (v_before['321'], v_after['321'], v_before['339'], v_after['339']))
loan4 = LOAN.create({'partner_id': bank_lender.id, 'lender_type': 'bank', 'contract_ref': 'HDTD-TD-01', 'principal': 90_000_000,
                     'rate': 9, 'date_start': date(2027, 3, 1), 'date_end': date(2030, 3, 1), 'company_id': factory.id,
                     'installment_count': 3, 'installment_months': 12, 'first_due': date(2027, 12, 1)})
loan4.action_make_schedule()
check('Lập lịch trả gốc đều 3 kỳ 30 triệu từ 01/12/2027', [(s.due_date, s.amount) for s in loan4.schedule_ids] ==
      [(date(2027, 12, 1), 30_000_000), (date(2028, 12, 1), 30_000_000), (date(2029, 12, 1), 30_000_000)])
loan4.schedule_ids[:1].write({'amount': 20_000_000})
try:
    LOAN_KT.browse(loan4.id).action_disburse(); check('Chặn giải ngân khi tổng lịch trả khác số vay', False)
except UserError:
    check('Chặn giải ngân khi tổng lịch trả khác số vay', True)
loan4.schedule_ids[:1].write({'amount': 30_000_000})
LOAN_KT.browse(loan4.id).action_disburse()
v_sched, _pl = b01_loan._b01_values(date(2027, 4, 1))
check('B01 31/03/2027: vay trả dần tách 30 triệu đến hạn vào 321, 60 triệu vào 339',
      v_sched['321'] - v_after['321'] == 30_000_000 and v_sched['339'] - v_after['339'] == 60_000_000,
      (v_sched['321'] - v_after['321'], v_sched['339'] - v_after['339']))
REM._cron_refresh(today=date(2027, 11, 15))
check('Nhắc kỳ trả gốc 01/12/2027 của hợp đồng trả dần', REM.search_count(
    [('key', '=', 'loan-%s-2027-12-01' % loan4.schedule_ids[:1].id), ('state', '=', 'open')]) == 1)
try:
    loan4.schedule_ids[:1].write({'amount': 1}); check('Không sửa lịch trả gốc sau giải ngân', False)
except UserError:
    check('Không sửa lịch trả gốc sau giải ngân', True)
check('Vay cá nhân lãi 24%/năm: nhật ký cảnh báo vượt mức 20% của Bộ luật Dân sự', Log.sudo().search_count(
    [('model', '=', 'lfood.loan'), ('res_id', '=', loan2.id), ('summary', 'ilike', 'vượt mức 20%')]) == 1)
try:
    loan1.write({'rate': 9}); check('Không sửa lãi suất hợp đồng đã giải ngân', False)
except UserError:
    check('Không sửa lãi suất hợp đồng đã giải ngân', True)
b635, b335 = net('635'), net('335')
wiz = env['lfood.loan.accrue'].with_user(users['ketoanvien']).with_company(factory).create(
    {'company_id': factory.id, 'date_to': date(2027, 3, 31)})
wiz.action_run()
acc1 = loan1.accrual_ids
acc2 = loan2.accrual_ids
check('Trích lãi tháng 3: ngân hàng 22 ngày = 2.200.000; cá nhân 31 ngày = 744.000',
      (acc1.amount, acc1.date_from, acc2.amount) == (2_200_000, date(2027, 3, 10), 744_000)
      and net('635') - b635 == 2_944_000 + loan3.interest_accrued + loan4.interest_accrued and net('335') - b335 == -(2_944_000 + loan3.interest_accrued + loan4.interest_accrued),
      (acc1.mapped('amount'), acc2.mapped('amount'), net('635') - b635))
check('Phần lãi vượt 20%/năm không được trừ: 744.000 x 4/24 = 124.000', acc2.nondeductible == 124_000 and acc1.nondeductible == 0,
      (acc2.nondeductible, acc1.nondeductible))
wiz2 = env['lfood.loan.accrue'].with_user(users['ketoanvien']).with_company(factory).create(
    {'company_id': factory.id, 'date_to': date(2027, 3, 31)})
wiz2.action_run()
check('Trích lại cùng ngày không phát sinh thêm', 'Không có lãi' in wiz2.result and len(loan1.accrual_ids) == 1, wiz2.result)
pr = env['lfood.payment'].browse(loan1.with_context(loan_part='principal').action_pay()['res_id'])
check('Phiếu trả gốc: Nợ 3411', pr.counterpart_account == '3411' and pr.amount == 365_000_000)
pr.with_user(users['ketoanvien']).write({'amount': 182_500_000, 'date': date(2027, 3, 31)})
try:
    pr.with_user(users['ketoanvien']).action_post(); check('Chặn trả gốc vào ngày đã trích lãi theo dư nợ cũ', False)
except UserError:
    check('Chặn trả gốc vào ngày đã trích lãi theo dư nợ cũ', True)
pr.with_user(users['ketoanvien']).write({'date': date(2027, 4, 11)})
pr.with_user(users['ketoanvien']).action_post()
check('Trả một nửa gốc 11/04: dư nợ 182.500.000', loan1.outstanding == 182_500_000 and loan1.state == 'running')
loan1.sudo()._accrue(date(2027, 4, 30))
check('Lãi tháng 4 theo dư nợ thực tế: 10 ngày x 100.000 + 20 ngày x 50.000 = 2.000.000',
      loan1.accrual_ids.sorted('date_to')[-1].amount == 2_000_000, loan1.accrual_ids.mapped('amount'))
pi = env['lfood.payment'].browse(loan1.with_context(loan_part='interest').action_pay()['res_id'])
check('Phiếu trả lãi: Nợ 335, số lãi đã trích chưa trả 4.200.000', pi.counterpart_account == '335' and pi.amount == 4_200_000,
      (pi.counterpart_account, pi.amount))
pi.with_user(users['ketoanvien']).write({'amount': 4_200_001, 'date': date(2027, 4, 30)})
try:
    pi.with_user(users['ketoanvien']).action_post(); check('Chặn trả lãi nhiều hơn số đã trích', False)
except UserError:
    check('Chặn trả lãi nhiều hơn số đã trích', True)
pi.with_user(users['ketoanvien']).write({'amount': 4_200_000})
pi.with_user(users['ketoanvien']).action_post()
pr2 = env['lfood.payment'].browse(loan1.with_context(loan_part='principal').action_pay()['res_id'])
pr2.with_user(users['ketoanvien']).write({'date': date(2027, 5, 5)})
pr2.with_user(users['ketoanvien']).action_post()
check('Trả hết gốc 05/05 nhưng chưa trích lãi 01-04/05 thì chưa tất toán', loan1.outstanding == 0 and loan1.state == 'running')
loan1.sudo()._accrue(date(2027, 5, 31))
pi2 = env['lfood.payment'].browse(loan1.with_context(loan_part='interest').action_pay()['res_id'])
check('Lãi 01-04/05 = 4 ngày x 50.000 = 200.000', pi2.amount == 200_000, pi2.amount)
pi2.with_user(users['ketoanvien']).write({'date': date(2027, 5, 31)})
pi2.with_user(users['ketoanvien']).action_post()
check('Hết gốc, hết lãi thì tất toán; 3411 và 335 của hợp đồng về 0', loan1.state == 'closed'
      and loan1.interest_accrued == loan1.interest_paid == 4_400_000, (loan1.state, loan1.interest_accrued, loan1.interest_paid))

# ---- giao dịch liên kết, khống chế lãi vay
fin27 = FINAL.create({'year': 2027, 'company_id': factory.id})
fin27.action_load()
check('Chưa có bên liên kết thì không xét khống chế lãi vay', not fin27.has_related
      and not fin27.adjust_line_ids.filtered(lambda l: l.source == 'interest_cap'))
loan_rate_line = fin27.adjust_line_ids.filtered(lambda l: l.source == 'loan_rate')
check('Quyết toán 2027 đưa lãi vay vượt 20%/năm (124.000) vào điều chỉnh tăng', loan_rate_line.amount == 124_000,
      loan_rate_line.mapped('amount'))
person_lender.write({'lfood_related': True, 'lfood_related_basis': 'Cá nhân kiểm soát doanh nghiệp, khoản vay từ 10% vốn góp'})
fin27.action_load()
acc27 = sum(env['lfood.loan.accrual'].sudo().search([('company_id', '=', factory.id), ('date_to', '>=', date(2027, 1, 1)),
                                                     ('date_to', '<=', date(2027, 12, 31))]).mapped('amount'))
b02_27 = LedgerReport.create({'report': 'b02', 'company_id': factory.id, 'date_from': date(2027, 1, 1),
                              'date_to': date(2027, 12, 31)})._b02_values(date(2027, 1, 1), date(2027, 12, 31))
exp_cap = max(round((fin27.ic_op_profit + fin27.ic_interest + fin27.ic_depreciation) * 30 / 100), 0)
check('Có giao dịch với bên liên kết: lấy lợi nhuận thuần B02 mã 30, lãi vay từ phân hệ Vay (trừ phần đã loại)',
      fin27.has_related and fin27.ic_op_profit == round(b02_27['30']) and fin27.ic_interest == round(acc27) - 124_000,
      (fin27.has_related, fin27.ic_op_profit, fin27.ic_interest, acc27))
cap_line = fin27.adjust_line_ids.filtered(lambda l: l.source == 'interest_cap')
check('Khống chế 30%: phần lãi vượt vào điều chỉnh tăng',
      fin27.ic_cap == exp_cap and fin27.ic_excess == max(fin27.ic_interest - exp_cap, 0)
      and (cap_line.amount or 0) == fin27.ic_excess and fin27.ic_excess > 0,
      (fin27.ic_cap, fin27.ic_excess, cap_line.mapped('amount')))
check('Bảng giao dịch liên kết liệt kê khoản vay nhận của bên liên kết',
      'Cá nhân cho vay thử' in fin27.related_html and '36.500.000' in fin27.related_html)
check('Tham số khống chế 30% năm 2027 ghi căn cứ Nghị định 255/2026',
      '255/2026' in ref('lfood_related.pv_ic_rate_2026').legal_ref
      and env['lfood.legal.param'].get_value('KHONG_CHE_LAI_VAY_TY_LE', date(2027, 12, 31)) == 30)
check('Lãi tiền gửi tự lấy từ phiếu thu lãi, không lẫn 515 chênh lệch tỷ giá', fin27.ic_interest_income == 0,
      fin27.ic_interest_income)
check('Bên liên kết là cá nhân: không được miễn kê khai; doanh thu nhỏ nên miễn lập hồ sơ',
      fin27.tp_status == 'doc' and 'Cá nhân cho vay thử' in fin27.tp_reason and 'dưới' in fin27.tp_reason
      and fin27.tp_related_total == 36_500_000, (fin27.tp_status, fin27.tp_reason, fin27.tp_related_total))
check('Bản nháp hồ sơ xác định giá có số liệu tài chính và kết quả đánh giá',
      'HỒ SƠ XÁC ĐỊNH GIÁ' in fin27.tp_doc_html and 'Phải kê khai, được miễn lập hồ sơ' in fin27.tp_doc_html)
dep_int = PayF.create({'kind': 'in', 'method': 'bank', 'purpose': 'other', 'amount': 500_000, 'memo': 'Lãi tiền gửi tháng 12',
                       'date': date(2027, 12, 25), 'company_id': factory.id, 'cash_account': '112',
                       'counterpart_account': '515'})
check('Phiếu thu ghi Có 515 tự đánh dấu là lãi tiền gửi', dep_int.lfood_interest_income)
dep_int.action_post()
fin27.action_load()
check('Lấy lại số gợi ý: lãi tiền gửi 500.000 trừ vào lãi vay thuần', fin27.ic_interest_income == 500_000,
      fin27.ic_interest_income)
person_lender.write({'lfood_related_domestic': True, 'lfood_related_rate': fin27.rate})
fin27.action_recompute_interest_cap()
check('Mọi bên liên kết nộp thuế TNDN tại Việt Nam cùng thuế suất: miễn kê khai và miễn lập hồ sơ',
      fin27.tp_status == 'full', (fin27.tp_status, fin27.tp_reason))
fin27.write({'tp_own_incentive': True})
fin27.action_recompute_interest_cap()
check('Doanh nghiệp đang được ưu đãi: không được miễn kê khai', fin27.tp_status == 'doc', fin27.tp_status)
fin27.write({'tp_own_incentive': False})
person_lender.write({'lfood_related_domestic': False})
fin27.write({'ic_interest_income': fin27.ic_interest})
fin27.action_recompute_interest_cap()
check('Lãi tiền gửi bằng lãi vay thì lãi vay thuần bằng 0, hết phần vượt',
      fin27.ic_excess == 0 and not fin27.adjust_line_ids.filtered(lambda l: l.source == 'interest_cap'))
fin27.write({'ic_interest_income': 0})
fin27.action_recompute_interest_cap()
excess27 = fin27.ic_excess
env['lfood.cit.finalization'].with_user(users['ketoantruong']).with_company(factory).browse(fin27.id).action_post()
fin28 = FINAL.create({'year': 2028, 'company_id': factory.id})
fin28.action_load()
fin28.write({'ic_op_profit': 10_000_000_000, 'ic_interest': 0, 'ic_depreciation': 0})
fin28.action_recompute_interest_cap()
carry_line = fin28.adjust_line_ids.filtered(lambda l: l.source == 'interest_carry')
check('Năm sau còn dưới mức khống chế: trừ phần lãi vượt năm 2027 bằng điều chỉnh giảm',
      fin28.ic_carry_used == excess27 and carry_line.kind == 'decrease' and carry_line.amount == excess27,
      (fin28.ic_carry_used, excess27, carry_line.mapped('amount')))

# ---- bảo vệ dữ liệu cá nhân
import base64 as _b64
check('Nhà máy xử lý dữ liệu lương (nhạy cảm): không được miễn người phụ trách, hồ sơ đánh giá tác động',
      'Không được miễn' in factory.lfood_privacy_exempt, factory.lfood_privacy_exempt)
CONS = env['lfood.privacy.consent'].with_user(users['ketoanvien']).with_company(factory)
env.flush_all()
env.cr.execute('SAVEPOINT pv_consent')
try:
    CONS.create({'subject_kind': 'employee', 'employee_id': e_hr.id, 'purpose': 'Gửi thông tin khuyến mãi',
                 'data_types': 'Họ tên, số điện thoại', 'basis': 'consent', 'company_id': factory.id})
    env.flush_all()
    check('Sự đồng ý phải có cách thể hiện và bằng chứng', False)
except ValidationError:
    check('Sự đồng ý phải có cách thể hiện và bằng chứng', True)
env.cr.execute('ROLLBACK TO SAVEPOINT pv_consent')
env.clear()
cons = CONS.create({'subject_kind': 'employee', 'employee_id': e_hr.id, 'purpose': 'Gửi thông tin khuyến mãi',
                    'data_types': 'Họ tên, số điện thoại', 'basis': 'consent', 'channel': 'paper',
                    'evidence': _b64.b64encode(b'giay dong y'), 'evidence_name': 'dongy.pdf', 'company_id': factory.id})
labor = CONS.create({'subject_kind': 'employee', 'employee_id': e_hr.id, 'purpose': 'Tính lương, bảo hiểm, thuế TNCN',
                     'data_types': 'Số định danh, tài khoản ngân hàng, lương', 'sensitive': True, 'basis': 'labor',
                     'company_id': factory.id})
cons.action_withdraw()
check('Rút lại sự đồng ý: ghi thời điểm, trạng thái Đã rút lại', cons.state == 'withdrawn' and cons.withdrawn_on)
try:
    cons.write({'purpose': 'sửa'}); check('Không sửa ghi nhận đã rút lại', False)
except UserError:
    check('Không sửa ghi nhận đã rút lại', True)
try:
    labor.action_withdraw(); check('Căn cứ quản lý lao động không rút lại được', False)
except UserError:
    check('Căn cứ quản lý lao động không rút lại được', True)
REQ = env['lfood.privacy.request'].with_user(users['ketoanvien']).with_company(factory)
req = REQ.create({'subject_kind': 'employee', 'employee_id': e_hr.id, 'subject_name': e_hr.name, 'kind': 'access',
                  'detail': 'Xin bản sao dữ liệu lương năm 2026', 'received_on': date(2026, 12, 11), 'company_id': factory.id})
check('Yêu cầu xem dữ liệu nhận thứ Sáu 11/12: phản hồi trước 15/12, thực hiện trước 21/12',
      req.name.startswith('YCDL') and (req.respond_by, req.due_date) == (date(2026, 12, 15), date(2026, 12, 21)),
      (req.name, req.respond_by, req.due_date))
REM._cron_refresh(today=date(2026, 12, 12))
check('Nhắc hạn phản hồi yêu cầu dữ liệu cá nhân', REM.search_count([('category', '=', 'privacy'), ('res_id', '=', req.id),
                                                                   ('state', '=', 'open')]) == 1)
try:
    req.action_done(); check('Phải phản hồi trước khi kết thúc yêu cầu', False)
except UserError:
    check('Phải phản hồi trước khi kết thúc yêu cầu', True)
req.action_respond()
req.action_extend()
check('Gia hạn một lần thêm 10 ngày', req.extended and req.due_date == date(2026, 12, 31), req.due_date)
try:
    req.action_extend(); check('Không gia hạn lần hai', False)
except UserError:
    check('Không gia hạn lần hai', True)
try:
    req.action_done(); check('Kết thúc phải ghi kết quả', False)
except UserError:
    check('Kết thúc phải ghi kết quả', True)
req.write({'result': 'Đã gửi bảng lương năm 2026 qua thư điện tử'})
req.action_done()
check('Yêu cầu đã thực hiện, nhật ký ghi lại', req.state == 'done' and Log.sudo().search_count(
    [('model', '=', 'lfood.privacy.request'), ('res_id', '=', req.id)]) >= 3)
BR = env['lfood.privacy.breach'].with_user(users['ketoantruong']).with_company(factory)
br = BR.create({'name': 'Lộ tệp chấm công có vị trí', 'detected_at': '2026-12-20 08:00:00', 'location_biometric': True,
                'description': 'Tệp chấm công GPS gửi nhầm địa chỉ thư', 'company_id': factory.id,
                'fixed_on': date(2026, 12, 21)})
check('Sự cố có dữ liệu vị trí: hạn báo chủ thể 72 giờ, lưu hồ sơ đến 21/12/2031',
      str(br.subject_notice_by) == '2026-12-23 08:00:00' and br.keep_until == date(2031, 12, 21),
      (br.subject_notice_by, br.keep_until))
try:
    br.unlink(); check('Không xóa hồ sơ sự cố trước 5 năm', False)
except UserError:
    check('Không xóa hồ sơ sự cố trước 5 năm', True)
n_view = Log.sudo().search_count([('action', '=', 'view'), ('model', '=', 'lfood.employee'), ('res_id', '=', e_hr.id)])
EMP.browse(e_hr.id).web_read({'name': {}})
EMP.browse(e_hr.id).web_read({'name': {}})
check('Mở xem hồ sơ nhân sự ghi nhật ký một lần trong ngày',
      Log.sudo().search_count([('action', '=', 'view'), ('model', '=', 'lfood.employee'), ('res_id', '=', e_hr.id)]) == n_view + 1)

# ---- truy xuất nguồn gốc, thu hồi sản phẩm
TR = env['lfood.trace'].with_user(users['ketoanvien'])
tr_sb = TR.create({'lot_id': lot_sb.id})
check('Truy xuất lô SB: nguồn cung cấp có hóa đơn 0009901, khách hàng siêu thị ở bước sau',
      'TRUY XUẤT NGUỒN GỐC LÔ SB' in tr_sb.html and '0009901' in tr_sb.html and 'Siêu thị kiểm thử' in tr_sb.html
      and '31/12' not in tr_sb.html.split('Hạn sử dụng:')[1][:12])
tr_ic = TR.create({'lot_id': lot_ic.id})
check('Truy xuất lô bán giữa hai pháp nhân: thấy cả nhà máy và văn phòng',
      factory.name in tr_ic.html and office.name in tr_ic.html)
ship_sb = -sum(env['lfood.stock.valuation'].sudo().search([('lot_id', '=', lot_sb.id), ('qty', '<', 0),
                                                           ('picking_id.purpose', '=', 'sale'),
                                                           ('picking_id.partner_id', '=', cust_mt.id)]).mapped('qty'))
RC = env['lfood.recall'].with_user(users['ketoanvien']).with_company(factory)
rc = RC.create({'lot_ids': [(6, 0, lot_sb.ids)], 'reason': 'Kết quả kiểm nghiệm vi sinh vượt giới hạn',
                'kind': 'mandatory', 'company_id': factory.id, 'date': date(2027, 1, 18)})
try:
    rc.action_start(); check('Thu hồi bắt buộc phải có văn bản và thời hạn', False)
except UserError:
    check('Thu hồi bắt buộc phải có văn bản và thời hạn', True)
rc.write({'authority_ref': '12/QĐ-ATTP', 'deadline': date(2027, 2, 18)})
rc.action_start()
rl = rc.line_ids.filtered(lambda l: l.partner_id == cust_mt)
check('Bắt đầu thu hồi: cách ly lô SB, danh sách khách hàng lấy từ thẻ kho',
      rc.name.startswith('THSP') and lot_sb.hold and rl and rl.qty_shipped == ship_sb and ship_sb > 0,
      (rc.name, lot_sb.hold, rl.qty_shipped, ship_sb))
try:
    rc.action_done(); check('Chưa báo khách và chưa chọn biện pháp thì chưa hoàn thành', False)
except UserError:
    check('Chưa báo khách và chưa chọn biện pháp thì chưa hoàn thành', True)
rl.action_notify()
pk_rc = PK.browse(rl.action_receive()['res_id'])
pk_rc.write({'date': date(2027, 1, 20)})
pk_rc.action_done()
env.flush_all(); env.invalidate_all()
check('Nhập hàng thu hồi theo lô: đã thu đủ, tỷ lệ 100%',
      pk_rc.state == 'done' and rl.qty_returned == ship_sb and rc.rate == 100, (pk_rc.state, rl.qty_returned, rc.rate))
rc.write({'handling': 'destroy', 'result': 'Đã báo cáo Chi cục An toàn thực phẩm ngày 25/01/2027'})
rc.action_done()
check('Hoàn thành thu hồi, báo cáo có văn bản, tỷ lệ, biện pháp',
      rc.state == 'done' and '12/QĐ-ATTP' in rc.report_html and '100.0%' in rc.report_html and 'Tiêu hủy' in rc.report_html)

# ---- hàng bán bị trả lại theo dõi lô
rf_vals = lambda qty, number, lot=False: {
    'kind': 'refund', 'origin_id': inv_km.id, 'partner_id': cust_mt.id, 'date': date(2027, 1, 25),
    'invoice_date': date(2027, 1, 25), 'invoice_template': '1', 'invoice_symbol': 'C27TLF', 'invoice_number': number,
    'memo': 'Khách trả hàng móp hộp',
    'line_ids': [(0, 0, {'product_id': so_prod.id, 'lot_id': lot, 'name': 'Súp hũ gà trả lại', 'quantity': qty,
                         'price_unit': 27000, 'vat_rate_id': vat8.id})]}
env.flush_all()
env.cr.execute('SAVEPOINT rf_over')
try:
    SI.create(rf_vals(8, '00000901')).action_post()
    check('Chặn trả lại nhiều hơn số đã giao theo hóa đơn gốc', False)
except UserError as err:
    check('Chặn trả lại nhiều hơn số đã giao theo hóa đơn gốc', 'chưa trả lại' in str(err), str(err)[:80])
env.cr.execute('ROLLBACK TO SAVEPOINT rf_over')
env.clear()
rf1 = SI.create(rf_vals(2, '00000902'))
rf1.action_post()
rp = rf1.picking_ids
check('Hóa đơn trả lại hàng theo lô: tự lấy lô SB đã giao, kho của hóa đơn gốc, nhập 2 hũ',
      rf1.state == 'posted' and rf1.line_ids.lot_id == lot_sb and rf1.warehouse_id == wh_so and rp.state == 'done'
      and rp.purpose == 'return_in' and rp.line_ids.lot_id == lot_sb and rp.line_ids.quantity == 2,
      (rf1.state, rf1.line_ids.lot_id.name, rp.mapped('state')))
env.flush_all()
env.cr.execute('SAVEPOINT rf_over2')
try:
    SI.create(rf_vals(6, '00000903')).action_post()
    check('Lần trả sau chỉ còn 5 hũ chưa trả', False)
except UserError as err:
    check('Lần trả sau chỉ còn 5 hũ chưa trả', '5' in str(err), str(err)[:80])
env.cr.execute('ROLLBACK TO SAVEPOINT rf_over2')
env.clear()
sb_out = env['lfood.stock.valuation'].sudo().search([('picking_id', 'in', inv_km.picking_ids.ids),
                                                    ('lot_id', '=', lot_sb.id), ('qty', '<', 0)])
unit_out = round(sum(sb_out.mapped('value')) / sum(sb_out.mapped('qty')), 2)
check('Hàng trả lại nhập kho theo giá vốn đã xuất bán, ghi Nợ 156 / Có 632',
      rp.line_ids.price_unit == unit_out and rp.amount == round(2 * unit_out)
      and {l.account_code for l in Move._active_for(rp).line_ids} == {'156', '632'},
      (rp.line_ids.price_unit, unit_out, rp.amount))
check('Truy xuất lô SB thấy phiếu hàng bán bị trả lại', rp.name in TR.create({'lot_id': lot_sb.id}).html)

# ---- kiểm tra chất lượng khi nhập, hành động khắc phục
tpl = env['lfood.qc.template'].with_user(users['ketoanvien']).create({'name': 'Yến thô nhập vào', 'line_ids': [
    (0, 0, {'name': 'Cảm quan', 'requirement': 'Không mốc, không lạ'}),
    (0, 0, {'name': 'Độ ẩm', 'requirement': 'Không quá 15%'})]})
qc_prod = env['lfood.product'].sudo().create({'code': 'QC01', 'name': 'Yến thô', 'uom': 'kg', 'kind': 'material',
                                             'track_lot': True, 'company_id': factory.id, 'qc_required': True,
                                             'qc_template_id': tpl.id})
wh_qc = WH.create({'code': 'KQC', 'name': 'Kho nguyên liệu', 'company_id': factory.id})
qc_in = PK.create({'kind': 'in', 'purpose': 'purchase', 'date': date(2027, 2, 1), 'warehouse_id': wh_qc.id,
                   'partner_id': vendor2.id, 'invoice_symbol': 'C27TAA', 'invoice_number': '0000011',
                   'line_ids': [(0, 0, {'product_id': qc_prod.id, 'lot_name': 'Y1', 'expiry_date': date(2028, 2, 1),
                                        'quantity': 10, 'price_unit': 20_000_000}),
                                (0, 0, {'product_id': qc_prod.id, 'lot_name': 'Y2', 'expiry_date': date(2028, 2, 1),
                                        'quantity': 5, 'price_unit': 20_000_000})]})
qc_in.action_done()
chk = qc_in.qc_check_ids
y1 = chk.filtered(lambda c: c.lot_id.name == 'Y1')
y2 = chk.filtered(lambda c: c.lot_id.name == 'Y2')
check('Nhập mua hàng cần kiểm tra: mỗi lô một phiếu KTCL theo bộ chỉ tiêu, lô bị cách ly chờ kiểm tra',
      len(chk) == 2 and y1.name.startswith('KTCL') and len(y1.line_ids) == 2 and y1.lot_id.hold
      and 'Chờ kiểm tra' in y1.lot_id.hold_reason, (len(chk), y1.lot_id.hold))
try:
    PK.create({'kind': 'out', 'purpose': 'internal', 'date': date(2027, 2, 2), 'warehouse_id': wh_qc.id,
               'line_ids': [(0, 0, {'product_id': qc_prod.id, 'quantity': 1})]}).action_done()
    check('Lô chưa kiểm tra không xuất dùng được', False)
except UserError:
    check('Lô chưa kiểm tra không xuất dùng được', True)
CHK_DIR = env['lfood.qc.check'].with_user(users['giamdoc']).with_company(factory)
y1.write({'inspector': 'Nhân viên QC', 'line_ids': [(1, l.id, {'result': 'Đạt', 'passed': True}) for l in y1.line_ids]})
try:
    y1.action_pass(); check('Kế toán viên không kết luận kiểm tra', False)
except UserError:
    check('Kế toán viên không kết luận kiểm tra', True)
CHK_DIR.browse(y1.id).action_pass()
check('Đạt: giải phóng lô Y1', y1.state == 'passed' and not y1.lot_id.hold)
y2.write({'inspector': 'Nhân viên QC', 'line_ids': [(1, y2.line_ids[0].id, {'result': 'Đạt', 'passed': True}),
                                                   (1, y2.line_ids[1].id, {'result': '18%', 'passed': False})]})
try:
    CHK_DIR.browse(y2.id).action_pass(); check('Có chỉ tiêu không đạt thì không kết luận Đạt được', False)
except UserError:
    check('Có chỉ tiêu không đạt thì không kết luận Đạt được', True)
y2.write({'conclusion': 'Độ ẩm 18% vượt yêu cầu, đề nghị trả nhà cung cấp'})
CHK_DIR.browse(y2.id).action_fail()
act = y2.action_ids
check('Không đạt: lô Y2 vẫn cách ly, mở hành động khắc phục hạn 7 ngày',
      y2.state == 'failed' and y2.lot_id.hold and 'Không đạt' in y2.lot_id.hold_reason
      and act.deadline == date(2027, 2, 8) and act.state == 'open', (y2.state, act.deadline))
REM._cron_refresh(today=date(2027, 2, 5))
check('Nhắc hạn hành động khắc phục', REM.search_count([('category', '=', 'quality'), ('res_id', '=', act.id),
                                                       ('res_model', '=', 'lfood.qc.action'), ('state', '=', 'open')]) == 1)
try:
    act.action_done(); check('Đóng hành động phải ghi biện pháp, người phụ trách', False)
except UserError:
    check('Đóng hành động phải ghi biện pháp, người phụ trách', True)
act.write({'measure': 'Trả lại nhà cung cấp, yêu cầu phiếu kiểm nghiệm độ ẩm từng lô', 'responsible': 'Trưởng kho'})
act.action_done()
check('Đóng hành động khắc phục', act.state == 'done' and act.done_on)
p_ret = PK.create({'kind': 'out', 'purpose': 'return_out', 'date': date(2027, 2, 6), 'warehouse_id': wh_qc.id,
                   'partner_id': vendor2.id, 'line_ids': [(0, 0, {'product_id': qc_prod.id, 'lot_id': y2.lot_id.id,
                                                                   'quantity': 5})]})
p_ret.action_done()
check('Lô cách ly vẫn trả được nhà cung cấp', p_ret.state == 'done')

# ---- lịch nghỉ lễ, Tết
HOL = env['lfood.holiday']
check('Lịch nghỉ 2026 có Tết Dương lịch, 5 ngày Tết Âm lịch, 30/4, 1/5',
      HOL.search_count([('year', '=', 2026)]) >= 8 and HOL.search_count([('date', '=', date(2026, 4, 30))]) == 1)
check('Hai ngày làm việc sau thứ Tư 29/4/2026 là thứ Ba 5/5 (bỏ 30/4, 1/5, cuối tuần)',
      HOL.add_working_days(date(2026, 4, 29), 2) == date(2026, 5, 5), HOL.add_working_days(date(2026, 4, 29), 2))
HOL.with_user(users['ketoanvien']).create({'date': date(2027, 2, 8), 'name': 'Tết Âm lịch Đinh Mùi', 'legal_ref': 'Thông báo nghỉ Tết 2027'})
check('Ngày nghỉ kế toán nhập thêm được tính vào hạn phản hồi yêu cầu dữ liệu cá nhân',
      REQ.create({'subject_kind': 'other', 'subject_name': 'Khách thử', 'kind': 'access', 'detail': 'x',
                  'received_on': date(2027, 2, 5), 'company_id': factory.id}).respond_by == date(2027, 2, 10))

# ---- đăng nhập an toàn
ICP = env['ir.config_parameter'].sudo()
check('Mặc định: khóa tạm sau 5 lần sai 15 phút, tự đăng xuất sau 30 phút, mật khẩu từ 10 ký tự',
      (ICP.get_param('base.login_cooldown_after'), ICP.get_param('base.login_cooldown_duration'),
       ICP.get_param('sessions.max_inactivity_seconds'), ICP.get_param('auth_password_policy.minlength'))
      == ('5', '900', '1800', '10'))
SEC = env['lfood.security.settings'].with_user(env.ref('base.user_admin'))
sec = SEC.create({})
check('Màn hình cấu hình đọc đúng số phút và liệt kê người chưa bật mã 2 lớp',
      (sec.cooldown_minutes, sec.inactivity_minutes) == (15, 30) and 'ketoanvien' in sec.no_totp_html)
sec.write({'inactivity_minutes': 20})
try:
    SEC.create({'inactivity_minutes': 1}).action_apply(); check('Chặn tự đăng xuất dưới 5 phút', False)
except UserError:
    check('Chặn tự đăng xuất dưới 5 phút', True)
sec.action_apply()
check('Lưu cấu hình, ghi nhật ký', ICP.get_param('sessions.max_inactivity_seconds') == '1200' and Log.sudo().search_count(
    [('action', '=', 'config'), ('summary', 'ilike', 'đăng nhập')]) >= 1)
try:
    env['lfood.security.settings'].with_user(users['ketoantruong']).create({}); check('Kế toán trưởng không sửa cấu hình đăng nhập', False)
except AccessError:
    check('Kế toán trưởng không sửa cấu hình đăng nhập', True)
ICP.set_param('sessions.max_inactivity_seconds', '1800')

# ---- lưu trữ chứng từ điện tử
DOC = env['lfood.document'].with_user(users['ketoanvien']).with_company(factory)
doc = DOC.create({'name': 'Hóa đơn mua yến thô 0000011', 'doc_type': 'invoice', 'doc_date': date(2027, 2, 1),
                  'ref': 'C27TAA 0000011', 'res_ref': 'lfood.stock.picking,%s' % qc_in.id, 'company_id': factory.id,
                  'file': _b64.b64encode(b'%PDF-1.4 hoa don'), 'file_name': 'hd0000011.pdf'})
check('Lưu chứng từ ghi sổ: lưu đến 31/12/2037, có mã SHA-256, tệp nguyên vẹn, gắn phiếu nhập',
      doc.retain_until == date(2037, 12, 31) and len(doc.checksum) == 64 and doc.intact and doc.res_ref == qc_in,
      (doc.retain_until, doc.checksum, doc.intact))
try:
    doc.write({'file': _b64.b64encode(b'sua')}); check('Không thay tệp đã lưu trữ', False)
except UserError:
    check('Không thay tệp đã lưu trữ', True)
try:
    doc.write({'policy_id': ref('lfood_archive.policy_management').id}); check('Không rút ngắn thời hạn lưu trữ', False)
except UserError:
    check('Không rút ngắn thời hạn lưu trữ', True)
try:
    doc.unlink(); check('Không xóa hồ sơ trong thời hạn lưu trữ', False)
except UserError:
    check('Không xóa hồ sơ trong thời hạn lưu trữ', True)
att = env['ir.attachment'].sudo().search([('res_model', '=', 'lfood.document'), ('res_id', '=', doc.id),
                                          ('res_field', '=', 'file')])
check('Tệp lưu trữ nằm trong tệp đính kèm của hồ sơ', len(att) == 1)
try:
    att.unlink(); check('Không xóa trực tiếp tệp đính kèm của hồ sơ còn hạn', False)
except UserError:
    check('Không xóa trực tiếp tệp đính kèm của hồ sơ còn hạn', True)
old_doc = DOC.create({'name': 'Tài liệu cũ', 'doc_type': 'other', 'doc_date': date(2015, 3, 1), 'company_id': factory.id,
                      'policy_id': ref('lfood_archive.policy_management').id,
                      'file': _b64.b64encode(b'cu'), 'file_name': 'cu.txt'})
old_doc.unlink()
check('Hồ sơ đã hết hạn lưu trữ (5 năm từ 2015) được hủy, nhật ký ghi lại',
      not old_doc.exists() and Log.sudo().search_count([('model', '=', 'lfood.document'), ('action', '=', 'unlink')]) >= 1)

# ---- điều chuyển, kỷ luật, phòng ban
dept_qa = env['lfood.department'].with_user(users['ketoanvien']).create(
    {'code': 'QA', 'name': 'Phòng Quản lý chất lượng', 'company_id': factory.id})
TRF = env['lfood.hr.transfer'].with_user(users['ketoanvien']).with_company(factory)
basic_hr = e_hr._basic_salary()
t1 = TRF.create({'employee_id': e_hr.id, 'kind': 'temporary', 'reason': 'Thiếu người kiểm kê cuối quý',
                 'notice_date': date(2027, 3, 1), 'date_from': date(2027, 3, 3), 'date_to': date(2027, 4, 30),
                 'new_job': 'Nhân viên kiểm kê', 'new_salary': 8_000_000})
check('Điều chuyển ghi lại công việc, lương cũ; cấp số DCNS; đếm 43 ngày làm việc',
      t1.name.startswith('DCNS') and t1.old_salary == basic_hr == 10_400_000 and t1.work_days == 43,
      (t1.name, t1.old_salary, t1.work_days))
for label, vals in [('Tạm chuyển phải báo trước ít nhất 3 ngày làm việc', {}),
                    ('Lương công việc mới phải ít nhất 85% lương cũ', {'notice_date': date(2027, 2, 26)}),
                    ('Lương mới không thấp hơn lương tối thiểu vùng', {'new_salary': 1_000_000, 'kind': 'permanent'})]:
    t1.write(vals)
    try:
        t1.action_done(); check(label, False)
    except ValidationError:
        check(label, True)
t1.write({'kind': 'temporary', 'new_salary': 9_000_000})
t1.action_done()
env.invalidate_all()
check('Tạm chuyển lương thấp hơn: giữ lương cũ 30 ngày làm việc, chưa đổi lương cơ bản',
      t1.state == 'done' and t1.keep_old_until and e_hr._basic_salary() == 10_400_000 and e_hr.job == 'Nhân viên kiểm kê',
      (t1.keep_old_until, e_hr._basic_salary()))
t2 = TRF.create({'employee_id': e_hr.id, 'kind': 'temporary', 'reason': 'Mùa cao điểm', 'notice_date': date(2027, 5, 20),
                 'date_from': date(2027, 6, 1), 'date_to': date(2027, 7, 30), 'new_job': 'Nhân viên kho',
                 'new_salary': 10_400_000})
try:
    t2.action_done(); check('Quá 60 ngày làm việc trong năm phải có văn bản đồng ý', False)
except ValidationError as err:
    check('Quá 60 ngày làm việc trong năm phải có văn bản đồng ý', '87' in str(err), str(err)[:80])
t2.write({'consent': True, 'consent_file': _b64.b64encode(b'dong y'), 'consent_name': 'dongy.pdf'})
t2.action_done()
check('Có văn bản đồng ý thì tạm chuyển tiếp được', t2.state == 'done')
t3 = TRF.create({'employee_id': e_hr.id, 'kind': 'permanent', 'reason': 'Bổ nhiệm', 'date_from': date(2027, 8, 1),
                 'new_department_id': dept_qa.id, 'new_job': 'Trưởng nhóm QA', 'new_salary': 12_000_000})
try:
    t3.action_done(); check('Điều chỉnh lâu dài phải có phụ lục hợp đồng', False)
except ValidationError:
    check('Điều chỉnh lâu dài phải có phụ lục hợp đồng', True)
t3.write({'consent': True, 'consent_file': _b64.b64encode(b'phu luc'), 'consent_name': 'phuluc.pdf'})
t3.action_done()
env.invalidate_all()
check('Bổ nhiệm: cập nhật phòng ban, chức danh, lương cơ bản 12 triệu',
      e_hr.department_id == dept_qa and e_hr.department == dept_qa.name and e_hr._basic_salary() == 12_000_000)
DSC = env['lfood.hr.discipline'].with_user(users['ketoanvien']).with_company(factory)
dsc = DSC.create({'employee_id': e_hr.id, 'violation_date': date(2027, 1, 10), 'violation': 'Đi muộn nhiều lần',
                  'meeting_date': date(2027, 8, 1), 'decision_ref': '05/QĐ-KL', 'decision_date': date(2027, 8, 1),
                  'employee_attended': True, 'minutes': _b64.b64encode(b'bien ban'), 'minutes_name': 'bb.pdf',
                  'form': 'delay', 'delay_months': 7})
check('Thời hiệu kỷ luật 6 tháng: hết ngày 10/07/2027', dsc.name.startswith('KLLD') and dsc.deadline == date(2027, 7, 10))
DSC_DIR = env['lfood.hr.discipline'].with_user(users['giamdoc']).with_company(factory)
try:
    dsc.action_decide(); check('Kế toán viên không ra quyết định kỷ luật', False)
except UserError:
    check('Kế toán viên không ra quyết định kỷ luật', True)
for label, vals in [('Họp kỷ luật phải có tổ chức đại diện người lao động', {}),
                    ('Chặn xử lý khi đã hết thời hiệu', {'union_attended': True}),
                    ('Kéo dài nâng lương không quá 6 tháng', {'decision_date': date(2027, 3, 1), 'meeting_date': date(2027, 3, 1)}),
                    ('Sa thải phải chọn trường hợp luật định', {'form': 'dismiss'})]:
    dsc.write(vals)
    try:
        DSC_DIR.browse(dsc.id).action_decide(); check(label, False)
    except ValidationError:
        check(label, True)
dsc.write({'finance_related': False, 'form': 'reprimand'})
DSC_DIR.browse(dsc.id).action_decide()
check('Ra quyết định khiển trách, nhật ký ghi lại', dsc.state == 'decided' and Log.sudo().search_count(
    [('model', '=', 'lfood.hr.discipline'), ('res_id', '=', dsc.id)]) >= 1)
fin_dsc = DSC.create({'employee_id': e_hr.id, 'violation_date': date(2027, 1, 10), 'violation': 'Làm mất tiền quỹ',
                      'finance_related': True})
check('Vi phạm liên quan tài sản: thời hiệu 12 tháng', fin_dsc.deadline == date(2028, 1, 10))

# ---- báo cáo tình hình thay đổi lao động
LR = env['lfood.labor.report'].with_user(users['ketoanvien']).with_company(factory)
lr = LR.create({'year': 2026, 'period': 'year', 'company_id': factory.id})
lr.action_compute()
emp_f = env['lfood.employee'].sudo().with_context(active_test=False).search([('company_id', '=', factory.id),
                                                                            ('date_start', '!=', False)])
exp_end = len(emp_f.filtered(lambda e: e.date_start <= date(2026, 12, 31) and (not e.date_end or e.date_end > date(2026, 12, 31))))
exp_in = len(emp_f.filtered(lambda e: date(2026, 1, 1) <= e.date_start <= date(2026, 12, 31)))
check('Báo cáo lao động năm 2026: hạn 05/12, đầu kỳ + tăng - giảm = cuối kỳ, có danh sách',
      lr.due_date == date(2026, 12, 5) and lr.count_end == exp_end and lr.count_in == exp_in
      and lr.count_start + lr.count_in - lr.count_out == lr.count_end and 'Mã số BHXH' in lr.html and e_hr.name in lr.html,
      (lr.count_start, lr.count_in, lr.count_out, lr.count_end, exp_end))
REM._cron_refresh(today=date(2026, 11, 20))
check('Nhắc hạn nộp báo cáo lao động năm', REM.search_count([('key', '=', 'laborrep-%s-2026-year' % factory.id),
                                                          ('state', '=', 'open')]) == 1)
lr.write({'receipt_ref': 'HS-2026-0001'})
lr.action_submitted()
REM._cron_refresh(today=date(2026, 11, 21))
check('Đã nộp thì việc nhắc tự đóng', lr.submitted_on and REM.search_count(
    [('key', '=', 'laborrep-%s-2026-year' % factory.id), ('state', '=', 'open')]) == 0)

# ---- ốm đau, thai sản
BEN = env['lfood.hr.benefit'].with_user(users['ketoanvien']).with_company(factory)
e_ben = EMP.create({'code': 'NVBH01', 'name': 'Chị Lan thử bảo hiểm', 'company_id': factory.id, 'region': 'I',
                    'date_start': date(2024, 1, 1), 'insurance_salary': 8_000_000, 'gender': 'female'})
cert = _b64.b64encode(b'giay chung nhan')
s1 = BEN.create({'employee_id': e_ben.id, 'kind': 'sick', 'date_from': date(2027, 3, 1), 'date_to': date(2027, 3, 5),
                 'years_paid': 3, 'certificate': cert, 'certificate_name': 'gcn.pdf'})
check('Ốm 5 ngày làm việc, lương đóng 8 triệu: 8.000.000 x 75% / 24 x 5 = 1.250.000, tối đa 30 ngày',
      s1.name.startswith('BHXH') and (s1.days, s1.amount, s1.limit_days) == (5, 1_250_000, 30), (s1.days, s1.amount, s1.limit_days))
b3383, b334 = net('3383'), net('334', partner_id=e_ben.partner_id.id)
s1.action_post()
check('Ghi sổ Nợ 3383 / Có 334 theo người lao động', net('3383') - b3383 == 1_250_000
      and net('334', partner_id=e_ben.partner_id.id) - b334 == -1_250_000)
s2 = BEN.create({'employee_id': e_ben.id, 'kind': 'sick', 'date_from': date(2027, 3, 8), 'date_to': date(2027, 4, 16),
                 'years_paid': 3, 'certificate': cert, 'certificate_name': 'gcn.pdf'})
try:
    s2.action_post(); check('Chặn ốm đau vượt 30 ngày trong năm', False)
except ValidationError as err:
    check('Chặn ốm đau vượt 30 ngày trong năm', '30' in str(err), str(err)[:80])
s2.write({'date_to': date(2027, 4, 9)})
s2.action_post()
rec_b = BEN.create({'employee_id': e_ben.id, 'kind': 'recovery', 'date_from': date(2027, 4, 12), 'date_to': date(2027, 4, 16),
                    'certificate': cert, 'certificate_name': 'x.pdf'})
ref_wage = env['lfood.legal.param'].get_value('LUONG_CO_SO', date(2027, 4, 12))
check('Dưỡng sức 5 ngày x 30% mức tham chiếu', rec_b.amount == round(ref_wage * 0.3 * 5) and ref_wage > 0,
      (rec_b.amount, ref_wage))
rec_b.action_post()
child = BEN.create({'employee_id': e_ben.id, 'kind': 'child_sick', 'date_from': date(2027, 5, 3), 'date_to': date(2027, 5, 4),
                    'child_birth': date(2020, 1, 1), 'certificate': cert, 'certificate_name': 'x.pdf'})
try:
    child.action_post(); check('Con từ 7 tuổi không hưởng chăm con ốm', False)
except ValidationError:
    check('Con từ 7 tuổi không hưởng chăm con ốm', True)
child.write({'child_birth': date(2025, 1, 1)})
check('Con dưới 3 tuổi: tối đa 20 ngày', child.limit_days == 20 and child.days == 2)
birth = BEN.create({'employee_id': e_ben.id, 'kind': 'birth', 'date_from': date(2027, 6, 1), 'date_to': date(2027, 11, 30),
                    'children': 1, 'salary_base': 8_000_000, 'certificate': cert, 'certificate_name': 'ks.pdf'})
check('Sinh con 6 tháng: 6 x 8.000.000 + trợ cấp 2 lần mức tham chiếu',
      birth.amount == 48_000_000 and birth.lump_sum == round(ref_wage * 2) and birth.total == birth.amount + birth.lump_sum)
birth.write({'date_to': date(2027, 12, 5)})
try:
    birth.action_post(); check('Nghỉ sinh một con tối đa 6 tháng', False)
except ValidationError:
    check('Nghỉ sinh một con tối đa 6 tháng', True)
male = BEN.create({'employee_id': e_hr.id, 'kind': 'male_birth', 'date_from': date(2027, 6, 1), 'date_to': date(2027, 6, 10),
                   'surgery': True, 'certificate': cert, 'certificate_name': 'x.pdf'})
try:
    male.action_post(); check('Nam nghỉ khi vợ sinh phẫu thuật tối đa 7 ngày làm việc', False)
except ValidationError:
    check('Nam nghỉ khi vợ sinh phẫu thuật tối đa 7 ngày làm việc', male.days == 8, male.days)
male.write({'date_to': date(2027, 6, 9 - 2)})
check('Nam nghỉ khi vợ sinh: sửa đến 07/6 còn 5 ngày làm việc', male.days == 5 and male.limit_days == 7,
      (male.days, male.limit_days))

# ---- người phụ thuộc
check('Chưa có sổ người phụ thuộc thì dùng số nhập tay', e_ben._dependents_in(date(2027, 3, 1), date(2027, 3, 31)) == e_ben.dependents)
DEP = env['lfood.dependent'].with_user(users['ketoanvien'])
DEP.create({'employee_id': e_ben.id, 'name': 'Bé An', 'relation': 'child', 'id_number': '8000000001',
            'date_from': date(2027, 3, 15), 'registered': True})
DEP.create({'employee_id': e_ben.id, 'name': 'Bà Hoa', 'relation': 'parent', 'id_number': '8000000002',
            'date_from': date(2026, 1, 1), 'date_to': date(2027, 2, 28), 'registered': True})
DEP.create({'employee_id': e_ben.id, 'name': 'Chưa đăng ký', 'relation': 'child', 'id_number': '8000000003',
            'date_from': date(2026, 1, 1)})
check('Tháng 2/2027: 1 người (bà Hoa); tháng 3/2027: 1 người (bé An từ tháng 3); người chưa đăng ký không tính',
      (e_ben._dependents_in(date(2027, 2, 1), date(2027, 2, 28)), e_ben._dependents_in(date(2027, 3, 1), date(2027, 3, 31)))
      == (1, 1))
env.flush_all()
env.cr.execute('SAVEPOINT dep_dup')
try:
    DEP.create({'employee_id': e_hr.id, 'name': 'Bé An', 'relation': 'child', 'id_number': '8000000001',
                'date_from': date(2027, 6, 1), 'registered': True})
    env.flush_all()
    check('Một người phụ thuộc không tính cho hai người nộp thuế cùng lúc', False)
except ValidationError:
    check('Một người phụ thuộc không tính cho hai người nộp thuế cùng lúc', True)
env.cr.execute('ROLLBACK TO SAVEPOINT dep_dup')
env.clear()

# ---- công bố sản phẩm, kiểm nghiệm định kỳ, sức khỏe người sản xuất
ic_prod.sudo().write({'declaration_required': True, 'lab_test_months': 6})
LT = env['lfood.lab.test'].with_user(users['ketoanvien']).with_company(factory)
old_test = LT.create({'name': 'KN-2025-01', 'product_id': ic_prod.id, 'lab': 'Trung tâm kiểm nghiệm thử', 'lab_iso17025': True,
                      'date': date(2025, 12, 1), 'file': _b64.b64encode(b'kn'), 'file_name': 'kn.pdf', 'company_id': factory.id})
DECL = env['lfood.product.declaration'].with_user(users['ketoanvien']).with_company(factory)
d1 = DECL.create({'name': 'TCB-001/2027', 'product_id': ic_prod.id, 'kind': 'standard', 'date_submitted': date(2027, 2, 1),
                  'lab_test_id': old_test.id, 'company_id': factory.id,
                  'dossier': _b64.b64encode(b'hs'), 'dossier_name': 'hs.pdf', 'label': _b64.b64encode(b'nhan'), 'label_name': 'nhan.pdf'})
try:
    d1.action_submit(); check('Phiếu kiểm nghiệm quá 12 tháng thì không nộp được hồ sơ công bố', False)
except ValidationError:
    check('Phiếu kiểm nghiệm quá 12 tháng thì không nộp được hồ sơ công bố', True)
new_test = LT.create({'name': 'KN-2027-01', 'product_id': ic_prod.id, 'lab': 'Trung tâm kiểm nghiệm thử', 'lab_iso17025': True,
                      'date': date(2027, 1, 15), 'file': _b64.b64encode(b'kn2'), 'file_name': 'kn2.pdf', 'company_id': factory.id})
d1.write({'lab_test_id': new_test.id})
d1.action_submit()
try:
    d1.action_publish(); check('Chưa có ngày đăng tải thì chưa được kinh doanh', False)
except UserError:
    check('Chưa có ngày đăng tải thì chưa được kinh doanh', True)
d1.write({'date_published': date(2027, 2, 16)})
d1.action_publish()
check('Hồ sơ công bố tiêu chuẩn được đăng tải: sản phẩm có hồ sơ hiệu lực từ 16/02/2027',
      ic_prod._declaration_valid(date(2027, 3, 1)) == d1 and not ic_prod._declaration_valid(date(2027, 2, 10)))
legacy = DECL.create({'name': 'TCB-cu', 'product_id': so_prod.id, 'kind': 'legacy', 'date_submitted': date(2024, 5, 1),
                      'date_published': date(2024, 5, 1), 'company_id': factory.id})
check('Tự công bố cũ phải công bố lại trước 27/01/2027', legacy.deadline == date(2027, 1, 27) and legacy.valid_until == date(2027, 1, 27))
hq = DECL.create({'name': 'HQ-01', 'product_id': ic_prod.id, 'kind': 'conformity', 'date_submitted': date(2027, 3, 1),
                  'date_published': date(2027, 3, 10), 'certificate_until': date(2031, 1, 1), 'company_id': factory.id})
check('Công bố hợp quy hiệu lực không quá 3 năm', hq.valid_until == date(2030, 3, 9), hq.valid_until)
REM._cron_refresh(today=date(2027, 7, 20))
check('Nhắc kiểm nghiệm định kỳ 6 tháng sau lần 15/01/2027', REM.search_count(
    [('key', '=', 'labtest-%s-%s-2027-07-15' % (factory.id, ic_prod.id)), ('state', '=', 'open')]) == 1)
e_ben.write({'food_handler': True})
WC = env['lfood.worker.check'].with_user(users['ketoanvien'])
env.flush_all()
env.cr.execute('SAVEPOINT wc_bad')
try:
    WC.create({'employee_id': e_ben.id, 'kind': 'health', 'date': date(2027, 1, 5), 'valid_months': 18})
    env.flush_all()
    check('Khám sức khỏe định kỳ ít nhất 12 tháng một lần', False)
except ValidationError:
    check('Khám sức khỏe định kỳ ít nhất 12 tháng một lần', True)
env.cr.execute('ROLLBACK TO SAVEPOINT wc_bad')
env.clear()
WC.create({'employee_id': e_ben.id, 'kind': 'health', 'date': date(2026, 8, 20), 'valid_months': 12, 'result': 'Loại 1'})
REM._cron_refresh(today=date(2027, 7, 25))
check('Nhắc khám sức khỏe lại hạn 19/08/2027 và tập huấn an toàn thực phẩm chưa có',
      REM.search_count([('key', '=', 'worker-%s-health-2027-08-19' % e_ben.id), ('state', '=', 'open')]) == 1
      and REM.search_count([('key', '=like', 'worker-%s-food_safety-%%' % e_ben.id), ('state', '=', 'open')]) == 1)

# ---- hợp đồng mua khung, đánh giá nhà cung cấp
KV = users['ketoanvien']
HDK = env['lfood.purchase.contract'].with_user(KV).with_company(factory)
hdk = HDK.create({'partner_id': supplier.id, 'contract_ref': 'HD-01/2027', 'date_from': date(2027, 1, 1),
                  'date_to': date(2027, 12, 31), 'company_id': factory.id,
                  'line_ids': [(0, 0, {'product_id': nl.id, 'price': 19_000, 'qty_committed': 1000})]})
try:
    hdk.action_activate(); check('Hợp đồng khung cần bản ký mới hiệu lực', False)
except UserError:
    check('Hợp đồng khung cần bản ký mới hiệu lực', True)
hdk.write({'document': _b64.b64encode(b'%PDF hop dong'), 'document_name': 'hd.pdf'})
hdk.action_activate()
POC = env['lfood.purchase.order'].with_user(KV).with_company(factory)
po_c = POC.create({'partner_id': supplier.id, 'date': date(2027, 3, 1), 'contract_id': hdk.id, 'company_id': factory.id,
                   'line_ids': [(0, 0, {'product_id': nl.id, 'name': 'Gạo lứt', 'quantity': 100, 'price_unit': 20_000,
                                        'vat_rate_id': vat8.id})]})
try:
    po_c.action_confirm(); check('Đơn mua giá cao hơn hợp đồng khung bị chặn', False)
except UserError:
    check('Đơn mua giá cao hơn hợp đồng khung bị chặn', True)
po_c.action_apply_contract()
po_c.action_confirm()
check('Áp giá hợp đồng rồi xác nhận; hợp đồng ghi nhận số đã đặt',
      po_c.state == 'confirmed' and po_c.line_ids.price_unit == 19_000 and hdk.line_ids.qty_ordered == 100,
      (po_c.state, po_c.line_ids.price_unit, hdk.line_ids.qty_ordered))
po_late = POC.create({'partner_id': supplier.id, 'date': date(2028, 1, 5), 'contract_id': hdk.id, 'company_id': factory.id,
                      'line_ids': [(0, 0, {'product_id': nl.id, 'name': 'Gạo lứt', 'quantity': 1, 'price_unit': 19_000})]})
try:
    po_late.action_confirm(); check('Đơn mua ngoài thời hạn hợp đồng bị chặn', False)
except UserError:
    check('Đơn mua ngoài thời hạn hợp đồng bị chặn', True)
try:
    hdk.write({'date_to': date(2028, 12, 31)}); check('Hợp đồng đã hiệu lực không sửa điều khoản', False)
except UserError:
    check('Hợp đồng đã hiệu lực không sửa điều khoản', True)

EV = env['lfood.supplier.evaluation'].with_user(KV).with_company(factory)
ev = EV.create({'partner_id': vendor2.id, 'date_from': date(2027, 1, 1), 'date_to': date(2027, 2, 28),
                'company_id': factory.id})
ev.action_compute()
check('Đánh giá NCC: 1/2 lô đạt KTCL, chưa có đơn thì giao hàng 100%, tổng 74 điểm, chấp thuận có điều kiện',
      (ev.quality_rate, ev.on_time_rate, ev.score, ev.result) == (50, 100, 74, 'conditional'),
      (ev.quality_rate, ev.on_time_rate, ev.score, ev.result))
try:
    ev.action_done(); check('Không đạt chấp thuận thì phải ghi yêu cầu khắc phục', False)
except UserError:
    check('Không đạt chấp thuận thì phải ghi yêu cầu khắc phục', True)
ev.write({'note': 'Yêu cầu kiểm soát độ ẩm trước khi giao'})
ev.action_done()
check('Kết luận đánh giá cập nhật trạng thái nhà cung cấp', vendor2.lfood_supplier_status == 'conditional')
env.flush_all()
env.cr.execute('SAVEPOINT ev_w')
try:
    EV.create({'partner_id': vendor2.id, 'date_from': date(2027, 1, 1), 'date_to': date(2027, 2, 28),
               'company_id': factory.id, 'weight_price': 50})
    env.flush_all()
    check('Tổng trọng số khác 100% bị chặn', False)
except ValidationError:
    check('Tổng trọng số khác 100% bị chặn', True)
env.cr.execute('ROLLBACK TO SAVEPOINT ev_w')
env.clear()
ev2 = EV.create({'partner_id': vendor2.id, 'date_from': date(2027, 1, 1), 'date_to': date(2027, 2, 28),
                 'company_id': factory.id, 'price_score': 20, 'service_score': 20, 'note': 'Loại'})
ev2.action_compute()
ev2.action_done()
po_rej = POC.create({'partner_id': vendor2.id, 'date': date(2027, 3, 2), 'company_id': factory.id,
                     'line_ids': [(0, 0, {'name': 'Yến thô', 'quantity': 1, 'price_unit': 1_000})]})
try:
    po_rej.action_confirm(); check('Nhà cung cấp bị loại (56 điểm) không đặt hàng được', False)
except UserError:
    check('Nhà cung cấp bị loại (56 điểm) không đặt hàng được', ev2.score == 56 and ev2.result == 'rejected', ev2.score)

# ---- hợp đồng nhà phân phối, trade marketing
npp = env['res.partner'].create({'name': 'Nhà phân phối kiểm thử', 'is_company': True})
for num, kind, lines in [('00000901', 'invoice', [(300_000_000, vat8), (100_000_000, kct)]),
                         ('00000902', 'refund', [(20_000_000, vat8)])]:
    vals = {'kind': kind, 'partner_id': npp.id, 'date': date(2027, 4, 10), 'invoice_template': '1',
            'invoice_symbol': 'C27TNP', 'invoice_number': num, 'company_id': factory.id,
            'line_ids': [(0, 0, {'name': 'Cháo hũ', 'quantity': 1, 'price_unit': a, 'vat_rate_id': r.id}) for a, r in lines]}
    if kind == 'refund':
        vals['origin_id'] = npp_inv.id
    rec = SI.create(vals)
    rec.action_post()
    if kind == 'invoice':
        npp_inv = rec
DC = env['lfood.distributor.contract'].with_user(KV).with_company(factory)
dc = DC.create({'partner_id': npp.id, 'contract_ref': 'NPP-01', 'date_from': date(2027, 4, 1), 'date_to': date(2027, 6, 30),
                'company_id': factory.id,
                'tier_ids': [(0, 0, {'threshold': 200_000_000, 'rate': 1}), (0, 0, {'threshold': 350_000_000, 'rate': 2})]})
dc.action_activate()
dc.action_compute()
check('Doanh số NPP 380 triệu (trừ giảm giá) đạt bậc 2%, thưởng 7,6 triệu', (dc.revenue, dc.rate, dc.rebate) == (380_000_000, 2, 7_600_000),
      (dc.revenue, dc.rate, dc.rebate))
dc.action_settle()
rb = dc.refund_id
check('Quyết toán lập hóa đơn điều chỉnh giảm nháp tách theo thuế suất',
      rb.kind == 'refund' and rb.state == 'draft' and rb.origin_id == npp_inv
      and sorted(rb.line_ids.mapped('amount')) == [2_000_000, 5_600_000] and rb.amount_tax == 448_000,
      (rb.kind, rb.state, rb.line_ids.mapped('amount'), rb.amount_tax))
rb.write({'invoice_template': '1', 'invoice_symbol': 'C27TNP', 'invoice_number': '00000903'})
rb.action_post()
check('Chiết khấu thương mại ghi Nợ 521, 33311 / Có 1311',
      {(l.account_code, l.debit, l.credit) for l in Move._active_for(rb).line_ids}
      == {('521', 5_600_000, 0), ('521', 2_000_000, 0), ('33311', 448_000, 0), ('1311', 0, 8_048_000)},
      [(l.account_code, l.debit, l.credit) for l in Move._active_for(rb).line_ids])
try:
    dc.action_settle(); check('Không quyết toán thưởng hai lần', False)
except UserError:
    check('Không quyết toán thưởng hai lần', True)
TP = env['lfood.trade.program'].with_user(KV).with_company(factory)
tp = TP.create({'name': 'Trưng bày quầy kệ Q2', 'partner_id': npp.id, 'cost_item_id': item_buy.id, 'company_id': factory.id,
                'date_from': date(2027, 4, 1), 'date_to': date(2027, 6, 30), 'budget': 10_000_000})
tpay = {'kind': 'out', 'method': 'bank', 'purpose': 'expense', 'amount': 6_000_000, 'memo': 'Hỗ trợ trưng bày',
        'date': date(2027, 5, 5), 'company_id': factory.id, 'cash_account': '112', 'counterpart_account': '6418',
        'trade_program_id': tp.id}
tp1 = PayF.create(tpay)
tp1.action_post()
check('Chi trade marketing trừ ngân sách, khoản mục lấy theo chương trình',
      (tp.spent, tp.remaining, tp1.cost_item_id) == (6_000_000, 4_000_000, item_buy), (tp.spent, tp.remaining))
try:
    PayF.create(dict(tpay, amount=5_000_000)).action_post(); check('Chi vượt ngân sách chương trình bị chặn', False)
except UserError:
    check('Chi vượt ngân sách chương trình bị chặn', True)
try:
    PayF.create(dict(tpay, amount=1_000_000, date=date(2027, 7, 5))).action_post()
    check('Chi ngoài thời gian chương trình bị chặn', False)
except UserError:
    check('Chi ngoài thời gian chương trình bị chặn', True)

# ---- tính thử tham số mới, lịch sử và gói tham số
from odoo.addons.lfood_voucher.models.tools import num as _num
check('Định dạng số tham số', (_num(2530000), _num(10.5), _num(0.03)) == ('2.530.000', '10,5', '0,03'))
vung1 = env['lfood.legal.param'].search([('code', '=', 'LUONG_TOI_THIEU_VUNG_I')])
draft_v = env['lfood.legal.param.value'].with_user(users['ketoanvien']).create(
    {'param_id': vung1.id, 'value': 6_000_000, 'date_from': date(2026, 9, 1), 'legal_ref': 'Dự thảo'})
sl2 = run.slip_ids.filtered(lambda x: x.employee_id == e2)
before = (sl2.si_base, sl2.net, run.total_net)
SIM = env['lfood.payroll.simulation'].with_user(users['ketoanvien'])
sim = SIM.create({'run_id': run.id, 'value_ids': [(6, 0, draft_v.ids)]})
sim.action_simulate()
sl2.invalidate_recordset()
check('Tính thử lương tối thiểu vùng 6 triệu: người lương 4 triệu đóng BH nhiều hơn, thực lĩnh giảm, DN đóng thêm 23,5% x 690.000',
      sim.diff_net == -72_450 and sim.diff_employer == 162_150 and '5.310.000 → 6.000.000' in sim.result_html,
      (sim.diff_net, sim.diff_employer))
check('Tính thử không đổi bảng lương, mức tham số vẫn chờ duyệt',
      (sl2.si_base, sl2.net, run.total_net) == before and draft_v.state == 'draft'
      and env['lfood.legal.param'].get_value('LUONG_TOI_THIEU_VUNG_I', date(2026, 9, 30)) == 5_310_000)
draft_v.unlink()

import json as _json
TOOLS = env['lfood.param.tools'].with_user(users['ketoanvien'])
tool = TOOLS.create({'date': date(2026, 9, 17)})
check('Tra cứu tham số theo ngày: lương cơ sở 2.530.000 từ 01/07/2026',
      'LUONG_CO_SO' in tool.history_html and '2.530.000' in tool.history_html)
tool.action_export()
pkg = _json.loads(_b64.b64decode(tool.export_file))
check('Xuất gói tham số có toàn bộ tham số và các mức',
      pkg['format'] == 'lfood-legal-params' and len(pkg['params']) == env['lfood.legal.param'].search_count([]))
tool.write({'import_file': tool.export_file, 'import_name': 'goi.json'})
try:
    tool.action_import(); check('Kế toán viên không nhập gói tham số', False)
except UserError:
    check('Kế toán viên không nhập gói tham số', True)
pkg['params'].append({'code': 'THU_NGHIEM_GOI', 'name': 'Tham số thử', 'group': 'other', 'value_type': 'number',
                      'kind': 'policy', 'description': '', 'values': [
                          {'value': 1, 'date_from': '2027-01-01', 'date_to': None, 'legal_ref': '', 'note': '', 'state': 'approved'}]})
co_so = next(p for p in pkg['params'] if p['code'] == 'LUONG_CO_SO')
co_so['values'].append({'value': 2_800_000, 'date_from': '2027-07-01', 'date_to': None, 'legal_ref': 'Dự kiến',
                        'note': '', 'state': 'approved'})
tool_kt = env['lfood.param.tools'].with_user(users['ketoantruong']).create({
    'import_file': _b64.b64encode(_json.dumps(pkg).encode()), 'import_name': 'goi.json'})
tool_kt.action_import()
newp = env['lfood.legal.param'].search([('code', '=', 'THU_NGHIEM_GOI')])
check('Nhập gói: chỉ thêm tham số, mức chưa có, tất cả ở trạng thái chờ duyệt',
      'Đã thêm 1 tham số, 2 mức' in tool_kt.result and newp.value_ids.state == 'draft'
      and env['lfood.legal.param'].get_value('LUONG_CO_SO', date(2027, 8, 1)) == 2_530_000, tool_kt.result)
try:
    env['lfood.param.tools'].with_user(users['ketoantruong']).create(
        {'import_file': _b64.b64encode(b'{"x": 1}')}).action_import()
    check('Tệp không đúng định dạng bị từ chối', False)
except UserError:
    check('Tệp không đúng định dạng bị từ chối', True)

# ---- đối chiếu hóa đơn với cơ quan thuế
from odoo.addons.lfood_vat.models.einvoice_check import to_number as _tn, invoice_no as _ino
check('Đọc số tiền, số hóa đơn kiểu Việt Nam',
      (_tn('1.234.567'), _tn('1.234,5'), _tn('30000000'), _tn(12.0), _ino('C27TNP 00000901'), _ino(901.0))
      == (1234567, 1234.5, 30000000, 12, 901, 901))
npp.vat = '0312345678'
csv_text = """BẢNG KÊ HÓA ĐƠN BÁN RA
STT;Ký hiệu mẫu số;Ký hiệu hóa đơn;Số hóa đơn;Ngày lập;Thông tin người mua;;Tổng tiền chưa thuế;Tổng tiền thuế;Trạng thái hóa đơn
;;;;;MST người mua;Tên người mua;;;
1;1;C27TNP;00000901;10/04/2027;0312345678;NPP;400.000.000;24.000.000;Hóa đơn mới
2;1;C27TNP;00000902;10/04/2027;0312345678;NPP;20.000.000;1.500.000;Hóa đơn điều chỉnh
3;1;C27TNP;00000903;30/06/2027;0312345678;NPP;7.600.000;448.000;Hóa đơn đã bị hủy
4;1;C27TNP;00000904;15/05/2027;0312345678;NPP;1.000.000;80.000;Hóa đơn mới
5;1;C27TNP;00000905;15/08/2027;0312345678;NPP;1.000.000;80.000;Hóa đơn mới
"""
EC = env['lfood.einvoice.check'].with_user(users['ketoanvien']).with_company(factory)
ec = EC.create({'kind': 'out', 'date_from': date(2027, 4, 1), 'date_to': date(2027, 6, 30), 'company_id': factory.id,
                'import_file': _b64.b64encode(csv_text.encode('utf-8-sig')), 'import_name': 'banra.csv'})
ec.action_check()
res = {l.invoice_no: l.result for l in ec.line_ids if l.partner_vat == '0312345678'}
check('Đối chiếu bán ra: khớp, lệch thuế, hóa đơn đã hủy mà sổ vẫn ghi, cổng có sổ chưa ghi; ngoài kỳ bỏ qua',
      res == {901: 'match', 902: 'diff', 903: 'cancelled', 904: 'portal_only'}, (res, ec.summary))
l902 = ec.line_ids.filtered(lambda l: l.invoice_no == 902)
check('Dòng lệch hiện số cổng thuế và số sổ, mở được chứng từ',
      (l902.portal_tax, l902.book_tax, l902.partner_id) == (1_500_000, -1_600_000, npp)
      and l902.action_open_source()['res_model'] == 'lfood.sale.invoice', (l902.portal_tax, l902.book_tax))
npp.vat = False
ec.action_check()
check('Đối chiếu lại thay kết quả cũ; đối tác chưa có mã số thuế thì thành chênh lệch',
      not ec.line_ids.filtered(lambda l: l.partner_vat == '0312345678' and l.result == 'match')
      and ec.line_ids.filtered(lambda l: not l.partner_vat and l.result == 'book_only'))
import openpyxl as _ox
wbk = _ox.Workbook()
ws = wbk.active
ws.append(['DANH SÁCH HÓA ĐƠN'])
ws.append(['STT', 'Ký hiệu hóa đơn', 'Số hóa đơn', 'Ngày lập', 'MST người bán', 'Tên người bán', 'MST người mua',
           'Tổng tiền chưa thuế', 'Tổng tiền thuế', 'Trạng thái hóa đơn'])
ws.append([1, 'C27TXX', 77, date(2027, 4, 2), '0999999999', 'NCC lạ', '1102021113', 5_000_000, 400_000, 'Hóa đơn mới'])
_buf = __import__('io').BytesIO()
wbk.save(_buf)
ec_in = EC.create({'kind': 'in', 'date_from': date(2027, 4, 1), 'date_to': date(2027, 4, 30), 'company_id': factory.id,
                   'import_file': _b64.b64encode(_buf.getvalue()), 'import_name': 'muavao.xlsx'})
ec_in.action_check()
odd = ec_in.line_ids.filtered(lambda l: l.partner_vat == '0999999999')
check('Nhập Excel mua vào: nhận MST người bán (không lấy MST người mua), hóa đơn sổ chưa ghi',
      len(odd) == 1 and odd.result == 'portal_only' and odd.portal_base == 5_000_000
      and not ec_in.line_ids.filtered(lambda l: l.partner_vat == '1102021113'), ec_in.summary)
try:
    EC.create({'kind': 'in', 'date_from': date(2027, 4, 1), 'date_to': date(2027, 4, 30), 'company_id': factory.id,
               'import_file': _b64.b64encode('a;b\n1;2\n'.encode())}).action_check()
    check('Tệp không có cột Số hóa đơn bị từ chối', False)
except UserError:
    check('Tệp không có cột Số hóa đơn bị từ chối', True)

# ---- tạm ứng lương, thưởng, thuế TNCN vãng lai, quyết toán năm
EMPO = env['lfood.employee'].with_user(users['ketoanvien']).with_company(office)
q1 = EMPO.create({'code': 'QT01', 'name': 'Người quyết toán', 'region': 'I', 'insurance_salary': 40_000_000, 'dependents': 1,
                  'company_id': office.id, 'date_start': date(2027, 1, 1),
                  'component_line_ids': [(0, 0, {'component_id': basic.id, 'amount': 40_000_000})]})
q2 = EMPO.create({'code': 'QT02', 'name': 'Thời vụ quyết toán', 'region': 'I', 'insurance_salary': 0, 'contract_type': 'short',
                  'insurance_enrolled': False, 'unemployment_enrolled': False, 'company_id': office.id,
                  'component_line_ids': [(0, 0, {'component_id': basic.id, 'amount': 3_000_000})]})
SADV = env['lfood.salary.advance'].with_user(users['ketoanvien'])
sadv = SADV.create({'employee_id': q1.id, 'date': date(2028, 12, 10), 'amount': 10_000_000})
sadv.action_post()
check('Chi tạm ứng lương: Nợ 334 / Có 112', gl(office, '334', partner_id=q1.partner_id.id) == 10_000_000
      and sadv.state == 'posted')
env['lfood.hr.reward'].with_user(users['ketoanvien']).create(
    {'employee_id': q1.id, 'date': date(2028, 12, 20), 'reason': 'Hoàn thành kế hoạch năm', 'amount': 60_000_000})
RUNO = env['lfood.payroll.run'].with_user(users['ketoanvien']).with_company(office)
for m in range(1, 13):
    r = RUNO.create({'company_id': office.id, 'year': 2028, 'month': m})
    r.action_load_employees()
    if m == 12:
        dec = r
    else:
        r.with_user(users['ketoantruong']).action_post()
qs = dec.slip_ids.filtered(lambda s: s.employee_id == q1)
check('Bảng lương tháng 12 tự thêm thưởng 60 triệu và trừ tạm ứng lương 10 triệu',
      qs.gross == 100_000_000 and qs.other_deductions == 10_000_000 and sadv.slip_line_id.slip_id == qs
      and qs.pit == 12_730_000, (qs.gross, qs.other_deductions, qs.pit))
dec.action_load_extras()
check('Lấy lại tạm ứng, thưởng không thêm trùng', len(qs.line_ids) == 3, len(qs.line_ids))
try:
    sadv.action_cancel(); check('Tạm ứng đã trừ lương không hủy được', False)
except UserError:
    check('Tạm ứng đã trừ lương không hủy được', True)
dec.with_user(users['ketoantruong']).action_post()
dec.write({'pay_date': date(2028, 12, 31)})
dec.action_pay()
check('Sau chi lương tháng 12, công nợ 334 chỉ còn lương 11 tháng chưa chi (tạm ứng không ghi trùng)',
      gl(office, '334', partner_id=q1.partner_id.id) == -sum(env['lfood.payroll.slip'].search([('employee_id', '=', q1.id), ('run_id', '!=', dec.id)]).mapped('net')),
      gl(office, '334', partner_id=q1.partner_id.id))

FL = env['lfood.pit.freelance'].with_user(users['ketoanvien']).with_company(office)
fl_old = FL.new({'name': 'x', 'gross': 3_000_000, 'date': date(2026, 6, 30)})
fl_new = FL.new({'name': 'x', 'gross': 3_000_000, 'date': date(2026, 7, 1)})
fl_nr = FL.new({'name': 'x', 'gross': 1_000_000, 'date': date(2026, 7, 1), 'resident': False})
fl_rq = FL.new({'name': 'x', 'gross': 1_000_000, 'date': date(2026, 7, 1), 'requested': True})
check('Vãng lai 3 triệu: trước 01/7/2026 khấu trừ 10% (ngưỡng 2 triệu), từ 01/7/2026 không khấu trừ (ngưỡng 5 triệu); '
      'không cư trú 20%; cá nhân yêu cầu thì khấu trừ',
      (fl_old.tax, fl_new.tax, fl_nr.tax, fl_rq.tax) == (300_000, 0, 200_000, 100_000),
      (fl_old.tax, fl_new.tax, fl_nr.tax, fl_rq.tax))
ctv = env['res.partner'].create({'name': 'Cộng tác viên thử'})
fl = FL.create({'name': 'Thù lao thiết kế nhãn', 'partner_id': ctv.id, 'tax_code': '079000000001', 'gross': 8_000_000,
                'date': date(2028, 5, 5), 'company_id': office.id})
fl.action_post()
check('Chi 8 triệu: khấu trừ 800.000, Nợ 6428 / Có 3335, Có 112',
      {(l.account_code, l.debit, l.credit) for l in Move._active_for(fl).line_ids}
      == {('6428', 8_000_000, 0), ('3335', 0, 800_000), ('112', 0, 7_200_000)})
fl_c = FL.create({'name': 'Thù lao khảo sát', 'partner_id': ctv.id, 'tax_code': '079000000001', 'gross': 6_000_000,
                  'date': date(2028, 6, 5), 'company_id': office.id, 'commitment': True})
check('Có cam kết thì không khấu trừ', fl_c.tax == 0)
try:
    fl_c.action_post(); check('Cam kết phải đính kèm bản cam kết', False)
except UserError:
    check('Cam kết phải đính kèm bản cam kết', True)
fl_c.write({'commitment_file': _b64.b64encode(b'cam ket'), 'commitment_name': 'camket.pdf'})
fl_c.action_post()

ST = env['lfood.pit.settlement'].with_user(users['ketoanvien']).with_company(office)
st = ST.create({'year': 2028, 'company_id': office.id})
st.action_compute()
l1 = st.line_ids.filtered(lambda l: l.employee_id == q1)
l2 = st.line_ids.filtered(lambda l: l.employee_id == q2)
check('Quyết toán năm: thuế cả năm 16.920.000 theo biểu năm, đã khấu trừ 22.740.000, nộp thừa 5.820.000',
      (l1.months, l1.dependent_months, l1.tax, l1.withheld, l1.difference) == (12, 12, 16_920_000, 22_740_000, -5_820_000),
      (l1.months, l1.dependent_months, l1.tax, l1.withheld, l1.difference))
check('Hợp đồng dưới 03 tháng không đủ điều kiện ủy quyền', not l2.eligible and 'dưới 03 tháng' in l2.ineligible_reason)
env.flush_all()
env.cr.execute('SAVEPOINT st_auth')
try:
    l2.write({'authorized': True})
    env.flush_all()
    check('Không cho ủy quyền khi không đủ điều kiện', False)
except ValidationError:
    check('Không cho ủy quyền khi không đủ điều kiện', True)
env.cr.execute('ROLLBACK TO SAVEPOINT st_auth')
env.clear()
l1.write({'authorized': True})
st.action_compute()
l1 = st.line_ids.filtered(lambda l: l.employee_id == q1)
check('Tính lại giữ ủy quyền; tổng nộp thừa của người ủy quyền', l1.authorized and st.total_refund == 5_820_000, st.total_refund)
l1.write({'other_income': 240_000_000})
st.action_compute()
l1 = st.line_ids.filtered(lambda l: l.employee_id == q1)
check('Thu nhập nơi khác bình quân trên 15 triệu/tháng: không đủ điều kiện, bỏ ủy quyền',
      not l1.eligible and not l1.authorized and st.total_refund == 0)
check('Quyết toán có bảng thu nhập vãng lai theo cá nhân',
      '079000000001' in st.freelance_html and '14.000.000' in st.freelance_html and 'Có cam kết' in st.freelance_html)
check('Hạn nộp gợi ý 31/03 năm sau', st.due_date == date(2029, 3, 31))

# ---- tăng, giảm lao động đóng bảo hiểm
ICH = env['lfood.insurance.change'].with_user(users['ketoanvien']).with_company(office)
ich1 = ICH.create({'year': 2028, 'month': 1, 'company_id': office.id})
ich1.action_compute()
l_q1 = ich1.line_ids.filtered(lambda l: l.employee_id == q1)
check('Tháng đầu đóng bảo hiểm: báo tăng, chưa có mã số BHXH thì ghi chú; người không tham gia không có trong danh sách',
      l_q1.kind == 'increase' and l_q1.new_si == 40_000_000 and 'Chưa có mã số BHXH' in l_q1.note
      and not ich1.line_ids.filtered(lambda l: l.employee_id == q2), (l_q1.kind, l_q1.note))
ich2 = ICH.create({'year': 2028, 'month': 2, 'company_id': office.id})
ich2.action_compute()
check('Tháng không đổi thì không có dòng', not ich2.line_ids.filtered(lambda l: l.employee_id == q1))
q1.write({'insurance_salary': 45_000_000, 'social_insurance_code': '7900000001'})
r_j = RUNO.create({'company_id': office.id, 'year': 2029, 'month': 1})
r_j.action_load_employees()
ich3 = ICH.create({'year': 2029, 'month': 1, 'company_id': office.id})
ich3.action_compute()
l_q1 = ich3.line_ids.filtered(lambda l: l.employee_id == q1)
check('Đổi lương đóng bảo hiểm: điều chỉnh từ 40 triệu thành 45 triệu',
      (l_q1.kind, l_q1.old_si, l_q1.new_si) == ('adjust', 40_000_000, 45_000_000), (l_q1.kind, l_q1.old_si, l_q1.new_si))
r_f = RUNO.create({'company_id': office.id, 'year': 2029, 'month': 2})
r_f.action_load_employees()
r_f.slip_ids.filtered(lambda s: s.employee_id == q1).write({'skip_insurance': True, 'note': 'Nghỉ không lương cả tháng'})
r_f.action_compute()
ich4 = ICH.create({'year': 2029, 'month': 2, 'company_id': office.id})
ich4.action_compute()
l_q1 = ich4.line_ids.filtered(lambda l: l.employee_id == q1)
csv_out = _b64.b64decode(ich4.export_file).decode('utf-8-sig')
check('Nghỉ không lương cả tháng: báo giảm, có tệp CSV kèm mã số BHXH',
      l_q1.kind == 'decrease' and 'Nghỉ không lương' in l_q1.note and '7900000001' in csv_out and 'Giảm' in csv_out,
      (l_q1.kind, l_q1.note))
try:
    ICH.create({'year': 2031, 'month': 5, 'company_id': office.id}).action_compute()
    check('Tháng chưa có bảng lương thì báo lỗi', False)
except UserError:
    check('Tháng chưa có bảng lương thì báo lỗi', True)

# ---- ca làm việc, lịch phân ca
from odoo.addons.lfood_hr.models.shift import shift_hours as _sh
check('Giờ làm và giờ làm đêm của ca (22h-6h là giờ đêm)',
      [_sh(6, 14, 0), _sh(22, 6, 0), _sh(18, 2, 0), _sh(4, 12, 0), _sh(8, 17, 1)] == [(8, 0), (8, 8), (8, 4), (8, 2), (8, 0)])
SHIFT = env['lfood.hr.shift'].with_user(users['ketoanvien']).with_company(factory)
sh_a = SHIFT.create({'name': 'Ca 1', 'hour_start': 6, 'hour_end': 14, 'company_id': factory.id})
sh_c = SHIFT.create({'name': 'Ca 3', 'hour_start': 22, 'hour_end': 6, 'company_id': factory.id})
env.flush_all()
env.cr.execute('SAVEPOINT sh_long')
try:
    SHIFT.create({'name': 'Ca dài', 'hour_start': 6, 'hour_end': 16, 'company_id': factory.id})
    env.flush_all()
    check('Ca quá 8 giờ làm việc bị chặn', False)
except ValidationError:
    check('Ca quá 8 giờ làm việc bị chặn', True)
env.cr.execute('ROLLBACK TO SAVEPOINT sh_long')
env.clear()
f1 = EMP.create({'code': 'CA01', 'name': 'Công nhân ca', 'company_id': factory.id, 'region': 'III'})
ROS = env['lfood.hr.roster'].with_user(users['ketoanvien'])
mon = date(2029, 3, 5)
rows = ROS.create([{'employee_id': f1.id, 'date': mon + timedelta(days=i), 'shift_id': sh_a.id} for i in range(5)]
                  + [{'employee_id': f1.id, 'date': mon + timedelta(days=5), 'shift_id': sh_c.id}])
check('Tuần 6 ca, 48 giờ, chuyển từ ca 1 sang ca 3 nghỉ đủ 12 giờ', len(rows) == 6)


def _roster_blocked(vals):
    env.flush_all()
    env.cr.execute('SAVEPOINT ros_bad')
    try:
        ROS.create(vals)
        env.flush_all()
        ok = False
    except ValidationError:
        ok = True
    env.cr.execute('ROLLBACK TO SAVEPOINT ros_bad')
    env.clear()
    return ok


check('Ca thứ 7 trong tuần bị chặn (quá 48 giờ, không có ngày nghỉ tuần)',
      _roster_blocked({'employee_id': f1.id, 'date': mon + timedelta(days=6), 'shift_id': sh_a.id}))
ROS.create({'employee_id': f1.id, 'date': mon + timedelta(days=8), 'shift_id': sh_c.id})
check('Ca 3 kết thúc 6 giờ sáng rồi vào ca 1 lúc 6 giờ cùng ngày bị chặn (nghỉ dưới 12 giờ)',
      _roster_blocked({'employee_id': f1.id, 'date': mon + timedelta(days=9), 'shift_id': sh_a.id}))
wk = ROS.search([('employee_id', '=', f1.id)])
wk.action_to_attendance()
att_c = env['lfood.hr.attendance'].search([('employee_id', '=', f1.id), ('date', '=', mon + timedelta(days=5))])
check('Tạo chấm công từ lịch ca: ca 3 có 8 giờ làm đêm; bấm lại không tạo trùng',
      att_c.hours_normal == 8 and att_c.night_hours == 8 and len(wk.mapped('attendance_id')) == 7
      and wk.action_to_attendance()['params']['message'].startswith('Đã tạo 0'))

# ---- tai nạn lao động, huấn luyện an toàn
from odoo.addons.lfood_hr_records.models.safety import compensation_months as _cm
check('Tháng lương bồi thường tai nạn: 3% không bồi thường, 8% 1,5 tháng, 30% 9,5 tháng, 85% 30 tháng, lỗi người lao động 40%',
      (_cm(3, False, False), _cm(8, False, False), _cm(30, False, False), _cm(85, False, False), _cm(30, False, True))
      == (0, 1.5, 9.5, 30, 3.8))
ACC = env['lfood.hr.accident'].with_user(users['ketoanvien'])
tnld = ACC.create({'employee_id': f1.id, 'date': date(2029, 3, 6), 'place': 'Xưởng đóng gói', 'severity': 'serious',
                  'description': 'Kẹt tay ở máy dán nhãn', 'monthly_salary': 7_800_000, 'days_off': 13,
                  'medical_cost': 4_000_000, 'impairment': 30})
check('Tai nạn nặng, suy giảm 30%: lương điều trị 13 ngày 3.900.000, bồi thường 9,5 tháng 74.100.000',
      (tnld.salary_during_treatment, tnld.compensation_months, tnld.compensation) == (3_900_000, 9.5, 74_100_000),
      (tnld.salary_during_treatment, tnld.compensation_months, tnld.compensation))
try:
    tnld.action_close(); check('Tai nạn nặng phải khai báo trước khi đóng hồ sơ', False)
except UserError:
    check('Tai nạn nặng phải khai báo trước khi đóng hồ sơ', True)
tnld.write({'reported_on': date(2029, 3, 6), 'investigation_file': _b64.b64encode(b'bien ban'), 'investigation_name': 'bb.pdf'})
tnld.action_close()
AREP = env['lfood.hr.accident.report'].with_user(users['ketoanvien']).with_company(factory)
arep = AREP.create({'year': 2029, 'period': 'h1', 'company_id': factory.id})
arep.action_compute()
check('Báo cáo tai nạn 6 tháng: hạn 05/7, có số vụ và tiền bồi thường',
      arep.due_date == date(2029, 7, 5) and '74.100.000' in arep.content_html and 'Số người bị thương nặng' in arep.content_html)
env['lfood.hr.safety.training'].with_user(users['ketoanvien']).create({
    'employee_id': f1.id, 'group': '4', 'course': 'Huấn luyện an toàn vận hành máy', 'date': date(2028, 5, 1),
    'valid_until': date(2029, 5, 1)})
env['lfood.reminder']._cron_refresh(date(2029, 4, 20))
check('Nhắc chứng nhận huấn luyện sắp hết hạn và báo cáo tai nạn 6 tháng',
      env['lfood.reminder'].search_count([('key', '=like', 'safety-%'), ('state', '=', 'open'), ('title', 'ilike', f1.name)]) == 1
      and env['lfood.reminder'].search_count([('key', '=', 'accrep-%s-2029-h1' % factory.id)]) == 0)
env['lfood.reminder']._cron_refresh(date(2029, 6, 20))
check('Gần 05/7 thì nhắc nộp báo cáo tai nạn 6 tháng',
      env['lfood.reminder'].search_count([('key', '=', 'accrep-%s-2029-h1' % factory.id), ('state', '=', 'open')]) == 1)

# ---- hóa đơn điều chỉnh, thay thế (Thông tư 91/2026/TT-BTC Điều 10)
def _hd(num, amount, **kw):
    vals = {'partner_id': customer.id, 'date': date(2027, 7, 10), 'invoice_template': '1', 'invoice_symbol': 'C27TDC',
            'invoice_number': num, 'company_id': factory.id,
            'line_ids': [(0, 0, {'name': 'Cháo hũ', 'quantity': 1, 'price_unit': amount, 'vat_rate_id': vat8.id})]}
    vals.update(kw)
    return SI.create(vals)


def _post_fails(rec):
    try:
        rec.action_post()
        return False
    except UserError:
        return True


hd_a = _hd('00000001', 10_000_000)
hd_a.action_post()
up = _hd('00000002', 1_000_000, correction='adjust', origin_id=hd_a.id)
c1 = _post_fails(up)
up.write({'correction_reason': 'error'})
c2 = _post_fails(up)
up.write({'agreement_file': _b64.b64encode(b'thoa thuan'), 'agreement_name': 'tt.pdf'})
up.action_post()
hd_a.invalidate_recordset()
check('Điều chỉnh tăng: phải có lý do, người mua là tổ chức phải có văn bản thỏa thuận; ghi Có 511, công nợ gốc không bị trừ',
      c1 and c2 and up.state == 'posted' and gl(factory, '511', move_id=Move._active_for(up).id) == -1_000_000
      and hd_a.amount_residual == 10_800_000, (c1, c2, up.state, hd_a.amount_residual))
rp_a = _hd('00000003', 11_000_000, correction='replace', origin_id=hd_a.id, correction_reason='error',
           agreement_file=_b64.b64encode(b'tt'), agreement_name='tt.pdf')
check('Đã điều chỉnh sai sót thì không được chuyển sang thay thế (khoản 6 điểm a)', _post_fails(rp_a) and hd_a.state == 'posted')

hd_b = _hd('00000004', 20_000_000)
hd_b.action_post()
rcv_b = Pay.create({'kind': 'in', 'method': 'bank', 'purpose': 'customer', 'partner_id': customer.id, 'amount': 5_000_000,
                    'memo': 'Thu hóa đơn 4', 'date': date(2027, 7, 12), 'sale_invoice_id': hd_b.id, 'company_id': factory.id})
rcv_b.action_post()
rp_bad = _hd('00000005', 18_000_000, correction='replace', origin_id=hd_b.id, correction_reason='discount')
check('Chiết khấu, trả hàng không được lập hóa đơn thay thế', _post_fails(rp_bad))
rp_bad.unlink()
rp_b = _hd('00000006', 18_000_000, correction='replace', origin_id=hd_b.id, correction_reason='error',
           agreement_file=_b64.b64encode(b'tt'), agreement_name='tt.pdf')
rp_b.action_post()
hd_b.invalidate_recordset()
check('Thay thế: hóa đơn gốc Bị thay thế, bút toán gốc được đảo, số đã thu chuyển sang hóa đơn thay thế',
      hd_b.state == 'replaced' and not Move._active_for(hd_b) and rp_b.amount_paid == 5_000_000
      and rp_b.amount_residual == 19_440_000 - 5_000_000 and hd_b.amount_residual == 0,
      (hd_b.state, rp_b.amount_paid, rp_b.amount_residual))
fix_rp = _hd('00000007', 500_000, correction='adjust', origin_id=rp_b.id, correction_reason='error',
             agreement_file=_b64.b64encode(b'tt'), agreement_name='tt.pdf')
check('Hóa đơn thay thế có sai sót tiếp thì phải thay thế tiếp', _post_fails(fix_rp))
ret_old = SI.create({'kind': 'refund', 'origin_id': hd_b.id, 'partner_id': customer.id, 'date': date(2027, 7, 15),
                     'invoice_template': '1', 'invoice_symbol': 'C27TDC', 'invoice_number': '00000008', 'company_id': factory.id,
                     'line_ids': [(0, 0, {'name': 'Giảm giá', 'quantity': 1, 'price_unit': 100_000, 'vat_rate_id': vat8.id})]})
check('Không điều chỉnh hóa đơn đã bị thay thế', _post_fails(ret_old))
hd_a.write({'error_notice_note': 'Sai địa chỉ người mua'})
hd_a.action_error_notice()
check('Sai địa chỉ: ghi nhận thông báo 04/SS trên hóa đơn đã ghi sổ, không phải lập lại',
      hd_a.error_notice_date and hd_a.state == 'posted')
try:
    hd_a.write({'memo': 'sửa'}); check('Hóa đơn đã ghi sổ vẫn khóa các trường khác', False)
except UserError:
    check('Hóa đơn đã ghi sổ vẫn khóa các trường khác', True)
vr_b = env['lfood.vat.return'].sudo().new({'company_id': factory.id, 'period_type': 'month', 'year': 2027, 'month': 7})
refs = [v['ref'] for v in vr_b._sale_lines() if v.get('source_model') == 'lfood.sale.invoice']
check('Bảng kê bán ra không còn hóa đơn bị thay thế, có hóa đơn thay thế',
      'C27TDC 00000006' in refs and 'C27TDC 00000004' not in refs, refs)

# ---- thuê tài sản
from odoo.addons.lfood_accrual.models.lease import add_months as _am
check('Cộng tháng giữ ngày cuối tháng', (_am(date(2027, 1, 31), 1), _am(date(2027, 11, 15), 3)) == (date(2027, 2, 28), date(2028, 2, 15)))
LEASE = env['lfood.lease'].with_user(users['ketoanvien']).with_company(factory)
lessor = env['res.partner'].create({'name': 'Công ty cho thuê kho thử', 'is_company': True})
ls = LEASE.create({'name': 'Kho lạnh Tân Uyên', 'partner_id': lessor.id, 'contract_ref': 'HDT-01', 'company_id': factory.id,
                   'date_from': date(2029, 1, 1), 'date_to': date(2029, 10, 31), 'monthly_rent': 10_000_000, 'cycle': 6,
                   'deposit': 20_000_000})
try:
    ls.action_start(); check('Hợp đồng thuê phải có bản hợp đồng', False)
except UserError:
    check('Hợp đồng thuê phải có bản hợp đồng', True)
ls.write({'document': _b64.b64encode(b'hdt'), 'document_name': 'hdt.pdf'})
ls.action_start()
check('Lịch thanh toán 6 tháng rồi 4 tháng; ký quỹ Nợ 244',
      [(p.date, p.months, p.amount) for p in ls.period_ids] == [(date(2029, 1, 1), 6, 60_000_000), (date(2029, 7, 1), 4, 40_000_000)]
      and gl(factory, '244', partner_id=lessor.id) == 20_000_000, [(p.date, p.months) for p in ls.period_ids])
ls.period_ids[0].action_record()
pre = ls.period_ids[0].prepaid_id
check('Kỳ 6 tháng tạo chi phí trả trước 60 triệu, phân bổ 6 kỳ 10 triệu, Nợ 242 / Có 3311',
      pre.state == 'running' and len(pre.line_ids) == 6 and set(pre.line_ids.mapped('amount')) == {10_000_000}
      and gl(factory, '242', move_id=Move._active_for(pre).id) == 60_000_000, (pre.state, pre.line_ids.mapped('amount')))
env['lfood.reminder']._cron_refresh(date(2029, 6, 20))
check('Nhắc kỳ thanh toán tiền thuê sắp tới',
      env['lfood.reminder'].search_count([('key', '=', 'lease-pay-%s' % ls.period_ids[1].id), ('state', '=', 'open')]) == 1
      and not env['lfood.reminder'].search_count([('key', '=', 'lease-pay-%s' % ls.period_ids[0].id), ('state', '=', 'open')]))
ls.action_close()
check('Kết thúc thuê nhận lại ký quỹ', ls.state == 'closed' and gl(factory, '244', partner_id=lessor.id) == 0)

# ---- lãi gộp
wh_mg = WH.create({'code': 'KLG', 'name': 'Kho lãi gộp', 'company_id': factory.id})
mg_p1 = env['lfood.product'].with_user(users['ketoanvien']).with_company(factory).create(
    {'code': 'LG01', 'name': 'Cháo yến', 'uom': 'hũ', 'kind': 'goods', 'track_lot': False, 'brand': 'Yến Việt',
     'vat_rate_id': vat8.id, 'company_id': factory.id})
mg_p2 = env['lfood.product'].with_user(users['ketoanvien']).with_company(factory).create(
    {'code': 'LG02', 'name': 'Súp cua', 'uom': 'hũ', 'kind': 'goods', 'track_lot': False, 'brand': 'Biển Xanh',
     'vat_rate_id': vat8.id, 'company_id': factory.id})
PK.create({'kind': 'in', 'purpose': 'purchase', 'date': date(2029, 8, 1), 'warehouse_id': wh_mg.id, 'partner_id': vendor2.id,
           'invoice_symbol': 'C29TLG', 'invoice_number': '0000001',
           'line_ids': [(0, 0, {'product_id': mg_p1.id, 'quantity': 100, 'price_unit': 20_000}),
                        (0, 0, {'product_id': mg_p2.id, 'quantity': 100, 'price_unit': 10_000})]}).action_done()
mg_cust = env['res.partner'].create({'name': 'Siêu thị lãi gộp', 'is_company': True, 'lfood_channel_id': channel_mt.id})
mg_inv = SI.create({'partner_id': mg_cust.id, 'date': date(2029, 8, 5), 'invoice_template': '1', 'invoice_symbol': 'C29TLG',
                    'invoice_number': '00000101', 'warehouse_id': wh_mg.id, 'company_id': factory.id,
                    'line_ids': [(0, 0, {'name': 'Cháo yến', 'product_id': mg_p1.id, 'quantity': 10, 'price_unit': 30_000, 'vat_rate_id': vat8.id}),
                                 (0, 0, {'name': 'Súp cua', 'product_id': mg_p2.id, 'quantity': 20, 'price_unit': 15_000, 'vat_rate_id': vat8.id})]})
mg_inv.action_post()
mg_ret = SI.create({'kind': 'refund', 'origin_id': mg_inv.id, 'partner_id': mg_cust.id, 'date': date(2029, 8, 8),
                    'invoice_template': '1', 'invoice_symbol': 'C29TLG', 'invoice_number': '00000102', 'company_id': factory.id,
                    'correction_reason': 'return',
                    'line_ids': [(0, 0, {'name': 'Súp cua trả lại', 'product_id': mg_p2.id, 'quantity': 5, 'price_unit': 15_000,
                                         'vat_rate_id': vat8.id})]})
mg_ret.action_post()
MR = env['lfood.margin.report'].with_user(users['giamdoc']).with_company(factory)
mr = MR.create({'date_from': date(2029, 8, 1), 'date_to': date(2029, 8, 31), 'company_id': factory.id, 'dimension': 'brand'})
rows = mr._rows()
check('Lãi gộp theo nhãn hàng: Yến Việt 300.000 - 200.000; Biển Xanh 225.000 - 150.000 (đã trừ hàng trả lại)',
      (rows.get('Yến Việt'), rows.get('Biển Xanh')) == ([300_000, 200_000], [225_000, 150_000]), rows)
mr.write({'dimension': 'channel'})
mr.action_compute()
check('Giám đốc xem lãi gộp theo kênh: cộng doanh thu 525.000, lãi gộp 175.000, tỷ lệ 33,3%',
      mr._rows()[channel_mt.name] == [525_000, 350_000] and '175.000' in mr.report_html and '33.3%' in mr.report_html,
      mr._rows())

# ---- phân bổ chi phí chung
ci_common = env['lfood.cost.item'].create({'code': 'PBC', 'name': 'Chi phí quản lý chung (phân bổ)'})
ci_yv = env['lfood.cost.item'].create({'code': 'PBYV', 'name': 'Nhãn Yến Việt'})
ci_bx = env['lfood.cost.item'].create({'code': 'PBBX', 'name': 'Nhãn Biển Xanh'})
common_pay = PayF.create({'kind': 'out', 'method': 'bank', 'purpose': 'expense', 'amount': 1_000_000, 'memo': 'Phí quản lý chung',
                          'date': date(2029, 8, 10), 'company_id': factory.id, 'cash_account': '112',
                          'counterpart_account': '6428', 'cost_item_id': ci_common.id})
common_pay.action_post()
ALC = env['lfood.cost.allocation'].with_user(users['ketoanvien']).with_company(factory)
alc = ALC.create({'name': 'Chi phí chung tháng 8/2029', 'company_id': factory.id, 'date_from': date(2029, 8, 1),
                  'date_to': date(2029, 8, 31), 'source_cost_item_id': ci_common.id, 'basis': 'revenue_brand',
                  'line_ids': [(0, 0, {'cost_item_id': ci_yv.id, 'key': 'Yến Việt'}),
                               (0, 0, {'cost_item_id': ci_bx.id, 'key': 'Biển Xanh'})]})
alc.action_compute()
check('Phân bổ chi phí chung 1.000.000 theo doanh thu nhãn hàng 300.000 : 225.000',
      alc.amount == 1_000_000 and alc.line_ids.mapped('amount') == [571_429, 428_571], alc.line_ids.mapped('amount'))
try:
    alc.action_post(); check('Kế toán viên không ghi sổ phân bổ', False)
except UserError:
    check('Kế toán viên không ghi sổ phân bổ', True)
alc_kt = env['lfood.cost.allocation'].with_user(users['ketoantruong']).browse(alc.id)
alc_kt.action_post()
check('Ghi sổ phân bổ: khoản mục chung về 0, nhãn hàng nhận đúng số, tổng 6428 không đổi',
      (gl(factory, '6428', cost_item_id=ci_common.id), gl(factory, '6428', cost_item_id=ci_yv.id),
       gl(factory, '6428', cost_item_id=ci_bx.id)) == (0, 571_429, 428_571),
      (gl(factory, '6428', cost_item_id=ci_common.id), gl(factory, '6428', cost_item_id=ci_yv.id)))
alc_kt.action_reset()
check('Hủy phân bổ trả chi phí về khoản mục chung', gl(factory, '6428', cost_item_id=ci_common.id) == 1_000_000
      and alc.state == 'draft')

# ---- quét mã vạch, tem lô
mg_p1.barcode = '8930000000017'
scan_pk = PK.create({'kind': 'out', 'purpose': 'internal', 'date': date(2029, 8, 20), 'warehouse_id': wh_mg.id,
                     'company_id': factory.id})
for code in ('8930000000017', '8930000000017', 'LG02', '8930000000017'):
    scan_pk.scan(code)
check('Quét mã vạch vào phiếu xuất: 3 lần cháo yến gộp một dòng, súp cua theo mã hàng',
      sorted((l.product_id.code, l.quantity) for l in scan_pk.line_ids) == [('LG01', 3), ('LG02', 1)],
      [(l.product_id.code, l.quantity) for l in scan_pk.line_ids])
try:
    scan_pk.scan('KHONGCO'); check('Mã không có trong danh mục báo lỗi', False)
except UserError:
    check('Mã không có trong danh mục báo lỗi', True)
env.flush_all()
env.cr.execute('SAVEPOINT bc_dup')
try:
    env['lfood.product'].create({'code': 'LG09', 'name': 'Trùng mã vạch', 'uom': 'hũ', 'barcode': '8930000000017',
                                 'company_id': factory.id})
    env.flush_all()
    check('Không gán một mã vạch cho hai mặt hàng', False)
except Exception:
    check('Không gán một mã vạch cho hai mặt hàng', True)
env.cr.execute('ROLLBACK TO SAVEPOINT bc_dup')
env.clear()
from odoo.addons.lfood_stock.models.barcode import lookup as _lookup
check('Tem lô có mã dạng MÃ HÀNG/SỐ LÔ và tra ngược được',
      lot_sb.label_code == 'SO01/SB' and _lookup(env, 'SO01/SB') == (so_prod, lot_sb, 1))
html_label = env['ir.actions.report']._render_qweb_html('lfood_stock.report_lot_label', lot_sb.ids)[0].decode()
check('In tem lô: có tên hàng, số lô, hạn dùng, mã vạch Code128', 'SO01/SB' in html_label and 'Code128' in html_label
      and '30/06/2027' in html_label)
cnt = env['lfood.stock.count'].with_user(users['ketoanvien']).with_company(factory).create(
    {'warehouse_id': wh_mg.id, 'date': date(2029, 8, 31), 'members': 'Thủ kho, kế toán', 'company_id': factory.id})
cnt.action_load()
cnt.action_scan_mode()
for _i in range(99):
    cnt.scan('8930000000017')
c1 = cnt.line_ids.filtered(lambda l: l.product_id == mg_p1)
check('Kiểm kê bằng máy quét: đếm lại từ 0, quét 99 hũ cháo yến, sổ còn 90 thì thừa 9',
      (c1.book_qty, c1.real_qty, c1.diff_qty) == (90, 99, 9), (c1.book_qty, c1.real_qty, c1.diff_qty))
cnt.scan('LG02')
c2 = cnt.line_ids.filtered(lambda l: l.product_id == mg_p2)
check('Súp cua quét 1 hũ, sổ còn 85 thì thiếu 84', (c2.book_qty, c2.real_qty) == (85, 1), (c2.book_qty, c2.real_qty))

# ---- cơ hội bán hàng
LEAD = env['lfood.sale.lead'].with_user(users['ketoanvien']).with_company(factory)
ld = LEAD.create({'name': 'Chuỗi cửa hàng Xanh - cháo hũ', 'prospect': 'Công ty Cửa hàng Xanh', 'vat': '0319999999',
                  'contact_name': 'Chị Mai', 'phone': '0900000000', 'channel_id': channel_mt.id, 'company_id': factory.id,
                  'expected_revenue': 50_000_000, 'next_action': 'Gửi mẫu', 'next_date': date(2029, 9, 5)})
ld.write({'stage': 'negotiation'})
check('Đàm phán: xác suất 70%, doanh số có trọng số 35 triệu', (ld.probability, ld.weighted_revenue) == (70, 35_000_000))
try:
    ld.write({'stage': 'won'}); check('Không kéo thẳng sang Thành công', False)
except UserError:
    check('Không kéo thẳng sang Thành công', True)
ld.action_won()
check('Thành công: tạo khách hàng có kênh, người liên hệ và báo giá nháp',
      ld.stage == 'won' and ld.partner_id.vat == '0319999999' and ld.partner_id.lfood_channel_id == channel_mt
      and ld.partner_id.child_ids.name == 'Chị Mai' and ld.order_id.state == 'draft' and ld.order_id.partner_id == ld.partner_id)
ld2 = LEAD.create({'name': 'Siêu thị Y', 'prospect': 'Siêu thị Y', 'company_id': factory.id})
try:
    ld2.action_lost(); check('Thất bại phải ghi lý do', False)
except UserError:
    check('Thất bại phải ghi lý do', True)
ld2.write({'lost_reason': 'Giá cao hơn đối thủ'})
ld2.action_lost()
check('Cơ hội thất bại xác suất 0', ld2.stage == 'lost' and ld2.weighted_revenue == 0)

# ---- báo cáo lao động, tiền lương
LCR = env['lfood.labor.cost.report'].with_user(users['giamdoc']).with_company(office)
lcr = LCR.create({'year': 2028, 'company_id': office.id})
lcd = lcr._data()
check('Báo cáo lao động, lương 2028: tháng 1 có 2 người, quỹ lương cả năm có thưởng tháng 12, vãng lai 14 triệu',
      lcd['headcount'][0] >= 2 and lcd['gross'][11] - lcd['gross'][10] == 60_000_000
      and sum(lcd['freelance']) == 14_000_000 and sum(lcd['freelance_pit']) == 800_000, (lcd['headcount'][0], sum(lcd['freelance'])))
lcr.action_compute()
check('Bảng báo cáo có 12 tháng và cột cả năm', 'T12' in lcr.report_html and 'Cả năm' in lcr.report_html)

# ---- tuyển dụng
JR = env['lfood.hr.job.request'].with_user(users['ketoanvien']).with_company(factory)
jr = JR.create({'name': 'Công nhân đóng gói', 'quantity': 1, 'reason': 'Mở thêm ca 3', 'company_id': factory.id})
try:
    jr.action_approve(); check('Kế toán không duyệt yêu cầu tuyển', False)
except UserError:
    check('Kế toán không duyệt yêu cầu tuyển', True)
jr.with_user(users['giamdoc']).action_approve()
AP = env['lfood.hr.applicant'].with_user(users['ketoanvien'])
ap1 = AP.create({'name': 'Ứng viên A', 'request_id': jr.id, 'phone': '0911111111'})
try:
    ap1.write({'stage': 'screening'}); check('Chưa đồng ý xử lý dữ liệu thì không sàng lọc được', False)
except UserError:
    check('Chưa đồng ý xử lý dữ liệu thì không sàng lọc được', True)
ap1.write({'consent': True, 'consent_date': date(2029, 3, 1)})
ap1.write({'stage': 'offer', 'employee_code': 'TD01', 'date_start': date(2029, 4, 1)})
ap1.action_hire()
check('Nhận việc: tạo hồ sơ nhân viên, đủ số lượng thì đóng yêu cầu',
      ap1.stage == 'hired' and ap1.employee_id.code == 'TD01' and ap1.employee_id.date_start == date(2029, 4, 1)
      and jr.state == 'closed')
ap2 = AP.create({'name': 'Ứng viên B', 'request_id': jr.id, 'consent': True})
ap2.write({'stage': 'rejected'})
ap3 = AP.create({'name': 'Ứng viên C', 'request_id': jr.id, 'consent': True, 'keep_longer': True})
ap3.write({'stage': 'rejected'})
env['lfood.hr.applicant'].search([('id', 'in', (ap2 | ap3).ids)]).write({'closed_on': date(2028, 1, 1)})
purged = env['lfood.hr.applicant']._cron_purge(date(2029, 6, 1))
check('Xóa hồ sơ không trúng tuyển quá 12 tháng, giữ người đồng ý lưu lâu hơn',
      purged >= 1 and not ap2.exists() and ap3.exists() and ap1.exists(), purged)

# ---- R&D
rnd_user = AU.create({'name': 'Chuyên viên R&D thử', 'login': 'rnd_thu', 'company_id': factory.id,
                      'company_ids': [(6, 0, factory.ids)], 'lfood_role': 'rnd'})
RP = env['lfood.rnd.project'].with_user(rnd_user)
rp = RP.create({'name': 'Cháo yến hạt sen', 'brand': 'Yến Việt', 'idea': 'Cháo ăn sáng cho người lớn tuổi'})
check('Dự án R&D có mã RD', rp.code.startswith('RD'), rp.code)
for u, label in ((users['ketoanvien'], 'Kế toán viên'), (users['ketoantruong'], 'Kế toán trưởng')):
    try:
        env['lfood.rnd.project'].with_user(u).search_count([]); check('%s không xem được R&D' % label, False)
    except AccessError:
        check('%s không xem được R&D' % label, True)
RF = env['lfood.rnd.formula'].with_user(rnd_user)
rf1 = RF.create({'project_id': rp.id, 'name': 'Cháo yến', 'batch_size': 200,
                'line_ids': [(0, 0, {'ingredient': 'Gạo', 'pct': 60}), (0, 0, {'ingredient': 'Nước', 'pct': 35}),
                             (0, 0, {'ingredient': 'Yến', 'pct': 4})]})
try:
    rf1.action_lock(); check('Chốt công thức khi tổng tỷ lệ khác 100% bị chặn', False)
except UserError:
    check('Chốt công thức khi tổng tỷ lệ khác 100% bị chặn', True)
rf1.line_ids.filtered(lambda l: l.ingredient == 'Yến').write({'pct': 5})
check('Khối lượng theo mẻ 200 kg: gạo 120 kg', rf1.line_ids.filtered(lambda l: l.ingredient == 'Gạo').qty == 120)
rf1.action_lock()
try:
    rf1.line_ids[0].write({'pct': 61}); check('Công thức đã chốt không sửa được', False)
except UserError:
    check('Công thức đã chốt không sửa được', True)
try:
    env['lfood.rnd.formula'].with_user(users['giamdoc']).browse(rf1.id).action_approve()
    check('Chưa có mẫu thử đạt thì không duyệt', False)
except UserError:
    check('Chưa có mẫu thử đạt thì không duyệt', True)
RS = env['lfood.rnd.sample'].with_user(rnd_user)
s_bad = RS.create({'formula_id': rf1.id, 'name': 'M1', 'color': 7, 'smell': 7, 'taste': 5, 'texture': 6,
                   'test_ids': [(0, 0, {'indicator': 'Độ ẩm', 'value': 80, 'unit': '%', 'limit_min': 70, 'limit_max': 85})]})
s_ok = RS.create({'formula_id': rf1.id, 'name': 'M2', 'color': 8, 'smell': 7, 'taste': 7, 'texture': 7,
                  'test_ids': [(0, 0, {'indicator': 'Coliform', 'value': 12, 'limit_max': 10})]})
check('Mẫu cảm quan 6,25 đạt; mẫu có chỉ tiêu vượt giới hạn không đạt',
      (s_bad.sensory_avg, s_bad.result, s_ok.result) == (6.25, 'pass', 'fail'), (s_bad.sensory_avg, s_bad.result, s_ok.result))
try:
    rf1.action_approve(); check('R&D không tự duyệt công thức', False)
except AccessError:
    check('R&D không tự duyệt công thức', True)
env['lfood.rnd.formula'].with_user(users['giamdoc']).browse(rf1.id).action_approve()
act_v2 = rf1.action_new_version()
rf2 = RF.browse(act_v2['res_id'])
check('Giám đốc duyệt v1; tạo v2 là bản nháp chép nguyên liệu',
      rf1.state == 'approved' and rf1.approved_by == users['giamdoc'] and rf2.version == 2 and rf2.state == 'draft'
      and len(rf2.line_ids) == 3 and rp.approved_formula_id == rf1)
rf2.write({'change_note': 'Tăng yến'})
rf2.line_ids.filtered(lambda l: l.ingredient == 'Nước').write({'pct': 34})
rf2.line_ids.filtered(lambda l: l.ingredient == 'Yến').write({'pct': 6})
rf2.action_lock()
RS.create({'formula_id': rf2.id, 'name': 'M3', 'color': 8, 'smell': 8, 'taste': 8, 'texture': 8})
env['lfood.rnd.formula'].with_user(users['giamdoc']).browse(rf2.id).action_approve()
check('Duyệt v2 thì v1 hết hiệu lực; nhật ký ghi người duyệt',
      rf1.state == 'obsolete' and rp.approved_formula_id == rf2
      and Log.sudo().search_count([('model', '=', 'lfood.rnd.formula'), ('res_id', '=', rf2.id),
                                   ('user_id', '=', users['giamdoc'].id)]) >= 1)
rp.write({'stage': 'transfer', 'transfer_note': 'Bàn giao công thức v2 cho nhà máy'})
check('Chuyển giao khi đã có công thức duyệt', rp.stage == 'transfer')

# ---- bảo trì thiết bị, đội xe
EQ = env['lfood.equipment'].with_user(users['ketoanvien']).with_company(factory)
eq = EQ.create({'name': 'Máy chiết rót 1', 'location': 'Dây chuyền cháo', 'interval_days': 90,
                'start_date': date(2029, 1, 1), 'company_id': factory.id})
check('Thiết bị mới: đến hạn bảo trì sau 90 ngày từ ngày theo dõi', eq.next_date == date(2029, 4, 1))
MT = env['lfood.maintenance'].with_user(users['ketoanvien']).with_company(factory)
MT.create({'equipment_id': eq.id, 'kind': 'preventive', 'date': date(2029, 3, 20), 'description': 'Thay gioăng',
           'downtime_hours': 4, 'cost': 1_500_000, 'company_id': factory.id, 'state': 'done'})
MT.create({'equipment_id': eq.id, 'kind': 'repair', 'date': date(2029, 5, 2), 'description': 'Hỏng motor',
           'downtime_hours': 10, 'cost': 6_000_000, 'company_id': factory.id, 'state': 'done'})
check('Bảo trì định kỳ 20/3 thì hạn tiếp 18/6; tổng dừng máy 14 giờ, chi phí 7,5 triệu',
      (eq.next_date, eq.downtime_hours, eq.cost_total) == (date(2029, 6, 18), 14, 7_500_000),
      (eq.next_date, eq.downtime_hours, eq.cost_total))
env.flush_all()
env.cr.execute('SAVEPOINT mt_bad')
try:
    MT.create({'kind': 'repair', 'description': 'x', 'company_id': factory.id})
    env.flush_all()
    check('Phiếu bảo trì phải chọn thiết bị hoặc xe', False)
except ValidationError:
    check('Phiếu bảo trì phải chọn thiết bị hoặc xe', True)
env.cr.execute('ROLLBACK TO SAVEPOINT mt_bad')
env.clear()
VH = env['lfood.vehicle'].with_user(users['ketoanvien']).with_company(factory)
vh = VH.create({'plate': '70C-123.45', 'model': 'Tải 1,5 tấn', 'region': 'south', 'fuel_norm': 12,
                'registration_expiry': date(2029, 6, 30), 'insurance_expiry': date(2029, 9, 1), 'company_id': factory.id})
FL2 = env['lfood.fuel.log'].with_user(users['ketoanvien'])
FL2.create({'vehicle_id': vh.id, 'date': date(2029, 6, 1), 'liters': 50, 'odometer': 10_000})
FL2.create({'vehicle_id': vh.id, 'date': date(2029, 6, 5), 'liters': 20, 'odometer': 10_200, 'full_tank': False})
fl_last = FL2.create({'vehicle_id': vh.id, 'date': date(2029, 6, 10), 'liters': 40, 'odometer': 10_400})
check('Tiêu hao giữa hai lần đổ đầy: 60 lít / 400 km = 15 lít/100 km, vượt định mức 12',
      (fl_last.consumption, fl_last.over_norm) == (15, True), (fl_last.consumption, fl_last.over_norm))
MT.create({'vehicle_id': vh.id, 'kind': 'preventive', 'date': date(2029, 6, 11), 'description': 'Bảo dưỡng 10.000 km',
           'odometer': 10_450, 'company_id': factory.id, 'state': 'done'})
check('Số km hiện tại 10.450, bảo dưỡng tiếp ở 20.450', (vh.odometer, vh.next_service_km) == (10_450, 20_450))
env['lfood.reminder']._cron_refresh(date(2029, 6, 10))
check('Nhắc hạn đăng kiểm xe và bảo trì thiết bị',
      env['lfood.reminder'].search_count([('key', '=', 'veh-registration_expiry-%s-2029-06-30' % vh.id), ('state', '=', 'open')]) == 1
      and env['lfood.reminder'].search_count([('key', '=', 'maint-%s-2029-06-18' % eq.id), ('state', '=', 'open')]) == 1)
chanh = env['lfood.carrier'].with_user(users['ketoanvien']).with_company(factory).create(
    {'partner_id': env['res.partner'].create({'name': 'Chành Bắc Nam thử'}).id, 'region': 'north',
     'rate_per_kg': 2_000, 'company_id': factory.id})
fr = env['lfood.freight.log'].with_user(users['ketoanvien']).create(
    {'carrier_id': chanh.id, 'destination': 'Hà Nội', 'weight': 500, 'cost': 1_250_000})
check('Chuyến gửi chành 2.500 đồng/kg cao hơn cước tham chiếu', (fr.cost_per_kg, fr.above_rate, fr.region) == (2_500, True, 'north'))

# ---- đánh giá hiệu suất, đào tạo
from odoo.addons.lfood_hr_records.models.performance import rate as _rate
check('Xếp loại theo điểm', [_rate(x) for x in (105, 90, 70, 69.9)] == ['A', 'B', 'C', 'D'])
KP = env['lfood.kpi.period'].with_user(users['ketoanvien']).with_company(factory)
kp = KP.create({'name': 'Quý 2/2029', 'date_from': date(2029, 4, 1), 'date_to': date(2029, 6, 30), 'bonus_base': 3_000_000,
                'company_id': factory.id,
                'review_ids': [(0, 0, {'employee_id': f1.id, 'line_ids': [
                    (0, 0, {'name': 'Sản lượng', 'weight': 60, 'target': 1000, 'actual': 1100}),
                    (0, 0, {'name': 'Tỷ lệ hàng hỏng (%)', 'weight': 40, 'target': 2, 'actual': 2.5, 'lower_better': True})]})]})
rv = kp.review_ids
check('KPI: sản lượng 110%, hàng hỏng 80%; tổng 98 điểm xếp B, thưởng 3 triệu',
      (rv.line_ids.mapped('achievement'), rv.score, rv.rating, rv.bonus) == ([110, 80], 98, 'B', 3_000_000),
      (rv.line_ids.mapped('achievement'), rv.score, rv.rating, rv.bonus))
try:
    kp.action_approve(); check('Kế toán không duyệt kết quả đánh giá', False)
except UserError:
    check('Kế toán không duyệt kết quả đánh giá', True)
kp.with_user(users['giamdoc']).action_approve()
check('Duyệt đánh giá tạo quyết định khen thưởng 3 triệu ngày cuối kỳ',
      rv.reward_id.amount == 3_000_000 and rv.reward_id.date == date(2029, 6, 30) and rv.reward_id.employee_id == f1)
TC = env['lfood.training.course'].with_user(users['ketoanvien']).with_company(factory)
tc = TC.create({'name': 'Vận hành nồi hơi', 'date_start': date(2028, 7, 1), 'valid_months': 12, 'cost': 6_000_000,
                'company_id': factory.id,
                'attendee_ids': [(0, 0, {'employee_id': f1.id, 'result': 'pass'}),
                                 (0, 0, {'employee_id': e_hr.id, 'result': 'fail'})]})
tc.action_done()
check('Học xong: người đạt có hạn chứng chỉ 01/07/2029, chi phí 3 triệu/người',
      tc.attendee_ids.filtered(lambda a: a.result == 'pass').expiry == date(2029, 7, 1) and tc.cost_per_head == 3_000_000
      and not tc.attendee_ids.filtered(lambda a: a.result == 'fail').expiry)
env['lfood.reminder']._cron_refresh(date(2029, 6, 15))
check('Nhắc chứng chỉ đào tạo sắp hết hạn',
      env['lfood.reminder'].search_count([('key', '=like', 'training-%'), ('state', '=', 'open'), ('title', 'ilike', 'nồi hơi')]) == 1)

# ---- giám sát HACCP
CCP = env['lfood.ccp'].with_user(users['ketoantruong']).with_company(factory)
ccp1 = CCP.create({'code': 'CCP1', 'name': 'Tiệt trùng', 'hazard': 'Clostridium botulinum', 'parameter': 'Nhiệt độ tiệt trùng',
                   'unit': '°C', 'limit_min': 121, 'has_min': True, 'corrective_action': 'Dừng dây chuyền, tiệt trùng lại mẻ',
                   'company_id': factory.id})
hlot = env['lfood.stock.lot'].create({'name': 'HACCP1', 'product_id': so_prod.id})
RD_ = env['lfood.ccp.reading'].with_user(users['ketoanvien'])
ok_read = RD_.create({'ccp_id': ccp1.id, 'value': 121.5, 'lot_id': hlot.id, 'operator': 'Tổ trưởng ca 1',
                      'measured_at': '2029-09-03 08:00:00'})
check('Đo trong giới hạn: không giữ lô', ok_read.in_limit and not ok_read.action_id)
bad_read = RD_.create({'ccp_id': ccp1.id, 'value': 118, 'lot_id': hlot.id, 'operator': 'Tổ trưởng ca 1',
                       'measured_at': '2029-09-03 09:00:00', 'deviation_note': 'Áp suất hơi thấp'})
check('Đo ngoài giới hạn: tự cách ly lô và mở hành động khắc phục có biện pháp định sẵn',
      not bad_read.in_limit and hlot.hold and 'CCP1' in hlot.hold_reason
      and bad_read.action_id.measure == 'Dừng dây chuyền, tiệt trùng lại mẻ' and bad_read.action_id.state == 'open',
      (bad_read.in_limit, hlot.hold, hlot.hold_reason))
try:
    bad_read.write({'value': 122}); check('Không sửa giá trị đã đo', False)
except UserError:
    check('Không sửa giá trị đã đo', True)
try:
    bad_read.action_verify(); check('Chưa khắc phục xong thì không xác nhận hồ sơ', False)
except UserError:
    check('Chưa khắc phục xong thì không xác nhận hồ sơ', True)
bad_read.action_id.sudo().write({'responsible': 'Quản đốc'})
bad_read.action_id.sudo().action_done()
(ok_read | bad_read).action_verify()
check('Khắc phục xong thì xác nhận hồ sơ', bad_read.verified_by == users['ketoanvien'] and ok_read.verified_by)
try:
    ok_read.unlink(); check('Không xóa hồ sơ giám sát', False)
except UserError:
    check('Không xóa hồ sơ giám sát', True)
env['lfood.stock.lot'].with_user(users['ketoantruong']).browse(hlot.id).action_release()
env['lfood.reminder']._cron_refresh(date(2029, 9, 7))
check('Quá một ngày làm việc không đo CCP thì nhắc',
      env['lfood.reminder'].search_count([('key', '=like', 'ccp-gap-%s-%%' % ccp1.id), ('state', '=', 'open')]) == 1)

# ---- nhập khẩu, xuất khẩu, nhà thầu nước ngoài
usd = env.ref('base.USD')
usd.sudo().active = True
wh_imp = WH.create({'code': 'KNK', 'name': 'Kho hàng nhập khẩu', 'company_id': factory.id})
imp_p = env['lfood.product'].with_user(users['ketoanvien']).with_company(factory).create(
    {'code': 'NK01', 'name': 'Yến sào nhập khẩu', 'uom': 'kg', 'kind': 'goods', 'company_id': factory.id})
foreign = env['res.partner'].create({'name': 'Swiftlet Co. Ltd (Indonesia)', 'is_company': True})
forwarder = env['res.partner'].create({'name': 'Công ty giao nhận thử', 'is_company': True})
IMP = env['lfood.import.declaration'].with_user(users['ketoanvien']).with_company(factory)
imp = IMP.create({'name': '10600000001', 'date': date(2029, 10, 5), 'partner_id': foreign.id, 'currency_id': usd.id,
                  'rate': 25_000, 'warehouse_id': wh_imp.id, 'company_id': factory.id,
                  'line_ids': [(0, 0, {'product_id': imp_p.id, 'quantity': 100, 'price_currency': 10, 'duty_rate': 5,
                                       'vat_rate': 8, 'lot_name': 'NK-A', 'expiry_date': date(2031, 10, 1)})],
                  'cost_ids': [(0, 0, {'name': 'Cước vận chuyển nội địa', 'partner_id': forwarder.id, 'amount': 1_000_000,
                                       'vat': 80_000})]})
check('Tờ khai nhập khẩu: trị giá 25 triệu, thuế NK 1,25 triệu, thuế GTGT 2,1 triệu, giá nhập kho 27,25 triệu',
      (imp.value_total, imp.duty_total, imp.vat_total, imp.landed_total) == (25_000_000, 1_250_000, 2_100_000, 27_250_000),
      (imp.value_total, imp.duty_total, imp.vat_total, imp.landed_total))
imp.action_post()
mimp = Move._active_for(imp)
supplier_line = mimp.line_ids.filtered(lambda l: l.account_code == '3311' and l.partner_id == foreign)
check('Ghi sổ nhập khẩu: kho 27,25 triệu qua 3388 về 0; Có 3333, 33312; công nợ người bán 1.000 USD',
      imp.picking_id.state == 'done' and imp.picking_id.amount == 27_250_000
      and sum(ML.sudo().search([('account_code', '=', '3388'),
                                ('move_id', 'in', (mimp | Move._active_for(imp.picking_id)).ids)]).mapped('balance')) == 0
      and gl(factory, '3333', move_id=mimp.id) == -1_250_000 and gl(factory, '33312', move_id=mimp.id) == -2_100_000
      and supplier_line.balance == -25_000_000 and supplier_line.amount_currency == -1000,
      (imp.picking_id.amount, supplier_line.balance, supplier_line.amount_currency))
check('Giá vốn đơn vị hàng nhập khẩu 272.500/kg', round(imp_p._position(upto=date(2029, 10, 31))[1]) == 27_250_000)
vr_imp = env['lfood.vat.return'].sudo().new({'company_id': factory.id, 'period_type': 'month', 'year': 2029, 'month': 10})
li = [v for v in vr_imp._purchase_lines() if v.get('source_model') == 'lfood.import.declaration']
check('Bảng kê mua vào: thuế GTGT nhập khẩu chưa có chứng từ nộp thuế thì chưa được khấu trừ',
      len(li) == 1 and li[0]['tax'] == 2_100_000 and not li[0]['deductible'])
imp.write({'tax_paid_ref': 'GNT-0001', 'tax_paid_date': date(2029, 10, 6)})
li = [v for v in vr_imp._purchase_lines() if v.get('source_model') == 'lfood.import.declaration']
check('Có chứng từ nộp thuế thì được khấu trừ', li[0]['deductible'] and li[0]['ref'] == 'GNT-0001')
try:
    imp.write({'rate': 26_000}); check('Tờ khai đã ghi sổ không sửa trị giá', False)
except UserError:
    check('Tờ khai đã ghi sổ không sửa trị giá', True)

buyer = env['res.partner'].create({'name': 'Nest Import Pte Ltd (Singapore)', 'is_company': True})
exp_inv = SI.create({'partner_id': buyer.id, 'date': date(2029, 10, 10), 'invoice_template': '1', 'invoice_symbol': 'C29TXK',
                     'invoice_number': '00000001', 'company_id': factory.id,
                     'line_ids': [(0, 0, {'name': 'Yến sào xuất khẩu', 'quantity': 1, 'price_unit': 200_000_000,
                                          'vat_rate_id': ref('lfood_voucher.vat_0').id})]})
exp_inv.action_post()
EXD = env['lfood.export.declaration'].with_user(users['ketoanvien']).with_company(factory)
exd = EXD.create({'name': '30600000001', 'date': date(2029, 10, 10), 'sale_invoice_id': exp_inv.id, 'company_id': factory.id})
check('Hồ sơ xuất khẩu thiếu hợp đồng, tờ khai, vận đơn, phiếu đóng gói, thanh toán',
      exd.zero_rate_ok and not exd.complete and 'hợp đồng' in exd.missing and 'không dùng tiền mặt' in exd.missing, exd.missing)
exd.write({'contract_ref': 'SC-2029-01', 'contract_file': _b64.b64encode(b'hd'), 'contract_name': 'hd.pdf',
           'declaration_file': _b64.b64encode(b'tk'), 'declaration_name': 'tk.pdf', 'bill_of_lading': 'BL-001',
           'packing_list': True})
Pay.create({'kind': 'in', 'method': 'bank', 'purpose': 'customer', 'partner_id': buyer.id, 'amount': 200_000_000,
            'memo': 'Thu tiền xuất khẩu', 'date': date(2029, 11, 5), 'sale_invoice_id': exp_inv.id,
            'company_id': factory.id}).action_post()
exd.invalidate_recordset()
check('Đủ hồ sơ xuất khẩu khi đã thu chuyển khoản đủ', exd.complete and not exd.missing, exd.missing)

from odoo.addons.lfood_trade.models.fct import fct_amounts as _fa
check('Thuế nhà thầu: giá gồm thuế 100 triệu dịch vụ -> GTGT 5 triệu, TNDN 5 triệu, trả 90 triệu; giá chưa gồm thuế 90 triệu cho cùng kết quả',
      _fa(100_000_000, 5, 5, False) == (100_000_000, 5_000_000, 5_000_000, 90_000_000)
      and _fa(90_000_000, 5, 5, True) == (100_000_000, 5_000_000, 5_000_000, 90_000_000))
FCTP = env['lfood.fct.payment'].with_user(users['ketoanvien']).with_company(factory)
fct1 = FCTP.create({'name': 'Phí tư vấn tiếp thị', 'partner_id': foreign.id, 'contract_ref': 'CT-01', 'date': date(2029, 10, 20),
                    'service_type': 'SERVICE', 'amount': 100_000_000, 'company_id': factory.id})
fct2 = FCTP.create({'name': 'Phí bản quyền nhãn hiệu', 'partner_id': foreign.id, 'contract_ref': 'CT-02', 'date': date(2029, 10, 20),
                    'service_type': 'ROYALTY', 'amount': 50_000_000, 'net_contract': True, 'company_id': factory.id})
check('Tỷ lệ lấy từ tham số: dịch vụ 5%/5%; bản quyền không chịu GTGT, TNDN 10%, giá chưa gồm thuế 50 triệu -> doanh thu 55.555.556',
      (fct1.vat_pct, fct1.cit_pct, fct2.vat_pct, fct2.cit_pct) == (5, 5, 0, 10)
      and (fct2.base, fct2.vat, fct2.cit, fct2.pay_amount) == (55_555_556, 0, 5_555_556, 50_000_000),
      (fct2.base, fct2.cit, fct2.pay_amount))
(fct1 | fct2).action_post()
check('Ghi sổ nhà thầu: Có 3334 10,55 triệu, Có 33311 5 triệu, Nợ 1331 5 triệu',
      gl(factory, '3334', move_id=Move._active_for(fct1).id) + gl(factory, '3334', move_id=Move._active_for(fct2).id) == -10_555_556
      and gl(factory, '1331', move_id=Move._active_for(fct1).id) == 5_000_000
      and gl(factory, '33311', move_id=Move._active_for(fct1).id) == -5_000_000)
li_f = [v for v in vr_imp._purchase_lines() if v.get('source_model') == 'lfood.fct.payment']
check('Bảng kê: thuế GTGT nộp thay nhà thầu, chưa có chứng từ nộp thì chưa khấu trừ; bản quyền không vào bảng kê',
      len(li_f) == 1 and li_f[0]['tax'] == 5_000_000 and not li_f[0]['deductible'])

# ---- hợp nhất hai pháp nhân
ic2 = env['lfood.product'].sudo().create({'code': 'IC02', 'name': 'Nước yến lon', 'uom': 'lon', 'kind': 'finished',
                                          'track_lot': True, 'vat_rate_id': vat8.id, 'company_id': False})
PK.create({'kind': 'in', 'purpose': 'factory', 'date': date(2029, 12, 1), 'warehouse_id': wh_icn.id,
           'line_ids': [(0, 0, {'product_id': ic2.id, 'lot_name': 'L2912', 'expiry_date': date(2031, 12, 1),
                                'quantity': 50, 'price_unit': 10_000})]}).action_done()
ic_b = IC.create({'company_id': factory.id, 'dest_company_id': office.id, 'warehouse_id': wh_icn.id,
                  'dest_warehouse_id': wh_icv.id, 'date': date(2029, 12, 10), 'invoice_symbol': 'C29TNM',
                  'invoice_number': '00000901', 'price_basis': 'Giá bán nhà phân phối độc lập',
                  'line_ids': [(0, 0, {'product_id': ic2.id, 'quantity': 30, 'price_unit': 15_000, 'vat_rate_id': vat8.id})]})
ic_b.action_post()
SI_O = env['lfood.sale.invoice'].with_user(users['ketoanvien']).with_company(office)
sold_o = SI_O.create({'partner_id': customer.id, 'date': date(2029, 12, 20), 'invoice_template': '1', 'invoice_symbol': 'C29TVP',
                      'invoice_number': '00000077', 'warehouse_id': wh_icv.id, 'company_id': office.id,
                      'line_ids': [(0, 0, {'name': 'Nước yến lon', 'product_id': ic2.id, 'quantity': 10, 'price_unit': 20_000,
                                           'vat_rate_id': vat8.id})]})
sold_o.action_post()
CR = env['lfood.consolidation.report'].with_user(users['giamdoc'])
cr = CR.create({'company_a_id': office.id, 'company_b_id': factory.id, 'date_from': date(2029, 12, 1),
                'date_to': date(2029, 12, 31)})
cd = cr._compute_data()
check('Hợp nhất: doanh thu nội bộ 450.000; lãi chưa thực hiện cuối kỳ 140.000 (20 lon x 5.000 và 20 hũ năm 2026 x 2.000), tăng trong kỳ 100.000',
      (cd['sales'], cd['up'], cd['up_change']) == (450_000, 140_000, 100_000), (cd['sales'], cd['up'], cd['up_change']))
pa, pb, pc = cd['pl']['a'], cd['pl']['b'], cd['pl']['c']
check('B02 hợp nhất: trừ doanh thu nội bộ; giá vốn trừ 450.000 cộng 100.000; lợi nhuận gộp giảm đúng lãi chưa thực hiện',
      pc['01'] == pa['01'] + pb['01'] - 450_000 and pc['11'] == pa['11'] + pb['11'] - 350_000
      and pc['20'] == pa['20'] + pb['20'] - 100_000, (pc['01'], pc['11'], pc['20']))
ba, bb, bc = cd['bs']['a'], cd['bs']['b'], cd['bs']['c']
f_rec_o = gl(factory, '131', partner_id=office.partner_id.id)
check('B01 hợp nhất: loại công nợ nội bộ khỏi phải thu, phải trả; tồn kho giảm lãi chưa thực hiện; lệch công nợ thì cảnh báo',
      cd['recv'] > 0 and bc['131'] == ba['131'] + bb['131'] - cd['recv'] and bc['311'] == ba['311'] + bb['311'] - cd['recv']
      and bc['141'] == ba['141'] + bb['141'] - 140_000 and (not cd['warn']) == (f_rec_o == -gl(office, '331', partner_id=factory.partner_id.id)),
      (cd['recv'], cd['warn'], f_rec_o))
cr.action_compute()
check('Báo cáo có bảng đối chiếu mua bán nội bộ khớp hóa đơn và phiếu nhập',
      'BNB' in cr.report_html and 'Khớp' in cr.report_html and 'Hợp nhất' in cr.report_html)
try:
    env['lfood.consolidation.report'].with_user(users['ketoanvien']).create(
        {'company_a_id': office.id, 'company_b_id': factory.id, 'date_from': date(2029, 12, 1), 'date_to': date(2029, 12, 31)})
    check('Kế toán viên không xem báo cáo hợp nhất', False)
except AccessError:
    check('Kế toán viên không xem báo cáo hợp nhất', True)

# ---- sàn thương mại điện tử
sea_cust = env['res.partner'].create({'name': 'Khách mua trên Shopee'})
SHOP = env['lfood.ecom.shop'].with_user(users['ketoanvien']).with_company(factory)
shop = SHOP.create({'name': 'LiFeOOD Official Shopee', 'platform': 'shopee', 'warehouse_id': wh_mg.id,
                    'customer_id': sea_cust.id, 'vat_rate_id': vat8.id, 'company_id': factory.id})
orders_csv = """ma_don;ngay;trang_thai;sku;so_luong;don_gia
SP001;25/12/2029;Hoàn thành;8930000000017;2;30000
SP001;25/12/2029;Hoàn thành;LG02;1;15000
SP002;26/12/2029;Chờ lấy hàng;LG02;5;15000
SP003;26/12/2029;Đã hủy;LG02;1;15000
"""
bad_csv = orders_csv + "SP004;26/12/2029;Hoàn thành;KHONGCO;1;1000\n"
shop.write({'import_file': _b64.b64encode(bad_csv.encode('utf-8-sig'))})
try:
    shop.action_import_orders(); check('SKU không có trong danh mục thì không nhập', False)
except UserError:
    check('SKU không có trong danh mục thì không nhập', True)
shop.write({'import_file': _b64.b64encode(orders_csv.encode('utf-8-sig'))})
shop.action_import_orders()
by_ref = {o.name: o for o in shop.order_ids}
check('Nhập đơn sàn: 3 đơn, gộp dòng theo mã đơn, nhận trạng thái',
      set(by_ref) == {'SP001', 'SP002', 'SP003'} and by_ref['SP001'].amount == 75_000 and len(by_ref['SP001'].line_ids) == 2
      and (by_ref['SP001'].status, by_ref['SP002'].status, by_ref['SP003'].status) == ('done', 'new', 'cancel'))
avail = shop._available()
check('Tồn khả dụng trừ đơn chờ giao: cháo yến 90, súp cua 85 - 5 = 80', (avail[mg_p1], avail[mg_p2]) == (90, 80),
      (avail.get(mg_p1), avail.get(mg_p2)))
shop.action_export_stock()
check('Xuất tệp tồn khả dụng theo SKU', '8930000000017;Cháo yến;90' in _b64.b64decode(shop.stock_file).decode('utf-8-sig'))
shop.action_invoice_orders()
inv_sp = by_ref['SP001'].invoice_id
check('Lập hóa đơn nháp cho đơn hoàn thành, không lập cho đơn chờ giao, đơn hủy',
      inv_sp.state == 'draft' and inv_sp.amount_total == 81_000 and not by_ref['SP002'].invoice_id and not by_ref['SP003'].invoice_id)
settle_bad = "ma_don;tien_hang;phi_san;thuc_nhan\nSP001;81000;8100;72900\nSP999;10000;1000;9000\n"
SET = env['lfood.ecom.settlement'].with_user(users['ketoanvien'])
st_e = SET.create({'shop_id': shop.id, 'name': 'PAY-2912', 'date': date(2029, 12, 31),
                   'import_file': _b64.b64encode(settle_bad.encode())})
st_e.action_load()
check('Đối soát báo đơn chưa ghi sổ hóa đơn và đơn không có trong app',
      'SP001 chưa ghi sổ hóa đơn' in st_e.issues and 'SP999 không có trong app' in st_e.issues, st_e.issues)
try:
    st_e.action_post(); check('Còn chênh lệch thì không ghi sổ đối soát', False)
except UserError:
    check('Còn chênh lệch thì không ghi sổ đối soát', True)
inv_sp.write({'invoice_template': '1', 'invoice_symbol': 'C29TSP', 'invoice_number': '00000001'})
inv_sp.action_post()
st_e.write({'import_file': _b64.b64encode("ma_don;tien_hang;phi_san;thuc_nhan\nSP001;81.000;8.100;72.900\n".encode())})
st_e.action_load()
st_e.action_post()
mst = Move._active_for(st_e)
inv_sp.invalidate_recordset()
check('Ghi sổ đối soát: Nợ 112 72.900, Nợ 6417 8.100 / Có 1311 81.000; đơn ghi nhận tiền về, hóa đơn hết phải thu',
      {(l.account_code, l.debit, l.credit) for l in mst.line_ids} == {('112', 72_900, 0), ('6417', 8_100, 0), ('1311', 0, 81_000)}
      and by_ref['SP001'].settled_amount == 72_900 and by_ref['SP001'].fee == 8_100 and inv_sp.amount_residual == 0,
      [(l.account_code, l.debit, l.credit) for l in mst.line_ids])
shop.write({'import_file': _b64.b64encode(orders_csv.replace('Chờ lấy hàng', 'Hoàn thành').encode('utf-8-sig'))})
shop.action_import_orders()
check('Nhập lại cập nhật trạng thái đơn chờ giao thành hoàn thành', by_ref['SP002'].status == 'done')

# ---- đơn vị quy đổi, điều khoản thanh toán, xây dựng cơ bản, tìm kiếm nhanh
CONV = env['lfood.uom.conversion'].with_user(users['ketoanvien'])
thung = CONV.create({'product_id': mg_p1.id, 'name': 'thùng', 'factor': 24, 'barcode': '8930000000024'})
check('Đơn vị quy đổi: 1 thùng = 24 hũ', thung.display_name == 'thùng (= 24 hũ)' and mg_p1.to_base_qty(3, 'thùng') == 72
      and mg_p1.to_base_qty(5, 'hũ') == 5, thung.display_name)
try:
    mg_p1.to_base_qty(1, 'kiện'); check('Đơn vị chưa khai báo thì báo lỗi', False)
except ValidationError:
    check('Đơn vị chưa khai báo thì báo lỗi', True)
scan_uom = PK.create({'kind': 'out', 'purpose': 'internal', 'date': date(2029, 12, 28), 'warehouse_id': wh_mg.id,
                      'company_id': factory.id})
scan_uom.scan('8930000000024')
scan_uom.scan('8930000000017')
check('Quét mã vạch thùng cộng 24 hũ, quét mã hũ cộng 1', scan_uom.line_ids.quantity == 25, scan_uom.line_ids.mapped('quantity'))
TERM = env['lfood.payment.term'].with_user(users['ketoantruong'])
env.flush_all()
env.cr.execute('SAVEPOINT term_bad')
try:
    TERM.create({'name': 'Sai tỷ lệ', 'line_ids': [(0, 0, {'name': 'Đợt 1', 'percent': 40, 'days': 0})]})
    env.flush_all()
    check('Tổng tỷ lệ các đợt phải đủ 100%', False)
except ValidationError:
    check('Tổng tỷ lệ các đợt phải đủ 100%', True)
env.cr.execute('ROLLBACK TO SAVEPOINT term_bad')
env.clear()
term = TERM.create({'name': '30% ngay, 70% sau 30 ngày',
                    'line_ids': [(0, 0, {'name': 'Đợt 1', 'percent': 30, 'days': 0}),
                                 (0, 0, {'name': 'Đợt 2', 'percent': 70, 'days': 30})]})
check('Lịch thanh toán chia đúng tới đồng',
      term.schedule(date(2030, 1, 10), 10_000_001) == [(date(2030, 1, 10), 3_000_000), (date(2030, 2, 9), 7_000_001)]
      and term.max_days == 30, term.schedule(date(2030, 1, 10), 10_000_001))
cust_mt.lfood_payment_term_id = term
inv_term = SI.new({'partner_id': cust_mt.id, 'date': date(2030, 1, 10), 'company_id': factory.id})
inv_term._onchange_partner_term()
inv_term._onchange_term()
check('Hóa đơn lấy điều khoản của khách, hạn thanh toán theo đợt cuối',
      inv_term.payment_term_id == term and inv_term.due_date == date(2030, 2, 9))
CIP = env['lfood.cip'].with_user(users['ketoanvien']).with_company(factory)
cip = CIP.create({'name': 'Nhà kho lạnh số 2', 'date_start': date(2030, 1, 5), 'company_id': factory.id,
                  'category_id': env['lfood.asset.category'].search([], limit=1).id, 'life_months': 120,
                  'line_ids': [(0, 0, {'date': date(2030, 1, 10), 'name': 'Thanh toán nhà thầu đợt 1',
                                       'partner_id': supplier.id, 'amount': 500_000_000}),
                               (0, 0, {'date': date(2030, 2, 10), 'name': 'Thiết bị lạnh', 'partner_id': supplier.id,
                                       'amount': 300_000_000})]})
try:
    cip.action_accept(); check('Chưa ghi sổ chi phí thì chưa nghiệm thu được', False)
except UserError:
    check('Chưa ghi sổ chi phí thì chưa nghiệm thu được', True)
cip.line_ids.action_post()
check('Chi phí xây dựng cơ bản ghi Nợ 2412 / Có 3311, tổng 800 triệu',
      cip.total == 800_000_000 and gl(factory, '2412') == 800_000_000, (cip.total, gl(factory, '2412')))
try:
    cip.line_ids[0].write({'amount': 1}); check('Chi phí đã ghi sổ không sửa được', False)
except UserError:
    check('Chi phí đã ghi sổ không sửa được', True)
cip.action_accept()
check('Nghiệm thu: kết chuyển 2412 về 0, tạo thẻ tài sản nháp nguyên giá 800 triệu',
      gl(factory, '2412') == 0 and cip.asset_id.original_value == 800_000_000 and cip.asset_id.state == 'draft'
      and cip.state == 'done', (gl(factory, '2412'), cip.asset_id.state))
QS = env['lfood.quick.search'].with_user(users['ketoanvien']).with_company(factory)
qs = QS.create({'query': 'Nhà kho lạnh số 2'})
check('Tìm kiếm nhanh thấy tài sản vừa tạo', 'Nhà kho lạnh số 2' in (qs.result_html or ''), qs.result_html)
qs2 = QS.create({'query': '8930000000017'})
check('Tìm theo mã vạch ra mặt hàng', 'Cháo yến' in (qs2.result_html or ''))
qs3 = QS.create({'query': 'khong-co-gi-trung-khop-xyz'})
check('Không tìm thấy thì báo rõ', 'Không tìm thấy' in (qs3.result_html or ''))

# ---- chứng thư số, chứng từ đã ký
CERT = env['lfood.digital.cert'].with_user(users['ketoantruong']).with_company(factory)
cert = CERT.create({'name': 'CÔNG TY CP LIFES FOOD', 'serial': '540101ABCD', 'provider': 'Viettel-CA',
                    'valid_from': date(2029, 1, 1), 'valid_to': date(2030, 1, 1), 'holder': 'Kế toán trưởng',
                    'purpose': 'invoice', 'company_id': factory.id})
check('Chứng thư số hiển thị theo nhà cung cấp và sê-ri', cert.display_name == 'Viettel-CA - 540101ABCD')
env.flush_all()
env.cr.execute('SAVEPOINT cert_bad')
try:
    CERT.create({'name': 'x', 'serial': 'x1', 'provider': 'y', 'valid_from': date(2030, 1, 1),
                 'valid_to': date(2029, 1, 1), 'company_id': factory.id})
    env.flush_all()
    check('Hiệu lực ngược thì chặn', False)
except ValidationError:
    check('Hiệu lực ngược thì chặn', True)
env.cr.execute('ROLLBACK TO SAVEPOINT cert_bad')
env.clear()
POL = env['lfood.archive.policy'].sudo().search([], limit=1)
DOC = env['lfood.document'].with_user(users['ketoanvien']).with_company(factory)
doc = DOC.create({'name': 'Hóa đơn bán ra ký số', 'doc_type': 'invoice', 'doc_date': date(2029, 10, 10),
                  'policy_id': POL.id, 'company_id': factory.id, 'file': _b64.b64encode(b'<xml>hoa don da ky</xml>'),
                  'file_name': 'hd.xml'})
env.flush_all()
env.cr.execute('SAVEPOINT sign_bad')
try:
    doc.write({'signed': True})
    env.flush_all()
    check('Đánh dấu đã ký mà thiếu chứng thư, người ký thì chặn', False)
except ValidationError:
    check('Đánh dấu đã ký mà thiếu chứng thư, người ký thì chặn', True)
env.cr.execute('ROLLBACK TO SAVEPOINT sign_bad')
env.clear()
env.cr.execute('SAVEPOINT sign_out')
try:
    doc.write({'signed': True, 'cert_id': cert.id, 'signer': 'Trần Yên Hưng', 'signature_format': 'xml',
               'signed_at': '2030-06-01 09:00:00'})
    env.flush_all()
    check('Ký ngoài thời hạn chứng thư thì chặn', False)
except ValidationError:
    check('Ký ngoài thời hạn chứng thư thì chặn', True)
env.cr.execute('ROLLBACK TO SAVEPOINT sign_out')
env.clear()
doc.write({'signed': True, 'cert_id': cert.id, 'signer': 'Trần Yên Hưng', 'signature_format': 'xml',
           'signed_at': '2029-10-10 09:00:00'})
check('Ghi nhận chứng từ đã ký số, tệp còn nguyên vẹn', doc.signed and doc.intact and doc.checksum)
env['lfood.reminder']._cron_refresh(date(2029, 12, 15))
check('Nhắc gia hạn chứng thư số sắp hết hạn',
      env['lfood.reminder'].search_count([('key', '=', 'cert-%s-2030-01-01' % cert.id), ('state', '=', 'open')]) == 1)

# ---- nhập dữ liệu ban đầu
JOB = env['lfood.import.job'].with_user(users['ketoantruong']).with_company(factory)
csv_partner = """Ma so thue;Ten nha cung cap;Dia chi;Dien thoai
0312345000;Công ty Nhập Thử A;12 Lê Lợi, TP.HCM;0909111222
;Công ty Nhập Thử B;3 Trần Phú;0909333444
"""
job1 = JOB.create({'name': 'Đối tác từ phần mềm cũ', 'kind': 'partner', 'company_id': factory.id,
                   'file': _b64.b64encode(csv_partner.encode('utf-8-sig')), 'file_name': 'doitac.csv'})
job1.action_read()
m = {x.field_key: x.column_index for x in job1.mapping_ids}
check('Đọc tệp và tự đoán cột: mã số thuế cột 0, tên cột 1, địa chỉ cột 2, điện thoại cột 3',
      (m['vat'], m['name'], m['street'], m['phone']) == (0, 1, 2, 3), m)
job1.action_check()
check('Kiểm tra trước khi nhập: đọc được 2 dòng, không lỗi',
      '2 dòng' in job1.preview_html and 'Không thấy lỗi' in job1.preview_html)
job1.action_import()
p_new = env['res.partner'].search([('vat', '=', '0312345000')])
check('Nhập đối tác: tạo mới theo mã số thuế, ghi kết quả',
      p_new.name == 'Công ty Nhập Thử A' and p_new.phone == '0909111222' and job1.result == 'Đã nhập 2 dòng'
      and job1.state == 'done', job1.result)
job1b = JOB.create({'name': 'Nhập lại lần hai', 'kind': 'partner', 'company_id': factory.id,
                    'file': _b64.b64encode(csv_partner.encode('utf-8-sig')), 'file_name': 'doitac.csv'})
job1b.action_read()
job1b.action_import()
check('Nhập lại không tạo trùng đối tác', env['res.partner'].search_count([('vat', '=', '0312345000')]) == 1
      and job1b.result == 'Đã nhập 0 dòng', job1b.result)
csv_bal = """Tai khoan;Du No;Du Co
111;100.000.000;
41111;;100.000.000
"""
job2 = JOB.create({'name': 'Số dư đầu kỳ 2030', 'kind': 'balance', 'company_id': factory.id,
                   'opening_date': date(2030, 1, 1), 'file': _b64.b64encode(csv_bal.encode('utf-8-sig')),
                   'file_name': 'sodu.csv'})
job2.action_read()
job2.action_import()
mbal = Move._active_for(job2)
check('Số dư đầu kỳ tạo bút toán cân Nợ 111 / Có 41111 100 triệu',
      {(l.account_code, l.debit, l.credit) for l in mbal.line_ids} == {('111', 100_000_000, 0), ('41111', 0, 100_000_000)},
      [(l.account_code, l.debit, l.credit) for l in mbal.line_ids])
job3 = JOB.create({'name': 'Số dư lệch', 'kind': 'balance', 'company_id': factory.id, 'opening_date': date(2030, 1, 1),
                   'file': _b64.b64encode("Tai khoan;Du No;Du Co\n111;5.000.000;\n4111;;4.000.000\n".encode('utf-8-sig')),
                   'file_name': 'lech.csv'})
job3.action_read()
job3.action_check()
check('Số dư đầu kỳ lệch Nợ Có thì báo và không cho nhập', 'lệch' in job3.preview_html)
try:
    job3.action_import(); check('Chặn nhập khi còn lỗi', False)
except UserError:
    check('Chặn nhập khi còn lỗi', True)
csv_stock = """Ma kho;Ma hang;So lo;Han dung;So luong;Don gia
KDB;SO01;TD-01;31/12/2031;10;20000
"""
job4 = JOB.create({'name': 'Tồn kho đầu kỳ 2030', 'kind': 'stock', 'company_id': factory.id,
                   'opening_date': date(2030, 1, 1), 'file': _b64.b64encode(csv_stock.encode('utf-8-sig')),
                   'file_name': 'ton.csv'})
job4.action_read()
job4.action_import()
lot_td = env['lfood.stock.lot'].search([('name', '=', 'TD-01')])
check('Tồn đầu kỳ tạo phiếu nhập, có lô và hạn dùng, không ghi sổ lại',
      lot_td.expiry_date == date(2031, 12, 31) and so_prod._position(wh_so, lot_td)[0] == 10
      and not Move.sudo().search_count([('source_model', '=', 'lfood.stock.picking'), ('memo', 'ilike', 'Tồn đầu kỳ theo')]),
      (lot_td.expiry_date, so_prod._position(wh_so, lot_td)))
try:
    env['lfood.import.job'].with_user(users['ketoanvien']).with_company(factory).create(
        {'name': 'x', 'kind': 'partner', 'company_id': factory.id, 'file': _b64.b64encode(b'a;b')})
    check('Kế toán viên không tạo đợt nhập dữ liệu', False)
except AccessError:
    check('Kế toán viên không tạo đợt nhập dữ liệu', True)

# ---- menu quản trị Odoo không lộ cho người dùng thường
_apps = env.ref('base.menu_management')
check('Menu Ứng dụng chỉ quản trị thấy; không còn module dịch vụ Odoo nào được cài',
      all(_apps.id not in env['ir.ui.menu'].with_user(users[l]).load_menus(False) for l in ('giamdoc', 'ketoantruong', 'ketoanvien', 'nhanvien'))
      and not env['ir.module.module'].search_count([('state', '=', 'installed'), ('name', 'in', [
          'base_install_request', 'partner_autocomplete', 'iap', 'iap_mail', 'sms', 'snailmail', 'web_unsplash', 'mail_bot'])]),
      env['ir.module.module'].search([('state', '=', 'installed'), ('name', 'in', [
          'base_install_request', 'partner_autocomplete', 'iap', 'iap_mail', 'sms', 'snailmail', 'web_unsplash', 'mail_bot'])]).mapped('name'))

# khóa sổ
factory.sudo().with_context(lfood_audit_skip=True).write({'lfood_lock_date': date(2026, 8, 31)})
late = KV_Move.create({'journal': 'general', 'date': date(2026, 8, 20), 'memo': 'ghi vào kỳ đã khóa',
                       'line_ids': [(0, 0, {'account_id': acc('156'), 'debit': 5}), (0, 0, {'account_id': acc('111'), 'credit': 5})]})
try:
    late.action_post(); check('Chặn ghi sổ vào kỳ đã khóa', False)
except UserError:
    check('Chặn ghi sổ vào kỳ đã khóa', True)
try:
    env['lfood.lock'].with_user(users['ketoanvien']).create({'company_id': factory.id, 'lock_date': date(2026, 9, 30), 'reason': 'x'}).action_apply()
    check('Kế toán viên không khóa sổ', False)
except (UserError, AccessError):
    check('Kế toán viên không khóa sổ', True)
m_aug = Move._active_for(env['lfood.asset.depreciation'].search([('date', '=', '2026-08-31'), ('state', '=', 'posted')]))
rev = m_aug.with_user(users['ketoantruong'])._reverse()
check('Đảo bút toán kỳ đã khóa thì ghi vào ngày mở', rev.date > date(2026, 8, 31), rev.date)
env.flush_all()
check('Sau mọi nghiệp vụ sổ vẫn cân', round(sum(ML.sudo().search([('state', '=', 'posted')]).mapped('balance'))) == 0)

env.cr.rollback()
print('\n==== KET QUA KIEM THU ====')
for name, ok, detail in results:
    print('%s  %s%s' % ('OK  ' if ok else 'LOI ', name, '' if ok else '  -> %s' % (detail,)))
print('Tong: %s dat / %s' % (sum(1 for r in results if r[1]), len(results)))
