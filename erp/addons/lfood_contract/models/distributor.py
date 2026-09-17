"""Hợp đồng nhà phân phối (BH07) và chương trình trade marketing (BH12).

Thưởng doanh số là chiết khấu thương mại: khi đạt mức theo hợp đồng, người bán lập hóa đơn điều chỉnh giảm cho hàng đã
bán (Thông tư 91/2026/TT-BTC, Điều 10 khoản 5 điểm b), ghi giảm doanh thu Nợ 521, Nợ 33311 / Có 131
(Thông tư 99/2025/TT-BTC). App tính doanh số chưa thuế theo hóa đơn đã ghi sổ trong kỳ (trừ hàng trả lại, giảm giá),
chọn bậc thưởng và lập hóa đơn điều chỉnh giảm nháp, tách theo thuế suất.
Hỗ trợ trưng bày, trade marketing do nhà phân phối lập hóa đơn dịch vụ cho công ty là chi phí bán hàng; app theo dõi
ngân sách và số chi (phiếu chi gắn chương trình) theo khoản mục.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd


class LfoodDistributorContract(models.Model):
    _name = 'lfood.distributor.contract'
    _description = 'Hợp đồng nhà phân phối'
    _order = 'date_from desc, id desc'

    name = fields.Char('Số', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    partner_id = fields.Many2one('res.partner', 'Nhà phân phối', required=True, index=True)
    contract_ref = fields.Char('Số hợp đồng ký', required=True)
    date_from = fields.Date('Kỳ thưởng từ', required=True)
    date_to = fields.Date('Đến', required=True)
    tier_ids = fields.One2many('lfood.distributor.tier', 'contract_id', 'Bậc thưởng doanh số', copy=True)
    revenue = fields.Float('Doanh số chưa thuế trong kỳ', digits=(16, 0), readonly=True)
    rate = fields.Float('Tỷ lệ thưởng đạt (%)', digits=(5, 2), readonly=True)
    rebate = fields.Float('Tiền thưởng chưa thuế', digits=(16, 0), readonly=True)
    refund_id = fields.Many2one('lfood.sale.invoice', 'Hóa đơn điều chỉnh giảm', readonly=True, copy=False)
    state = fields.Selection([('draft', 'Nháp'), ('active', 'Đang thực hiện'), ('settled', 'Đã quyết toán thưởng')],
                             'Trạng thái', default='draft', required=True, readonly=True, copy=False, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('lfood.distributor.contract') or '/'
        return super().create(vals_list)

    def action_activate(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.tier_ids:
                raise UserError(_('Nhập bậc thưởng doanh số.'))
            rec.state = 'active'
        return True

    def _revenue_by_rate(self):
        """{thuế suất: doanh số chưa thuế} sau khi trừ hàng trả lại, giảm giá trong kỳ."""
        invoices = self.env['lfood.sale.invoice'].sudo().search([
            ('company_id', '=', self.company_id.id), ('partner_id', '=', self.partner_id.id), ('state', '=', 'posted'),
            ('date', '>=', self.date_from), ('date', '<=', self.date_to)])
        out = {}
        for inv in invoices:
            sign = 1 if inv.kind == 'invoice' else -1
            for l in inv.line_ids:
                out[l.vat_rate_id] = out.get(l.vat_rate_id, 0) + sign * l.amount
        return out

    def action_compute(self):
        for rec in self.filtered(lambda r: r.state == 'active'):
            revenue = round(sum(rec._revenue_by_rate().values()))
            reached = rec.tier_ids.filtered(lambda t: t.threshold <= revenue).sorted('threshold')[-1:]
            rate = reached.rate if reached else 0
            rec.write({'revenue': revenue, 'rate': rate, 'rebate': round(revenue * rate / 100)})
        return True

    def action_settle(self):
        """Lập hóa đơn điều chỉnh giảm nháp theo từng thuế suất; kế toán ghi số hóa đơn điện tử rồi ghi sổ."""
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_('Chỉ quyết toán hợp đồng đang thực hiện.'))
        self.action_compute()
        if not self.rebate:
            raise UserError(_('Doanh số %s chưa đạt bậc thưởng.') % vnd(self.revenue))
        by_rate = self._revenue_by_rate()
        origin = self.env['lfood.sale.invoice'].sudo().search([
            ('company_id', '=', self.company_id.id), ('partner_id', '=', self.partner_id.id), ('state', '=', 'posted'),
            ('kind', '=', 'invoice'), ('date', '>=', self.date_from), ('date', '<=', self.date_to)], order='date desc', limit=1)
        lines = [(0, 0, {'name': _('Chiết khấu thương mại theo doanh số %s, hợp đồng %s') % (
                         '%g%%' % self.rate, self.contract_ref),
                         'quantity': 1, 'price_unit': round(base * self.rate / 100), 'vat_rate_id': rate.id})
                 for rate, base in by_rate.items() if round(base * self.rate / 100)]
        refund = self.env['lfood.sale.invoice'].create({
            'company_id': self.company_id.id, 'kind': 'refund', 'correction_reason': 'discount', 'origin_id': origin.id, 'partner_id': self.partner_id.id,
            'date': self.date_to, 'invoice_date': self.date_to,
            'memo': _('Thưởng doanh số kỳ %s - %s') % (self.date_from.strftime('%d/%m/%Y'), self.date_to.strftime('%d/%m/%Y')),
            'line_ids': lines})
        self.write({'refund_id': refund.id, 'state': 'settled'})
        self.env['lfood.audit.log']._record_event(
            'state', model=self._name, res_id=self.id, res_name=self.name, company_id=self.company_id.id,
            summary=_('Quyết toán thưởng %s: doanh số %s, thưởng %s') % (self.partner_id.name, vnd(self.revenue),
                                                                         vnd(self.rebate)))
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.sale.invoice', 'res_id': refund.id, 'view_mode': 'form'}


class LfoodDistributorTier(models.Model):
    _name = 'lfood.distributor.tier'
    _description = 'Bậc thưởng doanh số'
    _order = 'threshold'

    contract_id = fields.Many2one('lfood.distributor.contract', required=True, ondelete='cascade', index=True)
    threshold = fields.Float('Doanh số chưa thuế từ', digits=(16, 0), required=True)
    rate = fields.Float('Thưởng (%)', digits=(5, 2), required=True)

    @api.constrains('rate')
    def _check_rate(self):
        for rec in self:
            if not 0 < rec.rate < 100:
                raise ValidationError(_('Tỷ lệ thưởng phải trong khoảng 0-100%.'))


class LfoodTradeProgram(models.Model):
    _name = 'lfood.trade.program'
    _description = 'Chương trình trade marketing, trưng bày'
    _order = 'date_from desc, id desc'

    name = fields.Char('Tên chương trình', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    channel_id = fields.Many2one('lfood.sale.channel', 'Kênh')
    partner_id = fields.Many2one('res.partner', 'Nhà phân phối, siêu thị')
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục chi phí', required=True)
    date_from = fields.Date('Từ ngày', required=True)
    date_to = fields.Date('Đến ngày', required=True)
    budget = fields.Float('Ngân sách', digits=(16, 0), required=True)
    payment_ids = fields.One2many('lfood.payment', 'trade_program_id', 'Phiếu chi')
    spent = fields.Float('Đã chi', digits=(16, 0), compute='_compute_spent')
    remaining = fields.Float('Còn lại', digits=(16, 0), compute='_compute_spent')

    @api.depends('payment_ids.state', 'payment_ids.amount')
    def _compute_spent(self):
        for rec in self:
            rec.spent = sum(rec.payment_ids.filtered(lambda p: p.state == 'posted' and p.kind == 'out').mapped('amount'))
            rec.remaining = rec.budget - rec.spent


class LfoodPayment(models.Model):
    _inherit = 'lfood.payment'

    trade_program_id = fields.Many2one('lfood.trade.program', 'Chương trình trade marketing', index=True)

    @api.onchange('trade_program_id')
    def _onchange_trade_program(self):
        if self.trade_program_id:
            self.cost_item_id = self.trade_program_id.cost_item_id

    def action_post(self):
        for rec in self.filtered(lambda p: p.state == 'draft' and p.trade_program_id and p.kind == 'out'):
            prog = rec.trade_program_id
            if not prog.date_from <= rec.date <= prog.date_to:
                raise UserError(_('Ngày chi nằm ngoài thời gian chương trình %s.') % prog.name)
            if rec.amount > prog.remaining + 0.5:
                raise UserError(_('Chương trình %s chỉ còn %s ngân sách.') % (prog.name, vnd(prog.remaining)))
            if not rec.cost_item_id:
                rec.cost_item_id = prog.cost_item_id
        return super().action_post()
