"""Chuyển hàng giữa hai pháp nhân (KHO04).

Văn phòng và Nhà máy có mã số thuế riêng nên hàng chuyển giữa hai bên là mua bán: bên xuất lập hóa đơn GTGT
(Nghị định 254/2026/NĐ-CP), ghi doanh thu, giá vốn; bên nhận ghi nhập kho mua hàng,
thuế GTGT đầu vào, phải trả. Phiếu xuất kho kiêm vận chuyển nội bộ chỉ dùng khi chuyển trong cùng một pháp nhân.
Hai bên là bên có quan hệ liên kết nên giá chuyển phải theo giá thị trường và kê khai giao dịch liên kết
(Nghị định 255/2026/NĐ-CP) khi quyết toán thuế TNDN. Lô, hạn dùng giữ nguyên từ bên xuất sang bên nhận.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd


class LfoodIntercompanyTransfer(models.Model):
    _name = 'lfood.intercompany.transfer'
    _description = 'Bán hàng giữa hai pháp nhân'
    _order = 'date desc, id desc'

    name = fields.Char('Số chứng từ', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Bên bán', required=True, default=lambda s: s.env.company, index=True)
    dest_company_id = fields.Many2one('res.company', 'Bên mua', required=True, index=True,
                                      domain="[('id', '!=', company_id)]")
    date = fields.Date('Ngày', required=True, default=fields.Date.context_today, index=True)
    warehouse_id = fields.Many2one('lfood.warehouse', 'Xuất từ kho', required=True,
                                   domain="[('company_id', '=', company_id)]")
    dest_warehouse_id = fields.Many2one('lfood.warehouse', 'Nhập vào kho', required=True,
                                        domain="[('company_id', '=', dest_company_id)]")
    invoice_template = fields.Char('Ký hiệu mẫu số', default='1')
    invoice_symbol = fields.Char('Ký hiệu hóa đơn')
    invoice_number = fields.Char('Số hóa đơn')
    price_basis = fields.Char('Căn cứ giá chuyển', help='Ví dụ: giá bán cho nhà phân phối độc lập cùng thời điểm')
    memo = fields.Char('Diễn giải')
    line_ids = fields.One2many('lfood.intercompany.transfer.line', 'transfer_id', 'Hàng hóa', copy=True)
    amount_untaxed = fields.Float('Tiền hàng', digits=(16, 0), compute='_compute_amounts', store=True)
    amount_tax = fields.Float('Thuế GTGT', digits=(16, 0), compute='_compute_amounts', store=True)
    below_cost = fields.Char('Cảnh báo giá', compute='_compute_below_cost')
    sale_invoice_id = fields.Many2one('lfood.sale.invoice', 'Hóa đơn bên bán', readonly=True, copy=False)
    in_picking_id = fields.Many2one('lfood.stock.picking', 'Phiếu nhập bên mua', readonly=True, copy=False)
    state = fields.Selection([('draft', 'Nháp'), ('done', 'Đã ghi sổ hai bên')], 'Trạng thái', default='draft',
                             required=True, readonly=True, copy=False, index=True)

    @api.depends('line_ids.amount', 'line_ids.tax')
    def _compute_amounts(self):
        for rec in self:
            rec.amount_untaxed = sum(rec.line_ids.mapped('amount'))
            rec.amount_tax = sum(rec.line_ids.mapped('tax'))

    @api.depends('line_ids.price_unit', 'line_ids.product_id', 'warehouse_id')
    def _compute_below_cost(self):
        for rec in self:
            low = []
            for l in rec.line_ids.filtered('product_id'):
                qty, value = l.product_id._position(rec.warehouse_id) if rec.warehouse_id else (0, 0)
                if qty > 0 and l.price_unit < value / qty:
                    low.append(l.product_id.display_name)
            rec.below_cost = _('Giá chuyển thấp hơn giá vốn: %s. Kiểm tra căn cứ giá giao dịch liên kết.') % ', '.join(low) \
                if low else False

    @api.constrains('company_id', 'dest_company_id', 'warehouse_id', 'dest_warehouse_id')
    def _check_companies(self):
        for rec in self:
            if rec.company_id == rec.dest_company_id:
                raise ValidationError(_('Bên bán và bên mua phải là hai pháp nhân khác nhau. '
                                        'Chuyển trong cùng pháp nhân dùng phiếu chuyển kho.'))
            if rec.warehouse_id.company_id != rec.company_id or rec.dest_warehouse_id.company_id != rec.dest_company_id:
                raise ValidationError(_('Kho xuất phải thuộc bên bán, kho nhập phải thuộc bên mua.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.intercompany.transfer') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_ic_system') and self.filtered(lambda r: r.state != 'draft'):
            raise UserError(_('Chứng từ đã ghi sổ không sửa được. Điều chỉnh bằng hóa đơn điều chỉnh và phiếu trả hàng.'))
        return super().write(vals)

    def action_post(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.line_ids:
                raise UserError(_('Chưa có hàng hóa.'))
            if not (rec.invoice_symbol and rec.invoice_number):
                raise UserError(_('Nhập ký hiệu và số hóa đơn bên bán đã phát hành trên hệ thống hóa đơn điện tử.'))
            if not rec.price_basis:
                raise UserError(_('Ghi căn cứ giá chuyển (giao dịch giữa các bên có quan hệ liên kết).'))
            seller, buyer = rec.company_id, rec.dest_company_id
            label = _('Bán cho %s theo %s') % (buyer.name, rec.name)
            invoice = self.env['lfood.sale.invoice'].with_company(seller).create({
                'company_id': seller.id, 'partner_id': buyer.partner_id.id, 'date': rec.date, 'invoice_date': rec.date,
                'invoice_template': rec.invoice_template, 'invoice_symbol': rec.invoice_symbol,
                'invoice_number': rec.invoice_number, 'warehouse_id': rec.warehouse_id.id, 'memo': label,
                'line_ids': [(0, 0, {'product_id': l.product_id.id, 'name': l.product_id.name, 'uom': l.product_id.uom,
                                     'quantity': l.quantity, 'price_unit': l.price_unit, 'vat_rate_id': l.vat_rate_id.id})
                             for l in rec.line_ids]})
            invoice.action_post()
            out = invoice.picking_ids.filtered(lambda p: p.kind == 'out')
            valuations = self.env['lfood.stock.valuation'].sudo().search([('picking_id', 'in', out.ids), ('qty', '<', 0)])
            price = {l.product_id: l for l in rec.line_ids}
            in_lines = []
            for v in valuations:
                src = price[v.product_id]
                in_lines.append((0, 0, {'product_id': v.product_id.id, 'lot_id': v.lot_id.id, 'quantity': -v.qty,
                                        'price_unit': src.price_unit, 'vat_rate_id': src.vat_rate_id.id}))
            picking = self.env['lfood.stock.picking'].with_company(buyer).create({
                'company_id': buyer.id, 'kind': 'in', 'purpose': 'purchase', 'date': rec.date,
                'warehouse_id': rec.dest_warehouse_id.id, 'partner_id': seller.partner_id.id,
                'invoice_symbol': rec.invoice_symbol, 'invoice_number': rec.invoice_number, 'invoice_date': rec.date,
                'memo': _('Mua của %s theo %s') % (seller.name, rec.name), 'line_ids': in_lines})
            picking.action_done()
            rec.with_context(lfood_ic_system=True).write(
                {'state': 'done', 'sale_invoice_id': invoice.id, 'in_picking_id': picking.id})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=seller.id,
                summary=_('%s bán cho %s: tiền hàng %s, thuế %s%s') % (
                    seller.name, buyer.name, vnd(rec.amount_untaxed), vnd(rec.amount_tax),
                    ('. ' + rec.below_cost) if rec.below_cost else ''))
        return True


class LfoodIntercompanyTransferLine(models.Model):
    _name = 'lfood.intercompany.transfer.line'
    _description = 'Dòng bán hàng giữa hai pháp nhân'

    transfer_id = fields.Many2one('lfood.intercompany.transfer', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='transfer_id.company_id', store=True)
    product_id = fields.Many2one('lfood.product', 'Mặt hàng', required=True, domain="[('company_id', '=', False)]")
    uom = fields.Char(related='product_id.uom')
    quantity = fields.Float('Số lượng', digits=(16, 3), required=True, default=1)
    price_unit = fields.Float('Giá chuyển chưa thuế', digits=(16, 2), required=True)
    vat_rate_id = fields.Many2one('lfood.vat.rate', 'Thuế suất', required=True)
    amount = fields.Float('Thành tiền', digits=(16, 0), compute='_compute_amount', store=True)
    tax = fields.Float('Tiền thuế', digits=(16, 0), compute='_compute_amount', store=True)

    _product_uniq = models.Constraint('unique(transfer_id, product_id)', 'Mỗi mặt hàng nhập một dòng.')

    @api.depends('quantity', 'price_unit', 'vat_rate_id')
    def _compute_amount(self):
        for rec in self:
            rec.amount = round(rec.quantity * rec.price_unit)
            rec.tax = round(rec.amount * (rec.vat_rate_id.rate or 0) / 100)

    @api.onchange('product_id')
    def _onchange_product(self):
        if self.product_id.vat_rate_id:
            self.vat_rate_id = self.product_id.vat_rate_id

    @api.constrains('product_id', 'quantity', 'price_unit')
    def _check_line(self):
        for rec in self:
            if rec.product_id.company_id:
                raise ValidationError(_('%s chỉ dùng cho một pháp nhân. Hàng chuyển giữa hai pháp nhân phải là danh mục dùng chung.')
                                      % rec.product_id.display_name)
            if rec.quantity <= 0 or rec.price_unit <= 0:
                raise ValidationError(_('Số lượng và giá chuyển phải lớn hơn 0.'))

    def write(self, vals):
        if self.filtered(lambda l: l.transfer_id.state != 'draft'):
            raise UserError(_('Chứng từ đã ghi sổ không sửa được.'))
        return super().write(vals)
