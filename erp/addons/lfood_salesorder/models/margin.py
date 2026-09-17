"""Lãi gộp theo nhãn hàng, kênh, vùng, sản phẩm, khách hàng (BC03).

Doanh thu thuần: dòng hóa đơn bán ra đã ghi sổ trong kỳ (hàng bán trả lại, giảm giá, chiết khấu ghi âm). Giá vốn: giá trị
xuất kho của các phiếu kho gắn với hóa đơn đó (hàng trả lại nhập kho ghi giảm giá vốn). Dòng hóa đơn không gắn mặt hàng
(giảm giá, chiết khấu chung) vào nhóm "Chưa gắn mặt hàng" khi xem theo sản phẩm, nhãn hàng.
Báo cáo quản trị, không phải báo cáo tài chính; số tổng có thể khác sổ 511, 632 nếu có bút toán không đi qua hóa đơn.
"""
from markupsafe import Markup

from odoo import fields, models, _

from odoo.addons.lfood_voucher.models.tools import vnd

DIMENSIONS = [('brand', 'Nhãn hàng'), ('channel', 'Kênh'), ('region', 'Vùng (tỉnh, thành)'), ('product', 'Sản phẩm'),
              ('partner', 'Khách hàng')]


class LfoodProduct(models.Model):
    _inherit = 'lfood.product'

    brand = fields.Char('Nhãn hàng', index=True)


class LfoodMarginReport(models.TransientModel):
    _name = 'lfood.margin.report'
    _description = 'Báo cáo lãi gộp'

    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company)
    date_from = fields.Date('Từ ngày', required=True)
    date_to = fields.Date('Đến ngày', required=True)
    dimension = fields.Selection(DIMENSIONS, 'Xem theo', required=True, default='channel')
    report_html = fields.Html('Báo cáo', readonly=True, sanitize=False)

    def _key(self, dim, partner, product):
        none = _('Chưa gắn mặt hàng')
        if dim == 'brand':
            return (product.brand or _('Chưa đặt nhãn hàng')) if product else none
        if dim == 'product':
            return product.display_name if product else none
        if dim == 'channel':
            return partner.lfood_channel_id.name or _('Chưa đặt kênh')
        if dim == 'region':
            return partner.state_id.name or partner.city or _('Chưa có tỉnh, thành')
        return partner.display_name

    def _rows(self):
        """{nhóm: [doanh thu, giá vốn]}"""
        self.ensure_one()
        invoices = self.env['lfood.sale.invoice'].sudo().search([
            ('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
            ('date', '>=', self.date_from), ('date', '<=', self.date_to)])
        out = {}
        for inv in invoices:
            sign = 1 if inv.kind == 'invoice' else -1
            partner = inv.partner_id.commercial_partner_id
            for l in inv.line_ids:
                k = self._key(self.dimension, partner, l.product_id)
                out.setdefault(k, [0, 0])[0] += sign * l.amount
        vals = self.env['lfood.stock.valuation'].sudo().search([
            ('picking_id.sale_invoice_id', 'in', invoices.ids), ('picking_id.state', '=', 'done')])
        for v in vals:
            partner = v.picking_id.sale_invoice_id.partner_id.commercial_partner_id
            k = self._key(self.dimension, partner, v.product_id)
            out.setdefault(k, [0, 0])[1] -= v.value
        return out

    def action_compute(self):
        for rec in self:
            rows = rec._rows()
            total = [sum(r[0] for r in rows.values()), sum(r[1] for r in rows.values())]

            def line(name, rev, cogs, strong=False):
                pct = '%.1f%%' % ((rev - cogs) * 100 / rev) if rev else ''
                tpl = ('<tr class="fw-bold"><td>%s</td><td class="text-end">%s</td><td class="text-end">%s</td>'
                       '<td class="text-end">%s</td><td class="text-end">%s</td></tr>') if strong else (
                    '<tr><td>%s</td><td class="text-end">%s</td><td class="text-end">%s</td>'
                    '<td class="text-end">%s</td><td class="text-end">%s</td></tr>')
                return Markup(tpl) % (name, vnd(rev), vnd(cogs), vnd(rev - cogs), pct)

            body = Markup('').join(line(k, r[0], r[1]) for k, r in sorted(rows.items(), key=lambda i: -(i[1][0] - i[1][1])))
            rec.report_html = Markup(
                '<table class="table table-sm"><thead><tr><th>%s</th><th class="text-end">%s</th><th class="text-end">%s</th>'
                '<th class="text-end">%s</th><th class="text-end">%s</th></tr></thead><tbody>%s%s</tbody></table>') % (
                dict(DIMENSIONS)[rec.dimension], _('Doanh thu thuần'), _('Giá vốn'), _('Lãi gộp'), _('Tỷ lệ'),
                body, line(_('Cộng'), total[0], total[1], strong=True))
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form',
                'target': 'new'}
