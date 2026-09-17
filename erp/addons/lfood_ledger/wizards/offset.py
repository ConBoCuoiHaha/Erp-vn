"""Bù trừ công nợ với đối tác vừa mua vừa bán (KT06).

Đối tác vừa là khách hàng vừa là nhà cung cấp thì được bù trừ số phải thu với số phải trả theo
thỏa thuận giữa hai bên: ghi Nợ 3311 và Có 1311 đúng phần bù trừ, phần còn lại vẫn theo dõi bình thường.
Số bù trừ không vượt quá số nhỏ hơn giữa phải thu và phải trả tại ngày bù trừ.

Lưu ý thuế: khoản mua từ mức quy định phải thanh toán không dùng tiền mặt mới đủ điều kiện khấu trừ
thuế GTGT và tính chi phí được trừ; bù trừ công nợ là một hình thức thanh toán không dùng tiền mặt
nhưng phải có biên bản bù trừ công nợ hai bên ký, kế toán lưu kèm chứng từ này.
"""
from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd


class LfoodOffset(models.TransientModel):
    _name = 'lfood.offset'
    _description = 'Bù trừ công nợ'

    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company)
    partner_id = fields.Many2one('res.partner', 'Đối tác', required=True)
    date = fields.Date('Ngày bù trừ', required=True, default=fields.Date.context_today)
    receivable = fields.Float('Phải thu (1311)', digits=(16, 0), compute='_compute_balances')
    payable = fields.Float('Phải trả (3311)', digits=(16, 0), compute='_compute_balances')
    max_amount = fields.Float('Bù trừ tối đa', digits=(16, 0), compute='_compute_balances')
    amount = fields.Float('Số tiền bù trừ', digits=(16, 0), required=True)
    memo = fields.Char('Diễn giải', default=lambda s: _('Bù trừ công nợ theo biên bản hai bên'))
    preview = fields.Html('Xem trước', compute='_compute_preview', sanitize=False)

    def _balance(self, prefix):
        self.ensure_one()
        if not (self.partner_id and self.date):
            return 0.0
        lines = self.env['lfood.move.line'].sudo().search([
            ('company_id', '=', self.company_id.id), ('state', '=', 'posted'), ('date', '<=', self.date),
            ('partner_id', '=', self.partner_id.id), ('account_code', '=like', prefix + '%')])
        return sum(lines.mapped('balance'))

    @api.depends('partner_id', 'date', 'company_id')
    def _compute_balances(self):
        for rec in self:
            rec.receivable = max(0.0, rec._balance('131'))
            rec.payable = max(0.0, -rec._balance('331'))
            rec.max_amount = min(rec.receivable, rec.payable)

    @api.depends('receivable', 'payable', 'amount', 'partner_id')
    def _compute_preview(self):
        for rec in self:
            amount = min(rec.amount or 0, rec.max_amount)
            rec.preview = Markup(
                '<div class="o_lfood_changes"><table>'
                '<tr><th>%s</th><th>%s</th><th>%s</th></tr>'
                '<tr><td>3311 %s</td><td style="text-align:right">%s</td><td></td></tr>'
                '<tr><td>1311 %s</td><td></td><td style="text-align:right">%s</td></tr>'
                '</table><p>%s</p></div>') % (
                _('Tài khoản'), _('Nợ'), _('Có'), escape(rec.partner_id.name or ''), vnd(amount),
                escape(rec.partner_id.name or ''), vnd(amount),
                _('Sau bù trừ: còn phải thu %s, còn phải trả %s.')
                % (vnd(rec.receivable - amount), vnd(rec.payable - amount)))

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán mới ghi sổ bù trừ công nợ.'))
        amount = round(self.amount or 0)
        if amount <= 0:
            raise UserError(_('Số tiền bù trừ phải lớn hơn 0.'))
        if amount > round(self.max_amount):
            raise UserError(_('Đối tác %s tại ngày %s chỉ bù trừ được tối đa %s: phải thu %s, phải trả %s.')
                            % (self.partner_id.name, self.date.strftime('%d/%m/%Y'), vnd(self.max_amount),
                               vnd(self.receivable), vnd(self.payable)))
        label = '%s %s' % (self.memo or _('Bù trừ công nợ'), self.partner_id.name)
        move = self.env['lfood.move']._create_from_source(
            self.partner_id, 'general', self.date,
            [('3311', amount, 0, self.partner_id, label, None),
             ('1311', 0, amount, self.partner_id, label, None)],
            memo=label, ref=_('BT %s') % self.date.strftime('%d/%m/%Y'), company=self.company_id,
            key='offset:%s:%s' % (self.partner_id.id, fields.Datetime.now()))
        self.env['lfood.audit.log']._record_event(
            'state', model='lfood.move', res_id=move.id, res_name=move.name, company_id=self.company_id.id,
            summary=_('Bù trừ công nợ %s ngày %s: %s (phải thu %s, phải trả %s)')
                    % (self.partner_id.name, self.date.strftime('%d/%m/%Y'), vnd(amount),
                       vnd(self.receivable), vnd(self.payable)))
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.move', 'res_id': move.id, 'view_mode': 'form'}
