"""Tạm ứng và thanh toán tạm ứng (KT07) theo tài khoản 141, Thông tư 99/2025/TT-BTC.

Doanh nghiệp tự quy định người được tạm ứng, mức, thời hạn hoàn ứng và người duyệt; app theo dõi từng lần tạm ứng
của từng người. Chi tạm ứng: Nợ 141 / Có 111, 112 (phiếu chi). Thanh toán tạm ứng theo bảng kê chứng từ gốc đã duyệt:
Nợ chi phí, 1331 / Có 141. Chi không hết thì nộp lại quỹ (Nợ 111 / Có 141) hoặc trừ lương (Nợ 334 / Có 141);
chi quá số tạm ứng thì chi bổ sung (Nợ 141 / Có 111, 112). Hóa đơn GTGT trong bảng thanh toán được đưa lên bảng kê
mua vào; hóa đơn từ ngưỡng không dùng tiền mặt mà trả tiền mặt thì không được khấu trừ.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd

EXPENSE_ACCOUNTS = [('6427', '6427 Dịch vụ mua ngoài (quản lý)'), ('6428', '6428 Chi phí bằng tiền khác (quản lý)'),
                    ('6417', '6417 Dịch vụ mua ngoài (bán hàng)'), ('6418', '6418 Chi phí bằng tiền khác (bán hàng)'),
                    ('6423', '6423 Đồ dùng văn phòng'), ('6278', '6278 Chi phí bằng tiền khác (sản xuất)'),
                    ('153', '153 Công cụ, dụng cụ'), ('242', '242 Chi phí trả trước')]


class ResCompany(models.Model):
    _inherit = 'res.company'

    lfood_advance_block_overdue = fields.Boolean(
        'Chặn tạm ứng mới khi còn tạm ứng quá hạn', default=True,
        help='Quy chế nội bộ: người còn khoản tạm ứng quá hạn chưa thanh toán thì không được duyệt tạm ứng mới')


class LfoodAdvance(models.Model):
    _name = 'lfood.advance'
    _description = 'Tạm ứng'
    _order = 'date desc, id desc'

    name = fields.Char('Số', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    employee_id = fields.Many2one('lfood.employee', 'Người tạm ứng', required=True, index=True,
                                  domain="[('company_id', '=', company_id)]")
    partner_id = fields.Many2one(related='employee_id.partner_id')
    date = fields.Date('Ngày đề nghị', required=True, default=fields.Date.context_today, index=True)
    reason = fields.Char('Lý do tạm ứng', required=True)
    amount = fields.Float('Số tiền đề nghị', digits=(16, 0), required=True)
    due_date = fields.Date('Hạn thanh toán tạm ứng', required=True)
    method = fields.Selection([('cash', 'Tiền mặt'), ('bank', 'Chuyển khoản')], 'Hình thức chi', default='cash', required=True)
    approved_by = fields.Many2one('res.users', 'Người duyệt', readonly=True, copy=False)
    payment_ids = fields.One2many('lfood.payment', 'advance_id', 'Phiếu thu chi')
    paid = fields.Float('Đã chi tạm ứng', digits=(16, 0), compute='_compute_money')
    returned = fields.Float('Đã nộp lại, trừ lương', digits=(16, 0), compute='_compute_money')
    line_ids = fields.One2many('lfood.advance.line', 'advance_id', 'Bảng kê chứng từ đã chi', copy=False)
    spent = fields.Float('Đã chi theo chứng từ', digits=(16, 0), compute='_compute_money')
    remaining = fields.Float('Còn phải hoàn ứng (+) / chi bổ sung (-)', digits=(16, 0), compute='_compute_money')
    settle_date = fields.Date('Ngày thanh toán tạm ứng', copy=False)
    salary_deduct = fields.Boolean('Trừ lương phần chi không hết', copy=False)
    state = fields.Selection([('draft', 'Nháp'), ('approved', 'Đã duyệt'), ('paid', 'Đã chi'), ('settled', 'Đã thanh toán'),
                              ('closed', 'Hoàn tất'), ('refused', 'Từ chối')], 'Trạng thái', default='draft',
                             required=True, readonly=True, copy=False, index=True)

    @api.depends('payment_ids.state', 'payment_ids.amount', 'line_ids.total', 'state')
    def _compute_money(self):
        for rec in self:
            posted = rec.payment_ids.filtered(lambda p: p.state == 'posted')
            deduct = self.env['lfood.move']._active_for(rec).filtered(lambda m: m.source_key == 'deduct') if rec.id else []
            deducted = sum(deduct.line_ids.filtered(lambda l: l.account_code == '141').mapped('credit')) if deduct else 0
            rec.paid = sum(posted.filtered(lambda p: p.kind == 'out').mapped('amount'))
            rec.returned = sum(posted.filtered(lambda p: p.kind == 'in').mapped('amount')) + deducted
            rec.spent = sum(rec.line_ids.mapped('total'))
            booked = rec.spent if rec.state in ('settled', 'closed') else 0
            rec.remaining = rec.paid - rec.returned - booked

    @api.constrains('amount', 'date', 'due_date')
    def _check_values(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Số tiền tạm ứng phải lớn hơn 0.'))
            if rec.due_date < rec.date:
                raise ValidationError(_('Hạn thanh toán tạm ứng phải sau ngày đề nghị.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.advance') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_advance_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái tạm ứng chỉ đổi bằng các nút trên màn hình.'))
            locked = self.filtered(lambda r: r.state not in ('draft', 'paid'))
            if locked or (self.filtered(lambda r: r.state == 'paid') and set(vals) - {'line_ids', 'settle_date', 'salary_deduct'}):
                raise UserError(_('Tạm ứng đã duyệt không sửa được nội dung đề nghị.'))
        return super().write(vals)

    def _overdue_open(self):
        """Các lần tạm ứng khác của cùng người đã quá hạn mà chưa thanh toán."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        return self.search([('employee_id', '=', self.employee_id.id), ('id', '!=', self.id),
                            ('state', 'in', ('approved', 'paid')), ('due_date', '<', today)])

    def action_approve(self):
        if not (self.env.user.has_group('lfood_base.group_chief_accountant')
                or self.env.user.has_group('lfood_base.group_director')):
            raise UserError(_('Chỉ Kế toán trưởng hoặc Giám đốc được duyệt tạm ứng.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            overdue = rec._overdue_open()
            if overdue and rec.company_id.lfood_advance_block_overdue:
                raise UserError(_('%s còn tạm ứng quá hạn chưa thanh toán: %s.') % (
                    rec.employee_id.name, ', '.join(overdue.mapped('name'))))
            rec.with_context(lfood_advance_system=True).write({'state': 'approved', 'approved_by': self.env.uid})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Duyệt tạm ứng %s cho %s: %s') % (rec.name, rec.employee_id.name, vnd(rec.amount)))
        return True

    def action_refuse(self):
        if not (self.env.user.has_group('lfood_base.group_chief_accountant')
                or self.env.user.has_group('lfood_base.group_director')):
            raise UserError(_('Chỉ Kế toán trưởng hoặc Giám đốc được từ chối tạm ứng.'))
        self.filtered(lambda r: r.state == 'draft').with_context(lfood_advance_system=True).write({'state': 'refused'})
        return True

    def _new_payment(self, kind, amount, memo, method=None):
        self.ensure_one()
        return self.env['lfood.payment'].create({
            'company_id': self.company_id.id, 'kind': kind, 'method': method or self.method, 'purpose': 'advance',
            'partner_id': self.partner_id.id, 'person': self.employee_id.name, 'amount': amount, 'memo': memo,
            'date': fields.Date.context_today(self), 'advance_id': self.id})

    def action_pay(self):
        """Lập phiếu chi tạm ứng nháp; phiếu được ghi sổ thì tạm ứng chuyển sang Đã chi."""
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('Chỉ chi cho tạm ứng đã duyệt.'))
        if self.payment_ids.filtered(lambda p: p.kind == 'out' and p.state == 'draft'):
            raise UserError(_('Đã có phiếu chi nháp cho tạm ứng này.'))
        payment = self._new_payment('out', self.amount, _('Chi tạm ứng %s: %s') % (self.name, self.reason))
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.payment', 'res_id': payment.id, 'view_mode': 'form'}

    def _on_payment_posted(self):
        for rec in self:
            if rec.state == 'approved' and rec.paid > 0:
                rec.with_context(lfood_advance_system=True).write({'state': 'paid'})
            elif rec.state == 'settled' and not round(rec.remaining):
                rec.with_context(lfood_advance_system=True).write({'state': 'closed'})

    def action_settle(self):
        """Ghi sổ bảng thanh toán tạm ứng: Nợ chi phí, 1331 / Có 141; phần chênh lệch lập phiếu hoặc trừ lương."""
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được ghi sổ thanh toán tạm ứng.'))
        for rec in self:
            if rec.state != 'paid':
                raise UserError(_('Chỉ thanh toán tạm ứng đã chi.'))
            if not rec.line_ids:
                raise UserError(_('Nhập bảng kê chứng từ đã chi.'))
            day = rec.settle_date or fields.Date.context_today(self)
            label = _('Thanh toán tạm ứng %s của %s') % (rec.name, rec.employee_id.name)
            lines = []
            for l in rec.line_ids:
                lines.append((l.account, l.amount, 0, None, l.name, l.cost_item_id))
                if l.tax:
                    lines.append(('1331', l.tax, 0, None, _('Thuế GTGT %s') % l.name, None))
            lines.append(('141', 0, rec.spent, rec.partner_id, label, None))
            self.env['lfood.move']._create_from_source(rec, 'general', day, lines, memo=label, key='settle', ref=rec.name)
            rec.with_context(lfood_advance_system=True).write({'state': 'settled', 'settle_date': day})
            diff = round(rec.paid - rec.spent - rec.returned)
            if diff > 0 and rec.salary_deduct:
                text = _('Trừ lương tạm ứng chi không hết %s') % rec.name
                self.env['lfood.move']._create_from_source(
                    rec, 'general', day, [('334', diff, 0, rec.partner_id, text, None),
                                          ('141', 0, diff, rec.partner_id, text, None)],
                    memo=text, key='deduct', ref=rec.name)
            elif diff > 0:
                rec._new_payment('in', diff, _('Nộp lại tạm ứng chi không hết %s') % rec.name, method='cash')
            elif diff < 0:
                rec._new_payment('out', -diff, _('Chi bổ sung tạm ứng %s') % rec.name)
            if not diff or (diff > 0 and rec.salary_deduct):
                rec.with_context(lfood_advance_system=True).write({'state': 'closed'})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('%s: đã chi %s, chứng từ %s, chênh lệch %s') % (label, vnd(rec.paid), vnd(rec.spent), vnd(diff)))
        return True


