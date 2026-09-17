"""Lịch nghĩa vụ thuế và tiền chậm nộp (THUE12).

Nghĩa vụ tự sinh khi xác nhận tờ khai thuế GTGT, ghi sổ tạm nộp và quyết toán thuế TNDN; nghĩa vụ khác nhập tay.
Nộp thuế bằng phiếu chi nội dung Nộp thuế gắn với nghĩa vụ. Tiền chậm nộp tính theo Luật Quản lý thuế 108/2025/QH15,
Nghị định 252/2026/NĐ-CP; ghi sổ Nợ 811 / Có 3339 và không được tính vào chi phí được trừ khi tính thuế TNDN.
Quyết toán TNDN: phần tạm nộp thiếu so với tỷ lệ tối thiểu tính chậm nộp từ sau hạn tạm nộp quý 4 (Luật Thuế TNDN
67/2025/QH15), phần còn lại theo hạn nộp hồ sơ quyết toán.
"""
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd
from .late_calc import late_interest

TAX_TYPES = [('vat', 'Thuế GTGT'), ('cit', 'Thuế TNDN'), ('pit', 'Thuế TNCN'), ('other', 'Khác')]
TAX_ACCOUNT = {'vat': '33311', 'cit': '3334', 'pit': '3335', 'other': '3338'}
INTEREST_ACCOUNT, INTEREST_EXPENSE = '3339', '811'


