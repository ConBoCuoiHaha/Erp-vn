from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd


class LfoodMove(models.Model):
    _inherit = 'lfood.move'

    journal = fields.Selection(selection_add=[('stock', 'Kho')], ondelete={'stock': 'cascade'})


class LfoodSaleInvoice(models.Model):
    _inherit = 'lfood.sale.invoice'

    warehouse_id = fields.Many2one('lfood.warehouse', 'Xuất từ kho')
    picking_ids = fields.One2many('lfood.stock.picking', 'sale_invoice_id', 'Phiếu kho')

    def action_post(self):
        drafts = self.filtered(lambda r: r.state == 'draft')
        for inv in drafts.filtered(lambda r: r.kind == 'refund'):
            lines = inv.line_ids.filtered(lambda l: l.product_id and l.quantity)
            if not lines:
                continue
            if not inv.warehouse_id and inv.origin_id.warehouse_id:
                inv.warehouse_id = inv.origin_id.warehouse_id
            inv._check_return_lots(lines)
        res = super().action_post()
        Picking = self.env['lfood.stock.picking']
        for inv in drafts.filtered(lambda r: r.state == 'posted'):
            lines = inv.line_ids.filtered('product_id')
            if not lines:
                continue
            if not inv.warehouse_id:
                raise UserError(_('Hóa đơn có hàng trong kho: chọn Xuất từ kho.'))
            kind, purpose = ('out', 'sale') if inv.kind == 'invoice' else ('in', 'return_in')
            if inv.kind == 'refund' and not any(l.quantity for l in lines):
                continue
            picking = Picking.create({
                'company_id': inv.company_id.id, 'kind': kind, 'purpose': purpose, 'date': inv.date, 'warehouse_id': inv.warehouse_id.id,
                'partner_id': inv.partner_id.id, 'memo': _('Theo hóa đơn %s') % inv.invoice_number, 'sale_invoice_id': inv.id,
                'line_ids': [(0, 0, {'product_id': l.product_id.id, 'quantity': l.quantity, 'lot_id': l.lot_id.id,
                                     'price_unit': inv.origin_id._shipped_unit_cost(l.product_id, l.lot_id)
                                     if inv.kind == 'refund' and inv.origin_id else 0})
                             for l in lines],
            })
            picking.action_done()
        return res

    def _shipped_by_lot(self, product):
        """{lô: số đã giao theo hóa đơn này trừ số khách đã trả theo các hóa đơn giảm trừ đã ghi sổ}."""
        self.ensure_one()
        Valuation = self.env['lfood.stock.valuation'].sudo()
        shipped = {}
        pickings = self.picking_ids | self.sudo().search([('origin_id', '=', self.id), ('kind', '=', 'refund'),
                                                          ('state', '=', 'posted')]).picking_ids
        for v in Valuation.search([('picking_id', 'in', pickings.filtered(lambda p: p.state == 'done').ids),
                                   ('product_id', '=', product.id)]):
            shipped[v.lot_id] = shipped.get(v.lot_id, 0) - v.qty
        return shipped

    def _shipped_unit_cost(self, product, lot):
        """Giá vốn đơn vị đã ghi khi xuất bán theo hóa đơn này (theo lô nếu có); 0 thì phiếu kho dùng giá bình quân."""
        self.ensure_one()
        domain = [('picking_id', 'in', self.picking_ids.filtered(lambda p: p.state == 'done' and p.kind == 'out').ids),
                  ('product_id', '=', product.id), ('qty', '<', 0)]
        if lot:
            domain.append(('lot_id', '=', lot.id))
        moves = self.env['lfood.stock.valuation'].sudo().search(domain)
        qty = -sum(moves.mapped('qty'))
        return round(-sum(moves.mapped('value')) / qty, 2) if qty else 0

    def _check_return_lots(self, lines):
        """Hàng bán bị trả lại theo dõi lô: lấy lô đã giao theo hóa đơn gốc; không trả quá số đã giao của lô."""
        for line in lines.filtered(lambda l: l.quantity and l.product_id.track_lot):
            if not self.origin_id:
                if not line.lot_id:
                    raise UserError(_('%s theo dõi lô: chọn lô hàng trả lại.') % line.product_id.display_name)
                continue
            shipped = {lot: qty for lot, qty in self.origin_id._shipped_by_lot(line.product_id).items() if round(qty, 3) > 0}
            if not line.lot_id:
                if len(shipped) != 1:
                    raise UserError(_('%s: hóa đơn gốc giao từ các lô %s, chọn lô hàng trả lại.') % (
                        line.product_id.display_name, ', '.join(l.name for l in shipped) or _('(không có)')))
                line.lot_id = next(iter(shipped))
            same = lines.filtered(lambda l: l.product_id == line.product_id and l.lot_id == line.lot_id)
            if sum(same.mapped('quantity')) > shipped.get(line.lot_id, 0) + 1e-6:
                raise UserError(_('%s lô %s: hóa đơn gốc chỉ còn %s chưa trả lại.') % (
                    line.product_id.display_name, line.lot_id.name, '%g' % shipped.get(line.lot_id, 0)))

    def action_cancel(self):
        for inv in self.filtered(lambda r: r.state == 'posted'):
            inv.picking_ids.filtered(lambda p: p.state == 'done').action_cancel()
        return super().action_cancel()


