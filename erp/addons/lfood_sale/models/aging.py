"""Tuổi nợ phải thu, phải trả theo từng hóa đơn (báo cáo quản trị, không có mẫu bắt buộc)."""
from datetime import date

from markupsafe import Markup, escape

from odoo import api, fields, models, _

from odoo.addons.lfood_voucher.models.tools import vnd

BUCKETS = [(None, 0, 'Chưa đến hạn'), (1, 30, 'Quá hạn 1–30 ngày'), (31, 60, '31–60 ngày'), (61, 90, '61–90 ngày'), (91, None, 'Trên 90 ngày')]


def bucket_of(days_overdue):
    for i, (lo, hi, _label) in enumerate(BUCKETS):
        if lo is None and days_overdue <= hi:
            return i
        if lo is not None and days_overdue >= lo and (hi is None or days_overdue <= hi):
            return i
    return len(BUCKETS) - 1


class LfoodAging(models.TransientModel):
    _name = 'lfood.aging'
    _description = 'Tuổi nợ'

    kind = fields.Selection([('receivable', 'Phải thu khách hàng'), ('payable', 'Phải trả nhà cung cấp')], 'Loại',
                            required=True, default='receivable')
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company)
    as_of = fields.Date('Tính đến ngày', required=True, default=fields.Date.context_today)
    html = fields.Html('Nội dung', compute='_compute_html', sanitize=False)

    def _items(self):
        """[(đối tượng, số chứng từ, ngày, hạn thanh toán, còn nợ)]"""
        items = []
        Payment = self.env['lfood.payment'].sudo()
        if self.kind == 'receivable':
            for inv in self.env['lfood.sale.invoice'].sudo().search([('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
                                                                     ('kind', '=', 'invoice'), ('date', '<=', self.as_of)]):
                paid = sum(p.amount if p.kind == 'in' else -p.amount for p in Payment.search(
                    [('sale_invoice_id', '=', inv.id), ('state', '=', 'posted'), ('date', '<=', self.as_of)]))
                refunds = sum(self.env['lfood.sale.invoice'].sudo().search(
                    [('origin_id', '=', inv.id), ('state', '=', 'posted'), ('date', '<=', self.as_of)]).mapped('amount_total'))
                residual = round(inv.amount_total - paid - refunds)
                if residual:
                    items.append((inv.partner_id.name, inv.invoice_number or inv.name, inv.date, inv.due_date or inv.date, residual))
        else:
            for v in self.env['lfood.service.voucher'].sudo().search([('company_id', '=', self.company_id.id),
                                                                      ('state', 'in', ('posted', 'editing')),
                                                                      ('accounting_date', '<=', self.as_of)]):
                paid = sum(p.amount if p.kind == 'out' else -p.amount for p in Payment.search(
                    [('voucher_id', '=', v.id), ('state', '=', 'posted'), ('date', '<=', self.as_of)]))
                residual = round(v.report_amount_total - paid)
                if residual:
                    items.append((v.partner_id.name, v.invoice_ref or v.name, v.accounting_date, v.due_date or v.accounting_date, residual))
        return items

    def _summary(self):
        by_partner = {}
        for partner, _ref, _d, due, residual in self._items():
            row = by_partner.setdefault(partner, [0] * len(BUCKETS))
            row[bucket_of((self.as_of - due).days)] += residual
        return by_partner

    @api.depends('kind', 'company_id', 'as_of')
    def _compute_html(self):
        for rec in self:
            if not rec.as_of:
                rec.html = False
                continue
            head = Markup('').join(Markup('<th>%s</th>') % label for _lo, _hi, label in BUCKETS)
            summary = rec._summary()
            totals = [0] * len(BUCKETS)
            body = Markup('')
            for partner in sorted(summary):
                row = summary[partner]
                totals = [a + b for a, b in zip(totals, row)]
                body += Markup('<tr><td>%s</td>%s<td style="text-align:right"><b>%s</b></td></tr>') % (
                    escape(partner), Markup('').join(Markup('<td style="text-align:right">%s</td>') % (vnd(x) if x else '') for x in row),
                    vnd(sum(row)))
            foot = Markup('<tr><td><b>Cộng</b></td>%s<td style="text-align:right"><b>%s</b></td></tr>') % (
                Markup('').join(Markup('<td style="text-align:right"><b>%s</b></td>') % vnd(x) for x in totals), vnd(sum(totals)))
            detail = Markup('').join(
                Markup('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td style="text-align:right">%s</td><td style="text-align:right">%s</td></tr>')
                % (escape(p), escape(ref), d.strftime('%d/%m/%Y'), due.strftime('%d/%m/%Y'), max((rec.as_of - due).days, 0), vnd(r))
                for p, ref, d, due, r in sorted(rec._items(), key=lambda x: (x[0], x[3])))
            rec.html = Markup(
                '<h4>Tổng hợp theo đối tượng</h4><div class="o_lfood_changes"><table><tr><th>Đối tượng</th>%s<th>Tổng</th></tr>%s%s</table></div>'
                '<h4>Chi tiết từng hóa đơn</h4><div class="o_lfood_changes"><table><tr><th>Đối tượng</th><th>Hóa đơn</th><th>Ngày</th>'
                '<th>Hạn thanh toán</th><th>Số ngày quá hạn</th><th>Còn nợ</th></tr>%s</table></div>'
                '<p class="text-muted">Còn nợ = số trên hóa đơn trừ phiếu thu, phiếu chi đã gắn với hóa đơn và hàng bán trả lại, giảm giá. '
                'Thu, chi tiền không gắn hóa đơn vẫn giảm công nợ trên sổ nhưng không trừ vào tuổi nợ: đối chiếu với Sổ chi tiết công nợ.</p>') % (
                head, body, foot, detail)