class LfoodTaxObligation(models.Model):
    _name = 'lfood.tax.obligation'
    _description = 'Nghĩa vụ nộp thuế'
    _order = 'due_date desc, id desc'

    name = fields.Char('Nội dung', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    tax_type = fields.Selection(TAX_TYPES, 'Loại thuế', required=True, default='vat')
    account = fields.Char('TK thuế', compute='_compute_account', store=True, readonly=False)
    amount = fields.Float('Số phải nộp', digits=(16, 0), required=True)
    due_date = fields.Date('Hạn nộp', required=True, index=True)
    source_model = fields.Char('Nguồn', readonly=True)
    source_id = fields.Integer(readonly=True)
    source_key = fields.Char(readonly=True, index=True)
    payment_ids = fields.One2many('lfood.payment', 'tax_obligation_id', 'Phiếu nộp')
    paid = fields.Float('Đã nộp thuế', digits=(16, 0), compute='_compute_status')
    remaining = fields.Float('Còn phải nộp', digits=(16, 0), compute='_compute_status')
    last_paid = fields.Date('Ngày nộp gần nhất', compute='_compute_status')
    interest = fields.Float('Tiền chậm nộp đến hôm nay', digits=(16, 0), compute='_compute_status')
    interest_posted = fields.Float('Tiền chậm nộp đã ghi sổ', digits=(16, 0), compute='_compute_status')
    interest_paid = fields.Float('Tiền chậm nộp đã nộp', digits=(16, 0), compute='_compute_status')
    detail_html = fields.Html('Cách tính', compute='_compute_status', sanitize=False)
    state = fields.Selection([('open', 'Chưa nộp đủ'), ('paid', 'Đã nộp đủ'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             compute='_compute_state', store=True, index=True)
    cancelled = fields.Boolean('Hủy', readonly=True)

    _key_uniq = models.Constraint('unique(source_key)', 'Nghĩa vụ của chứng từ này đã có.')

    @api.depends('tax_type')
    def _compute_account(self):
        for rec in self:
            rec.account = TAX_ACCOUNT[rec.tax_type]

    def _rate(self, at):
        return self.env['lfood.legal.param'].get_value('TIEN_CHAM_NOP_TY_LE_NGAY', at, default=0.03)

    def interest_at(self, as_of):
        self.ensure_one()
        tax_pays = self.payment_ids.filtered(lambda p: p.state == 'posted' and not p.tax_interest)
        # ponytail: một tỷ lệ cho cả thời gian nợ; tỷ lệ đổi giữa kỳ thì cần tách đoạn theo ngày hiệu lực
        return late_interest(self.amount, self.due_date, [(p.date, p.amount) for p in tax_pays], as_of, self._rate(as_of))

    @api.depends('payment_ids.state', 'payment_ids.amount', 'amount', 'due_date')
    def _compute_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            posted = rec.payment_ids.filtered(lambda p: p.state == 'posted')
            tax_pays = posted.filtered(lambda p: not p.tax_interest)
            rec.paid = sum(tax_pays.mapped('amount'))
            rec.remaining = rec.amount - rec.paid
            rec.last_paid = max(tax_pays.mapped('date')) if tax_pays else False
            rec.interest_paid = sum(posted.filtered('tax_interest').mapped('amount'))
            moves = self.env['lfood.move']._active_for(rec) if rec.id else self.env['lfood.move']
            rec.interest_posted = sum(moves.line_ids.filtered(lambda l: l.account_code == INTEREST_ACCOUNT).mapped('credit'))
            if not (rec.due_date and rec.amount):
                rec.interest, rec.detail_html = 0, False
                continue
            total, rows = rec.interest_at(today)
            rec.interest = total
            rec.detail_html = '<table class="table table-sm"><thead><tr><th>Số tiền</th><th>Số ngày chậm</th>' \
                              '<th>Tiền chậm nộp</th></tr></thead><tbody>%s</tbody></table>' % ''.join(
                '<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (vnd(a), d, vnd(i)) for a, d, i in rows)

    @api.depends('payment_ids.state', 'payment_ids.amount', 'amount', 'cancelled')
    def _compute_state(self):
        for rec in self:
            paid = sum(rec.payment_ids.filtered(lambda p: p.state == 'posted' and not p.tax_interest).mapped('amount'))
            rec.state = 'cancel' if rec.cancelled else ('paid' if paid >= rec.amount else 'open')

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Số phải nộp phải lớn hơn 0.'))

    def write(self, vals):
        if not self.env.context.get('lfood_tax_system') and self.filtered('source_model') \
                and set(vals) & {'amount', 'due_date', 'tax_type', 'account'}:
            raise UserError(_('Nghĩa vụ sinh từ tờ khai không sửa được số tiền, hạn nộp; sửa tờ khai gốc.'))
        return super().write(vals)

    def action_pay(self):
        self.ensure_one()
        return self._open_payment(self.remaining, False, _('Nộp %s') % self.name)

    def action_pay_interest(self):
        self.ensure_one()
        due = self.interest_posted - self.interest_paid
        if due <= 0:
            raise UserError(_('Chưa có tiền chậm nộp đã ghi sổ mà chưa nộp.'))
        return self._open_payment(due, True, _('Nộp tiền chậm nộp %s') % self.name)

    def _open_payment(self, amount, interest, memo):
        if amount <= 0:
            raise UserError(_('Không còn số phải nộp.'))
        payment = self.env['lfood.payment'].create({
            'company_id': self.company_id.id, 'kind': 'out', 'method': 'bank', 'purpose': 'tax', 'amount': amount,
            'memo': memo, 'tax_obligation_id': self.id, 'tax_interest': interest,
            'date': fields.Date.context_today(self)})
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.payment', 'res_id': payment.id, 'view_mode': 'form'}

    def action_post_interest(self, as_of=None):
        """Ghi sổ phần tiền chậm nộp phát sinh thêm đến ngày as_of: Nợ 811 / Có 3339."""
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được ghi sổ tiền chậm nộp.'))
        as_of = as_of or fields.Date.context_today(self)
        for rec in self:
            total, _rows = rec.interest_at(as_of)
            extra = round(total - rec.interest_posted)
            if extra <= 0:
                continue
            label = _('Tiền chậm nộp %s đến ngày %s') % (rec.name, as_of.strftime('%d/%m/%Y'))
            self.env['lfood.move']._create_from_source(
                rec, 'general', as_of, [(INTEREST_EXPENSE, extra, 0, None, label, None),
                                        (INTEREST_ACCOUNT, 0, extra, None, label, None)],
                memo=label, key='interest-%s' % as_of, ref=rec.name)
            rec.invalidate_recordset(['interest_posted'])
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('%s: %s (không được trừ khi tính thuế TNDN)') % (label, vnd(extra)))
        return True

    @api.model
    def _sync_from(self, source, key, tax_type, name, amount, due):
        """Tạo hoặc hủy nghĩa vụ tự sinh cho một chứng từ nguồn."""
        key = '%s-%s-%s' % (source._name, source.id, key)
        rec = self.sudo().search([('source_key', '=', key)])
        if amount <= 0:
            if rec:
                rec.with_context(lfood_tax_system=True).write({'cancelled': True})
            return rec
        vals = {'company_id': source.company_id.id, 'tax_type': tax_type, 'name': name, 'amount': amount,
                'due_date': due, 'source_model': source._name, 'source_id': source.id, 'source_key': key,
                'cancelled': False}
        if rec:
            rec.with_context(lfood_tax_system=True).write(vals)
            return rec
        return self.sudo().create(vals)


class LfoodPayment(models.Model):
    _inherit = 'lfood.payment'

    purpose = fields.Selection(selection_add=[('tax', 'Nộp thuế, tiền chậm nộp')],
                               ondelete={'tax': lambda recs: recs.write({'purpose': 'other'})})
    tax_obligation_id = fields.Many2one('lfood.tax.obligation', 'Nghĩa vụ thuế', index=True,
                                        domain="[('company_id', '=', company_id), ('state', '=', 'open')]")
    tax_interest = fields.Boolean('Nộp tiền chậm nộp')

    @api.depends('method', 'purpose', 'tax_obligation_id', 'tax_interest')
    def _compute_accounts(self):
        super()._compute_accounts()
        for rec in self.filtered(lambda p: p.purpose == 'tax'):
            rec.counterpart_account = INTEREST_ACCOUNT if rec.tax_interest else (rec.tax_obligation_id.account or '3338')

    def action_post(self):
        for rec in self.filtered(lambda p: p.state == 'draft' and p.purpose == 'tax'):
            if not rec.tax_obligation_id:
                raise UserError(_('Phiếu nộp thuế phải chọn nghĩa vụ thuế.'))
            if not rec.tax_interest and rec.amount > rec.tax_obligation_id.remaining + 0.5:
                raise UserError(_('Số nộp lớn hơn số còn phải nộp %s.') % vnd(rec.tax_obligation_id.remaining))
        return super().action_post()


class LfoodVatReturn(models.Model):
    _inherit = 'lfood.vat.return'

    def action_confirm(self):
        res = super().action_confirm()
        for rec in self.filtered(lambda r: r.state == 'confirmed'):
            self.env['lfood.tax.obligation']._sync_from(
                rec, 'tax', 'vat', _('Thuế GTGT %s') % rec.name, rec.values.get('40', 0), rec.due_date)
        return res

    def action_reset(self):
        res = super().action_reset()
        for rec in self.filtered(lambda r: r.state == 'draft'):
            self.env['lfood.tax.obligation']._sync_from(rec, 'tax', 'vat', '', 0, rec.due_date)
        return res


class LfoodCitProvisional(models.Model):
    _inherit = 'lfood.cit.provisional'

    def action_post(self):
        res = super().action_post()
        for rec in self.filtered(lambda r: r.state == 'posted'):
            self.env['lfood.tax.obligation']._sync_from(
                rec, 'tax', 'cit', _('Tạm nộp thuế TNDN quý %s/%s') % (rec.quarter, rec.year), rec.tax, rec.date_due)
        return res

    def action_cancel(self):
        res = super().action_cancel()
        for rec in self.filtered(lambda r: r.state == 'cancel'):
            self.env['lfood.tax.obligation']._sync_from(rec, 'tax', 'cit', '', 0, rec.date_due)
        return res


class LfoodCitFinalization(models.Model):
    _inherit = 'lfood.cit.finalization'

    def action_post(self):
        res = super().action_post()
        Obl = self.env['lfood.tax.obligation']
        for rec in self.filtered(lambda r: r.state == 'posted'):
            shortfall = min(rec.shortfall_amount, rec.tax_remaining)
            q4_due = Obl.env['lfood.cit.provisional'].new({'year': rec.year, 'quarter': '4'}).date_due
            Obl._sync_from(rec, 'shortfall', 'cit', _('Thuế TNDN năm %s: phần tạm nộp thiếu') % rec.year, shortfall, q4_due)
            Obl._sync_from(rec, 'tax', 'cit', _('Thuế TNDN năm %s còn phải nộp') % rec.year,
                           rec.tax_remaining - shortfall, rec.date_due)
        return res

    def action_cancel(self):
        res = super().action_cancel()
        for rec in self.filtered(lambda r: r.state == 'cancel'):
            for key in ('shortfall', 'tax'):
                self.env['lfood.tax.obligation']._sync_from(rec, key, 'cit', '', 0, rec.date_due)
        return res