class LfoodSaleInvoiceLine(models.Model):
    _inherit = 'lfood.sale.invoice.line'

    product_id = fields.Many2one('lfood.product', 'Mặt hàng trong kho')
    lot_id = fields.Many2one('lfood.stock.lot', 'Lô', domain="[('product_id', '=', product_id)]",
                             help='Hàng bán bị trả lại: để trống thì lấy lô đã giao theo hóa đơn gốc')

    @api.onchange('product_id')
    def _onchange_product(self):
        if self.product_id:
            self.name = self.product_id.name
            self.uom = self.product_id.uom
            self.vat_rate_id = self.product_id.vat_rate_id or self.vat_rate_id


class LfoodPayment(models.Model):
    _inherit = 'lfood.payment'

    picking_id = fields.Many2one('lfood.stock.picking', 'Thanh toán cho phiếu nhập mua',
                                 domain="[('partner_id', '=', partner_id), ('state', '=', 'done'), ('purpose', '=', 'purchase')]")


class LfoodVatReturn(models.Model):
    _inherit = 'lfood.vat.return'

    def _purchase_lines(self):
        vals = super()._purchase_lines()
        limit_param = self.env['lfood.legal.param']
        pickings = self.env['lfood.stock.picking'].sudo().search([
            ('company_id', '=', self.company_id.id), ('state', '=', 'done'), ('purpose', '=', 'purchase'),
            ('date', '>=', self.date_from), ('date', '<=', self.date_to)])
        Payment = self.env['lfood.payment'].sudo()
        for p in pickings:
            total = p.amount + p.amount_tax
            limit = limit_param.get_value('NGUONG_TT_KHONG_TIEN_MAT', p.date, default=5000000)
            cash = p.payment_method == 'cash' or Payment.search_count([('picking_id', '=', p.id), ('state', '=', 'posted'), ('method', '=', 'cash')])
            ok, reason = True, ''
            if not p.invoice_number:
                ok, reason = False, _('Chưa có hóa đơn GTGT hợp pháp')
            elif total >= limit and cash:
                ok, reason = False, _('Hóa đơn từ %s đồng thanh toán bằng tiền mặt: không đủ điều kiện khấu trừ') % vnd(limit)
            by_rate = {}
            for l in p.line_ids:
                base, tax = by_rate.get(l.vat_rate_id, (0, 0))
                by_rate[l.vat_rate_id] = (base + l.amount, tax + l.tax)
            for rate, (base, tax) in by_rate.items():
                vals.append({'kind': 'in', 'date': p.invoice_date or p.date, 'ref': '%s %s' % (p.invoice_symbol or '', p.invoice_number or p.name),
                             'partner_id': p.partner_id.id, 'name': p.memo or p.name, 'base': base, 'tax': tax, 'rate': rate.rate,
                             'rate_name': rate.name or _('Không có thuế'), 'deductible': ok and tax > 0,
                             'reason': reason if tax else _('Không có thuế GTGT'), 'source_model': p._name, 'source_id': p.id})
        return vals


