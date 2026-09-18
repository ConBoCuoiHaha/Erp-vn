"""Bán hàng xuất khẩu (BH14).

Hàng hóa xuất khẩu áp dụng thuế suất 0% (Luật Thuế GTGT 48/2024/QH15, Điều 9 khoản 1). Điều kiện khấu trừ, hoàn thuế
đầu vào của hàng xuất khẩu (Điều 14 khoản 2 điểm c): hợp đồng ký với bên nước ngoài, hóa đơn, chứng từ thanh toán không
dùng tiền mặt, tờ khai hải quan, phiếu đóng gói, vận đơn, chứng từ bảo hiểm (nếu có). Hồ sơ xuất khẩu gắn với hóa đơn
bán ra thuế suất 0% và kiểm tra đủ bộ chứng từ; thanh toán lấy từ phiếu thu chuyển khoản gắn với hóa đơn.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LfoodExportDeclaration(models.Model):
    _name = 'lfood.export.declaration'
    _description = 'Hồ sơ hàng xuất khẩu'
    _order = 'date desc, id desc'

    name = fields.Char('Số tờ khai xuất khẩu', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    date = fields.Date('Ngày tờ khai', required=True)
    sale_invoice_id = fields.Many2one('lfood.sale.invoice', 'Hóa đơn bán ra', required=True, index=True,
                                      domain="[('state', '=', 'posted'), ('kind', '=', 'invoice')]")
    partner_id = fields.Many2one(related='sale_invoice_id.partner_id', string='Người mua nước ngoài')
    amount = fields.Float(related='sale_invoice_id.amount_total', string='Giá trị hóa đơn')
    contract_ref = fields.Char('Số hợp đồng với bên nước ngoài')
    contract_file = fields.Binary('Hợp đồng', attachment=True)
    contract_name = fields.Char()
    declaration_file = fields.Binary('Tờ khai hải quan', attachment=True)
    declaration_name = fields.Char()
    bill_of_lading = fields.Char('Số vận đơn')
    packing_list = fields.Boolean('Có phiếu đóng gói')
    insurance_ref = fields.Char('Chứng từ bảo hiểm (nếu có)')
    paid_non_cash = fields.Float('Đã thu không dùng tiền mặt', digits=(16, 0), compute='_compute_check')
    zero_rate_ok = fields.Boolean('Hóa đơn thuế suất 0%', compute='_compute_check')
    missing = fields.Char('Còn thiếu', compute='_compute_check')
    complete = fields.Boolean('Đủ hồ sơ', compute='_compute_check')

    _uniq = models.Constraint('unique(company_id, name)', 'Số tờ khai đã được ghi nhận.')

    def _compute_check(self):
        Payment = self.env['lfood.payment'].sudo()
        for rec in self:
            inv = rec.sale_invoice_id
            pays = Payment.search([('sale_invoice_id', '=', inv.id), ('state', '=', 'posted'), ('kind', '=', 'in'),
                                   ('method', '=', 'bank')])
            rec.paid_non_cash = sum(pays.mapped('amount'))
            rec.zero_rate_ok = bool(inv.line_ids) and all(
                l.vat_rate_id.rate == 0 and l.vat_rate_id != self.env.ref('lfood_voucher.vat_kct', raise_if_not_found=False)
                for l in inv.line_ids)
            miss = []
            if not rec.zero_rate_ok:
                miss.append(_('hóa đơn chưa đúng thuế suất 0%'))
            if not (rec.contract_ref and rec.contract_file):
                miss.append(_('hợp đồng'))
            if not rec.declaration_file:
                miss.append(_('tờ khai hải quan'))
            if not rec.bill_of_lading:
                miss.append(_('vận đơn'))
            if not rec.packing_list:
                miss.append(_('phiếu đóng gói'))
            if rec.paid_non_cash + 0.5 < inv.amount_total:
                miss.append(_('chứng từ thanh toán không dùng tiền mặt (còn %s)') % '{:,.0f}'.format(
                    inv.amount_total - rec.paid_non_cash).replace(',', '.'))
            rec.missing = ', '.join(miss)
            rec.complete = not miss

    @api.constrains('sale_invoice_id')
    def _check_invoice(self):
        for rec in self:
            if rec.sale_invoice_id.company_id != rec.company_id:
                raise UserError(_('Hóa đơn không thuộc công ty của hồ sơ.'))
