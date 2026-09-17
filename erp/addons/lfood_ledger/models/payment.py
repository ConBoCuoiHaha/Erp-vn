from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd

KINDS = [('out', 'Chi tiền'), ('in', 'Thu tiền')]
PURPOSES = [
    ('supplier', 'Trả tiền nhà cung cấp'),
    ('customer', 'Thu tiền khách hàng'),
    ('advance', 'Tạm ứng, hoàn ứng nhân viên'),
    ('expense', 'Chi phí trực tiếp'),
    ('other', 'Khác'),
]
DEFAULT_COUNTERPART = {'supplier': '3311', 'customer': '1311', 'advance': '141', 'expense': '6428', 'other': '3388'}


class LfoodPayment(models.Model):
    _name = 'lfood.payment'
    _description = 'Phiếu thu, phiếu chi'
    _order = 'date desc, id desc'

    name = fields.Char('Số phiếu', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    kind = fields.Selection(KINDS, 'Loại', required=True, default='out')
    method = fields.Selection([('cash', 'Tiền mặt'), ('bank', 'Chuyển khoản')], 'Hình thức', required=True, default='bank')
    purpose = fields.Selection(PURPOSES, 'Nội dung', required=True, default='supplier')
    date = fields.Date('Ngày', required=True, default=fields.Date.context_today, index=True)
    partner_id = fields.Many2one('res.partner', 'Đối tượng', index=True)
    person = fields.Char('Người nộp / người nhận')
    amount = fields.Float('Số tiền', digits=(16, 0), required=True)
    memo = fields.Char('Lý do', required=True)
    cash_account = fields.Char('TK tiền', compute='_compute_accounts', store=True, readonly=False)
    counterpart_account = fields.Char('TK đối ứng', compute='_compute_accounts', store=True, readonly=False)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP')
    voucher_id = fields.Many2one('lfood.service.voucher', 'Thanh toán cho chứng từ',
                                 domain="[('partner_id', '=', partner_id), ('state', 'in', ('posted', 'editing'))]")
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             default='draft', readonly=True, copy=False, index=True)
    cash_warning = fields.Boolean('Cảnh báo tiền mặt', compute='_compute_cash_warning')
    move_id = fields.Many2one('lfood.move', 'Bút toán', compute='_compute_move')

    @api.depends('method', 'purpose')
    def _compute_accounts(self):
        for rec in self:
            rec.cash_account = '111' if rec.method == 'cash' else '112'
            rec.counterpart_account = DEFAULT_COUNTERPART.get(rec.purpose)

    @api.depends('method', 'kind', 'purpose', 'amount', 'date')
    def _compute_cash_warning(self):
        Param = self.env['lfood.legal.param']
        for rec in self:
            limit = Param.get_value('NGUONG_TT_KHONG_TIEN_MAT', rec.date, default=5000000)
            rec.cash_warning = rec.kind == 'out' and rec.method == 'cash' and rec.purpose in ('supplier', 'expense') \
                and rec.amount >= limit

    def _compute_move(self):
        Move = self.env['lfood.move']
        for rec in self:
            rec.move_id = Move._active_for(rec)[:1] if rec.id else False

    def write(self, vals):
        if not self.env.context.get('lfood_ledger_system'):
            if {'state', 'name'} & set(vals):
                raise UserError(_('Trạng thái phiếu chỉ đổi bằng nút Ghi sổ, Hủy.'))
            if self.filtered(lambda p: p.state != 'draft'):
                raise UserError(_('Phiếu đã ghi sổ không sửa được. Hãy Hủy phiếu (hệ thống tự đảo bút toán) rồi lập phiếu mới.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda p: p.state == 'posted'):
            raise UserError(_('Phiếu đã ghi sổ không xóa được, hãy Hủy.'))
        return super().unlink()

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được ghi sổ phiếu thu chi.'))
        Move = self.env['lfood.move']
        for rec in self.filtered(lambda p: p.state == 'draft'):
            if rec.amount <= 0:
                raise UserError(_('Số tiền phải lớn hơn 0.'))
            code = 'PC' if rec.kind == 'out' else 'PT'
            if rec.method == 'bank':
                code = 'UNC' if rec.kind == 'out' else 'BC'
            name = self.env['ir.sequence'].with_company(rec.company_id).next_by_code('lfood.payment.%s' % code.lower()) or '/'
            rec.with_context(lfood_ledger_system=True).write({'name': name, 'state': 'posted'})
            counter_acc = self.env['lfood.account'].by_code(rec.counterpart_account)
            partner = rec.partner_id if counter_acc.track_partner else None
            label = rec.memo
            if rec.kind == 'out':
                lines = [(rec.counterpart_account, rec.amount, 0, partner, label, rec.cost_item_id),
                         (rec.cash_account, 0, rec.amount, None, label, None)]
            else:
                lines = [(rec.cash_account, rec.amount, 0, None, label, None),
                         (rec.counterpart_account, 0, rec.amount, partner, label, rec.cost_item_id)]
            Move._create_from_source(rec, 'cash' if rec.method == 'cash' else 'bank', rec.date, lines,
                                     memo='%s %s' % (name, rec.memo), ref=name)
            summary = _('Ghi sổ %s, %s %s') % (name, dict(KINDS)[rec.kind].lower(), vnd(rec.amount))
            if rec.cash_warning:
                summary += _(' — CHI TIỀN MẶT từ ngưỡng không dùng tiền mặt: không đủ điều kiện khấu trừ thuế GTGT và tính chi phí được trừ')
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=name,
                                                      company_id=rec.company_id.id, summary=summary)
        return True

    def action_cancel(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được hủy phiếu đã ghi sổ.'))
        for rec in self.filtered(lambda p: p.state == 'posted'):
            self.env['lfood.move']._active_for(rec)._reverse(memo=_('Hủy phiếu %s') % rec.name)
            rec.with_context(lfood_ledger_system=True).write({'state': 'cancel'})
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=rec.name,
                                                      company_id=rec.company_id.id, summary=_('Hủy phiếu %s') % rec.name)
        return True

    def action_view_moves(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Bút toán'), 'res_model': 'lfood.move', 'view_mode': 'list,form',
                'domain': [('source_model', '=', self._name), ('source_id', '=', self.id)]}