class LfoodAdvanceLine(models.Model):
    _name = 'lfood.advance.line'
    _description = 'Chứng từ trong bảng thanh toán tạm ứng'

    advance_id = fields.Many2one('lfood.advance', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='advance_id.company_id', store=True)
    date = fields.Date('Ngày chứng từ', required=True)
    name = fields.Char('Nội dung chi', required=True)
    account = fields.Selection(EXPENSE_ACCOUNTS, 'TK chi phí', required=True, default='6428')
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP')
    invoice_ref = fields.Char('Ký hiệu, số hóa đơn')
    seller_id = fields.Many2one('res.partner', 'Người bán')
    amount = fields.Float('Tiền chưa thuế', digits=(16, 0), required=True)
    vat_rate_id = fields.Many2one('lfood.vat.rate', 'Thuế suất')
    tax = fields.Float('Thuế GTGT', digits=(16, 0), compute='_compute_tax', store=True, readonly=False)
    total = fields.Float('Tổng tiền', digits=(16, 0), compute='_compute_total', store=True)
    pay_method = fields.Selection([('cash', 'Tiền mặt'), ('bank', 'Chuyển khoản, thẻ của công ty')], 'Người tạm ứng trả bằng',
                                  default='cash', required=True)

    @api.depends('amount', 'vat_rate_id')
    def _compute_tax(self):
        for rec in self:
            rec.tax = round(rec.amount * (rec.vat_rate_id.rate or 0) / 100)

    @api.depends('amount', 'tax')
    def _compute_total(self):
        for rec in self:
            rec.total = rec.amount + rec.tax

    @api.constrains('amount', 'tax', 'invoice_ref', 'seller_id')
    def _check_line(self):
        for rec in self:
            if rec.amount <= 0 or rec.tax < 0:
                raise ValidationError(_('Số tiền chứng từ phải lớn hơn 0.'))
            if rec.tax and not (rec.invoice_ref and rec.seller_id):
                raise ValidationError(_('Dòng có thuế GTGT phải ghi số hóa đơn và người bán.'))

    def write(self, vals):
        if self.filtered(lambda l: l.advance_id.state not in ('draft', 'paid')):
            raise UserError(_('Bảng thanh toán đã ghi sổ không sửa được.'))
        return super().write(vals)