class LfoodStockReport(models.TransientModel):
    _name = 'lfood.stock.report'
    _description = 'Báo cáo kho'

    report = fields.Selection([('balance', 'Tổng hợp nhập, xuất, tồn'), ('expiry', 'Hàng sắp hết hạn dùng')], 'Báo cáo',
                              required=True, default='balance')
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company)
    warehouse_id = fields.Many2one('lfood.warehouse', 'Kho')
    date_from = fields.Date('Từ ngày', required=True, default=lambda s: fields.Date.context_today(s).replace(day=1))
    date_to = fields.Date('Đến ngày', required=True, default=fields.Date.context_today)
    days = fields.Integer('Hết hạn trong vòng (ngày)', default=30)
    html = fields.Html('Nội dung', compute='_compute_html', sanitize=False)

    def _balance_rows(self):
        self.env['lfood.stock.valuation'].flush_model()
        wh = 'AND v.warehouse_id = %s' % int(self.warehouse_id.id) if self.warehouse_id else ''
        self.env.cr.execute("""
            SELECT p.code, p.name, p.uom,
                   SUM(CASE WHEN v.date < %(f)s THEN v.qty ELSE 0 END), SUM(CASE WHEN v.date < %(f)s THEN v.value ELSE 0 END),
                   SUM(CASE WHEN v.date >= %(f)s AND v.qty > 0 THEN v.qty ELSE 0 END), SUM(CASE WHEN v.date >= %(f)s AND v.qty > 0 THEN v.value ELSE 0 END),
                   SUM(CASE WHEN v.date >= %(f)s AND v.qty < 0 THEN -v.qty ELSE 0 END), SUM(CASE WHEN v.date >= %(f)s AND v.qty < 0 THEN -v.value ELSE 0 END)
            FROM lfood_stock_valuation v JOIN lfood_product p ON p.id = v.product_id
            WHERE v.company_id = %(c)s AND v.date <= %(t)s """ + wh + """
            GROUP BY p.code, p.name, p.uom ORDER BY p.code""", {'f': self.date_from, 't': self.date_to, 'c': self.company_id.id})
        return self.env.cr.fetchall()

    @api.depends('report', 'company_id', 'warehouse_id', 'date_from', 'date_to', 'days')
    def _compute_html(self):
        for rec in self:
            if not (rec.date_from and rec.date_to):
                rec.html = False
                continue
            if rec.report == 'balance':
                body, tot = Markup(''), [0, 0, 0, 0]
                for code, name, uom, oq, ov, iq, iv, xq, xv in rec._balance_rows():
                    cq, cv = oq + iq - xq, ov + iv - xv
                    tot = [tot[0] + ov, tot[1] + iv, tot[2] + xv, tot[3] + cv]
                    body += Markup('<tr><td>%s</td><td>%s</td><td>%s</td>%s</tr>') % (
                        code, escape(name), escape(uom), Markup('').join(Markup('<td style="text-align:right">%s</td>') % x for x in (
                            '%g' % oq, vnd(ov), '%g' % iq, vnd(iv), '%g' % xq, vnd(xv), '%g' % cq, vnd(cv))))
                rec.html = Markup('<div class="o_lfood_changes"><table><tr><th>Mã</th><th>Tên hàng</th><th>ĐVT</th><th>Tồn đầu SL</th><th>Tồn đầu giá trị</th>'
                                  '<th>Nhập SL</th><th>Nhập giá trị</th><th>Xuất SL</th><th>Xuất giá trị</th><th>Tồn cuối SL</th><th>Tồn cuối giá trị</th></tr>%s'
                                  '<tr><td></td><td><b>Cộng</b></td><td></td><td></td><td style="text-align:right"><b>%s</b></td><td></td>'
                                  '<td style="text-align:right"><b>%s</b></td><td></td><td style="text-align:right"><b>%s</b></td><td></td>'
                                  '<td style="text-align:right"><b>%s</b></td></tr></table></div>'
                                  '<p class="text-muted">Tồn cuối giá trị phải khớp số dư các tài khoản 152, 153, 155, 156 trên Bảng cân đối số phát sinh '
                                  '(trừ số dư nhập trực tiếp qua phiếu kế toán).</p>') % (body, vnd(tot[0]), vnd(tot[1]), vnd(tot[2]), vnd(tot[3]))
            else:
                limit = fields.Date.add(rec.date_to, days=rec.days)
                lots = self.env['lfood.stock.lot'].search([('expiry_date', '!=', False), ('expiry_date', '<=', limit),
                                                           ('product_id.company_id', 'in', [rec.company_id.id, False])])
                body = Markup('').join(
                    Markup('<tr><td>%s</td><td>%s</td><td>%s</td><td style="text-align:right">%g</td><td style="text-align:right">%s</td></tr>')
                    % (escape(l.product_id.display_name), escape(l.name), l.expiry_date.strftime('%d/%m/%Y'), l.qty_on_hand,
                       (l.expiry_date - rec.date_to).days)
                    for l in lots if l.qty_on_hand > 0)
                rec.html = Markup('<div class="o_lfood_changes"><table><tr><th>Mặt hàng</th><th>Lô</th><th>Hạn dùng</th><th>Còn tồn</th>'
                                  '<th>Số ngày còn lại (âm là đã hết hạn)</th></tr>%s</table></div>'
                                  '<p class="text-muted">Hàng đã hết hạn cần lập biên bản hủy và phiếu xuất Kiểm kê hoặc Xuất dùng nội bộ theo quyết định xử lý.</p>') % body
