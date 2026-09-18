"""Điều khoản thanh toán (DM08).

Điều khoản gồm các đợt: tỷ lệ phần trăm và số ngày kể từ ngày hóa đơn (ví dụ 30% ngay, 70% sau 30 ngày). Khách hàng
gắn điều khoản mặc định; hóa đơn bán ra lấy điều khoản của khách, tính hạn thanh toán là đợt cuối cùng và hiện lịch
thanh toán từng đợt để theo dõi thu nợ.
"""
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from odoo.addons.lfood_voucher.models.tools import allocate, vnd


class LfoodPaymentTerm(models.Model):
    _name = 'lfood.payment.term'
    _description = 'Điều khoản thanh toán'
    _order = 'name'

    name = fields.Char('Tên điều khoản', required=True)
    note = fields.Char('Ghi chú')
    line_ids = fields.One2many('lfood.payment.term.line', 'term_id', 'Các đợt', copy=True)
    max_days = fields.Integer('Số ngày đợt cuối', compute='_compute_days', store=True)
    active = fields.Boolean(default=True)

    @api.depends('line_ids.days')
    def _compute_days(self):
        for rec in self:
            rec.max_days = max(rec.line_ids.mapped('days') or [0])

    @api.constrains('line_ids')
    def _check_lines(self):
        for rec in self:
            if rec.line_ids and round(sum(rec.line_ids.mapped('percent')), 2) != 100:
                raise ValidationError(_('Tổng tỷ lệ các đợt của %s phải bằng 100%%.') % rec.name)

    def schedule(self, date, amount):
        """[(ngày đến hạn, số tiền)] chia đúng tới đồng."""
        self.ensure_one()
        lines = self.line_ids.sorted('days')
        shares = allocate(amount, lines.mapped('percent'))
        return [(date + timedelta(days=l.days), s) for l, s in zip(lines, shares)]


class LfoodPaymentTermLine(models.Model):
    _name = 'lfood.payment.term.line'
    _description = 'Đợt thanh toán'
    _order = 'days'

    term_id = fields.Many2one('lfood.payment.term', required=True, ondelete='cascade', index=True)
    name = fields.Char('Đợt', required=True)
    percent = fields.Float('Tỷ lệ (%)', required=True)
    days = fields.Integer('Sau bao nhiêu ngày', default=0)

    @api.constrains('percent', 'days')
    def _check(self):
        for rec in self:
            if not 0 < rec.percent <= 100 or rec.days < 0:
                raise ValidationError(_('Tỷ lệ trong khoảng 0-100%, số ngày không âm.'))


class ResPartner(models.Model):
    _inherit = 'res.partner'

    lfood_payment_term_id = fields.Many2one('lfood.payment.term', 'Điều khoản thanh toán')


class LfoodSaleInvoice(models.Model):
    _inherit = 'lfood.sale.invoice'

    payment_term_id = fields.Many2one('lfood.payment.term', 'Điều khoản thanh toán')
    payment_schedule = fields.Char('Lịch thanh toán', compute='_compute_schedule')

    @api.onchange('partner_id')
    def _onchange_partner_term(self):
        if self.partner_id.lfood_payment_term_id:
            self.payment_term_id = self.partner_id.lfood_payment_term_id

    @api.onchange('payment_term_id', 'date')
    def _onchange_term(self):
        if self.payment_term_id and self.date:
            self.due_date = self.date + timedelta(days=self.payment_term_id.max_days)

    @api.depends('payment_term_id', 'date', 'amount_total')
    def _compute_schedule(self):
        for rec in self:
            if not (rec.payment_term_id and rec.date and rec.amount_total):
                rec.payment_schedule = False
                continue
            rec.payment_schedule = '; '.join('%s: %s' % (d.strftime('%d/%m/%Y'), vnd(a))
                                             for d, a in rec.payment_term_id.schedule(rec.date, rec.amount_total))