class LfoodPayment(models.Model):
    _inherit = 'lfood.payment'

    advance_id = fields.Many2one('lfood.advance', 'Tạm ứng', index=True, readonly=True, copy=False)

    def action_post(self):
        res = super().action_post()
        self.mapped('advance_id')._on_payment_posted()
        return res


class LfoodVatReturn(models.Model):
    _inherit = 'lfood.vat.return'

    def _purchase_lines(self):
        vals = super()._purchase_lines()
        lines = self.env['lfood.advance.line'].sudo().search([
            ('company_id', '=', self.company_id.id), ('tax', '>', 0),
            ('advance_id.state', 'in', ('settled', 'closed')),
            ('advance_id.settle_date', '>=', self.date_from), ('advance_id.settle_date', '<=', self.date_to)])
        Param = self.env['lfood.legal.param']
        for l in lines:
            limit = Param.get_value('NGUONG_TT_KHONG_TIEN_MAT', l.date, default=5000000)
            ok, reason = True, ''
            if l.total >= limit and l.pay_method == 'cash':
                ok, reason = False, _('Hóa đơn từ %s đồng thanh toán bằng tiền mặt: không đủ điều kiện khấu trừ') % vnd(limit)
            vals.append({'kind': 'in', 'date': l.date, 'ref': l.invoice_ref, 'partner_id': l.seller_id.id,
                         'name': l.name, 'base': l.amount, 'tax': l.tax, 'rate': l.vat_rate_id.rate,
                         'rate_name': l.vat_rate_id.name, 'deductible': ok, 'reason': reason,
                         'source_model': l.advance_id._name, 'source_id': l.advance_id.id})
        return vals
