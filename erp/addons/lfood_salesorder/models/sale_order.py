"""Bán hàng: kênh phân phối, bảng giá theo kênh, hạn mức tín dụng, báo giá và đơn bán (BH02, BH03, BH04, BH06).

Luồng: báo giá (nháp) -> xác nhận đơn; vượt hạn mức tín dụng thì chờ Kế toán trưởng hoặc Giám đốc duyệt ->
lập hóa đơn từ số lượng chưa lập -> kế toán ghi nhận số hóa đơn điện tử và ghi sổ; phân hệ kho tự xuất hàng
theo lô hết hạn trước, bỏ qua lô còn hạn ít hơn mức khách yêu cầu.
Hạn mức tín dụng và hạn dùng tối thiểu là quy chế công ty, không phải quy định pháp luật.
"""
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd


class LfoodSaleChannel(models.Model):
    _name = 'lfood.sale.channel'
    _description = 'Kênh phân phối'
    _order = 'code'

    code = fields.Char('Mã kênh', required=True)
    name = fields.Char('Tên kênh', required=True)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục chi phí bán hàng của kênh')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique(code)', 'Mã kênh đã tồn tại.')


class LfoodPricelist(models.Model):
    _name = 'lfood.pricelist'
    _description = 'Bảng giá bán'
    _order = 'date_from desc, id desc'

    name = fields.Char('Tên bảng giá', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    channel_id = fields.Many2one('lfood.sale.channel', 'Kênh áp dụng')
    date_from = fields.Date('Hiệu lực từ', required=True, default=fields.Date.context_today)
    date_to = fields.Date('Hiệu lực đến')
    line_ids = fields.One2many('lfood.pricelist.line', 'pricelist_id', 'Giá', copy=True)
    active = fields.Boolean(default=True)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_('Ngày hết hiệu lực phải sau ngày bắt đầu.'))

    def _price_for(self, product, quantity, at):
        """(đơn giá, chiết khấu %) của dòng giá có số lượng tối thiểu lớn nhất không vượt số lượng đặt."""
        self.ensure_one()
        if at < self.date_from or (self.date_to and at > self.date_to):
            return None
        lines = self.line_ids.filtered(lambda l: l.product_id == product and l.min_qty <= quantity)
        if not lines:
            return None
        best = lines.sorted('min_qty')[-1]
        return best.price, best.discount


class LfoodPricelistLine(models.Model):
    _name = 'lfood.pricelist.line'
    _description = 'Dòng bảng giá'
    _order = 'pricelist_id, product_id, min_qty'

    pricelist_id = fields.Many2one('lfood.pricelist', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('lfood.product', 'Mặt hàng', required=True)
    min_qty = fields.Float('Từ số lượng', digits=(16, 3), default=1)
    price = fields.Float('Đơn giá chưa thuế', digits=(16, 2), required=True)
    discount = fields.Float('Chiết khấu (%)', digits=(6, 2))

    @api.constrains('discount', 'price')
    def _check_values(self):
        for rec in self:
            if rec.price < 0 or not 0 <= rec.discount <= 100:
                raise ValidationError(_('Đơn giá không âm, chiết khấu từ 0 đến 100%.'))


class ResPartner(models.Model):
    _inherit = 'res.partner'

    lfood_channel_id = fields.Many2one('lfood.sale.channel', 'Kênh phân phối')
    lfood_pricelist_id = fields.Many2one('lfood.pricelist', 'Bảng giá mặc định')
    lfood_credit_limit = fields.Float('Hạn mức công nợ', digits=(16, 0),
                                      help='Để 0 là không kiểm soát hạn mức')
    lfood_payment_days = fields.Integer('Số ngày được nợ')
    lfood_min_shelf_days = fields.Integer('Hạn dùng còn lại tối thiểu khi giao (ngày)',
                                          help='Không giao lô còn hạn ít hơn số ngày này')


class LfoodSaleOrder(models.Model):
    _name = 'lfood.sale.order'
    _description = 'Báo giá, đơn bán hàng'
    _order = 'date desc, id desc'

    name = fields.Char('Số đơn', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    partner_id = fields.Many2one('res.partner', 'Khách hàng', required=True, index=True)
    channel_id = fields.Many2one('lfood.sale.channel', 'Kênh', compute='_compute_partner_defaults', store=True,
                                 readonly=False)
    pricelist_id = fields.Many2one('lfood.pricelist', 'Bảng giá', compute='_compute_partner_defaults', store=True,
                                   readonly=False)
    user_id = fields.Many2one('res.users', 'Nhân viên bán hàng', default=lambda s: s.env.user)
    date = fields.Date('Ngày đặt', required=True, default=fields.Date.context_today, index=True)
    date_delivery = fields.Date('Ngày giao dự kiến')
    warehouse_id = fields.Many2one('lfood.warehouse', 'Xuất từ kho')
    memo = fields.Char('Diễn giải')
    line_ids = fields.One2many('lfood.sale.order.line', 'order_id', 'Hàng hóa', copy=True)
    amount_untaxed = fields.Float('Tiền hàng', digits=(16, 0), compute='_compute_amounts', store=True)
    amount_tax = fields.Float('Thuế GTGT', digits=(16, 0), compute='_compute_amounts', store=True)
    amount_total = fields.Float('Tổng thanh toán', digits=(16, 0), compute='_compute_amounts', store=True)
    credit_note = fields.Char('Kiểm tra hạn mức', readonly=True, copy=False)
    state = fields.Selection([('draft', 'Báo giá'), ('waiting', 'Chờ duyệt tín dụng'), ('confirmed', 'Đã xác nhận'),
                              ('done', 'Đã lập đủ hóa đơn'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)
    approved_by = fields.Many2one('res.users', 'Người duyệt tín dụng', readonly=True, copy=False)
    invoice_ids = fields.One2many('lfood.sale.invoice', 'sale_order_id', 'Hóa đơn')
    invoice_count = fields.Integer('Số hóa đơn', compute='_compute_invoice_count')

    @api.depends('partner_id')
    def _compute_partner_defaults(self):
        for rec in self:
            rec.channel_id = rec.partner_id.lfood_channel_id
            rec.pricelist_id = rec.partner_id.lfood_pricelist_id

    @api.depends('line_ids.amount', 'line_ids.tax')
    def _compute_amounts(self):
        for rec in self:
            rec.amount_untaxed = sum(rec.line_ids.mapped('amount'))
            rec.amount_tax = sum(rec.line_ids.mapped('tax'))
            rec.amount_total = rec.amount_untaxed + rec.amount_tax

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.sale.order') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_sale_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái đơn bán chỉ đổi bằng các nút trên màn hình.'))
            if self.filtered(lambda r: r.state != 'draft') and set(vals) - {'memo', 'date_delivery'}:
                raise UserError(_('Đơn đã xác nhận không sửa được. Hủy đơn rồi lập đơn mới.'))
        return super().write(vals)

    def action_apply_prices(self):
        """Lấy đơn giá, chiết khấu theo bảng giá cho mọi dòng."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ áp giá cho báo giá.'))
            for line in rec.line_ids:
                line._apply_pricelist()
        return True

    def _exposure(self):
        """Công nợ phải thu hiện tại cộng đơn đã xác nhận chưa lập hóa đơn của khách."""
        self.ensure_one()
        lines = self.env['lfood.move.line'].sudo().search([
            ('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
            ('partner_id', '=', self.partner_id.id), ('account_code', '=like', '131%')])
        receivable = sum(lines.mapped('balance'))
        open_orders = self.sudo().search([('partner_id', '=', self.partner_id.id), ('id', '!=', self.id),
                                          ('company_id', '=', self.company_id.id),
                                          ('state', 'in', ('waiting', 'confirmed'))])
        pending = sum(l.amount_total_uninvoiced for o in open_orders for l in o.line_ids)
        return receivable, pending

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ xác nhận báo giá.'))
            if not rec.line_ids:
                raise UserError(_('Đơn chưa có hàng hóa.'))
            limit = rec.partner_id.lfood_credit_limit
            state, note = 'confirmed', ''
            if limit:
                receivable, pending = rec._exposure()
                total = receivable + pending + rec.amount_total
                note = _('Công nợ %s + đơn đang mở %s + đơn này %s = %s, hạn mức %s') % (
                    vnd(receivable), vnd(pending), vnd(rec.amount_total), vnd(total), vnd(limit))
                if total > limit:
                    state = 'waiting'
            rec.with_context(lfood_sale_system=True).write({'state': state, 'credit_note': note})
            if state == 'waiting':
                self.env['lfood.audit.log']._record_event(
                    'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                    summary=_('Đơn %s vượt hạn mức tín dụng, chờ duyệt: %s') % (rec.name, note))
        return True

    def action_approve_credit(self):
        if not (self.env.user.has_group('lfood_base.group_chief_accountant')
                or self.env.user.has_group('lfood_base.group_director')):
            raise UserError(_('Chỉ Kế toán trưởng hoặc Giám đốc được duyệt vượt hạn mức tín dụng.'))
        for rec in self.filtered(lambda r: r.state == 'waiting'):
            rec.with_context(lfood_sale_system=True).write({'state': 'confirmed', 'approved_by': self.env.uid})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Duyệt đơn %s vượt hạn mức tín dụng: %s') % (rec.name, rec.credit_note))
        return True

    def action_cancel(self):
        for rec in self:
            if rec.invoice_ids.filtered(lambda i: i.state == 'posted'):
                raise UserError(_('Đơn %s đã có hóa đơn ghi sổ, không hủy được.') % rec.name)
            rec.with_context(lfood_sale_system=True).write({'state': 'cancel'})
        return True

    def action_create_invoice(self):
        """Lập hóa đơn nháp cho phần chưa lập hóa đơn; kế toán nhập ký hiệu, số hóa đơn điện tử rồi ghi sổ."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_('Chỉ lập hóa đơn cho đơn đã xác nhận.'))
        lines = self.line_ids.filtered(lambda l: l.qty_to_invoice > 0)
        if not lines:
            raise UserError(_('Đơn đã lập đủ hóa đơn.'))
        if self.invoice_ids.filtered(lambda i: i.state == 'draft'):
            raise UserError(_('Đơn đang có hóa đơn nháp, ghi sổ hoặc xóa hóa đơn đó trước.'))
        days = self.partner_id.lfood_payment_days
        today = fields.Date.context_today(self)
        invoice = self.env['lfood.sale.invoice'].create({
            'company_id': self.company_id.id, 'partner_id': self.partner_id.id, 'sale_order_id': self.id,
            'warehouse_id': self.warehouse_id.id, 'date': today, 'invoice_date': today,
            'due_date': today + timedelta(days=days) if days else False,
            'memo': _('Theo đơn bán %s') % self.name,
            'line_ids': [(0, 0, {
                'name': l.product_id.name + (_(' (chiết khấu %s%%)') % ('%g' % l.discount) if l.discount else ''),
                'product_id': l.product_id.id, 'uom': l.product_id.uom, 'quantity': l.qty_to_invoice,
                'price_unit': l.net_price, 'vat_rate_id': l.vat_rate_id.id, 'sale_order_line_id': l.id,
            }) for l in lines],
        })
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.sale.invoice', 'res_id': invoice.id,
                'view_mode': 'form'}

    def action_view_invoices(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Hóa đơn'), 'res_model': 'lfood.sale.invoice',
                'view_mode': 'list,form', 'domain': [('sale_order_id', '=', self.id)]}

    def _update_done(self):
        for rec in self.filtered(lambda r: r.state == 'confirmed'):
            if all(l.qty_to_invoice <= 0 for l in rec.line_ids):
                rec.with_context(lfood_sale_system=True).write({'state': 'done'})


class LfoodSaleOrderLine(models.Model):
    _name = 'lfood.sale.order.line'
    _description = 'Dòng đơn bán'

    order_id = fields.Many2one('lfood.sale.order', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    product_id = fields.Many2one('lfood.product', 'Mặt hàng', required=True)
    quantity = fields.Float('Số lượng', digits=(16, 3), required=True, default=1)
    price_unit = fields.Float('Đơn giá', digits=(16, 2))
    discount = fields.Float('Chiết khấu (%)', digits=(6, 2))
    net_price = fields.Float('Đơn giá sau chiết khấu', digits=(16, 2), compute='_compute_amount', store=True)
    amount = fields.Float('Thành tiền', digits=(16, 0), compute='_compute_amount', store=True)
    vat_rate_id = fields.Many2one('lfood.vat.rate', 'Thuế suất', required=True)
    tax = fields.Float('Tiền thuế', digits=(16, 0), compute='_compute_amount', store=True)
    qty_invoiced = fields.Float('Đã lập hóa đơn', digits=(16, 3), compute='_compute_invoiced', store=True)
    qty_to_invoice = fields.Float('Còn phải lập', digits=(16, 3), compute='_compute_invoiced', store=True)
    amount_total_uninvoiced = fields.Float('Giá trị chưa lập hóa đơn', digits=(16, 0),
                                           compute='_compute_invoiced', store=True)
    invoice_line_ids = fields.One2many('lfood.sale.invoice.line', 'sale_order_line_id', 'Dòng hóa đơn')

    @api.depends('quantity', 'price_unit', 'discount', 'vat_rate_id')
    def _compute_amount(self):
        for rec in self:
            rec.net_price = round(rec.price_unit * (1 - (rec.discount or 0) / 100), 2)
            rec.amount = round(rec.quantity * rec.net_price)
            rec.tax = round(rec.amount * (rec.vat_rate_id.rate or 0) / 100)

    @api.depends('quantity', 'amount', 'tax', 'invoice_line_ids.quantity', 'invoice_line_ids.invoice_id.state')
    def _compute_invoiced(self):
        for rec in self:
            done = rec.invoice_line_ids.filtered(lambda l: l.invoice_id.state == 'posted'
                                                 and l.invoice_id.kind == 'invoice')
            rec.qty_invoiced = sum(done.mapped('quantity'))
            rec.qty_to_invoice = max(0.0, rec.quantity - rec.qty_invoiced)
            share = rec.qty_to_invoice / rec.quantity if rec.quantity else 0
            rec.amount_total_uninvoiced = round((rec.amount + rec.tax) * share)

    @api.onchange('product_id')
    def _onchange_product(self):
        if self.product_id:
            self.vat_rate_id = self.product_id.vat_rate_id or self.vat_rate_id
            self._apply_pricelist()

    def _apply_pricelist(self):
        for rec in self:
            pricelist = rec.order_id.pricelist_id
            found = pricelist and pricelist._price_for(rec.product_id, rec.quantity, rec.order_id.date)
            if found:
                rec.price_unit, rec.discount = found

    @api.constrains('quantity', 'discount')
    def _check_values(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError(_('Số lượng phải lớn hơn 0.'))
            if not 0 <= rec.discount <= 100:
                raise ValidationError(_('Chiết khấu từ 0 đến 100%.'))

    def write(self, vals):
        if not self.env.context.get('lfood_sale_system') and self.filtered(lambda l: l.order_id.state != 'draft'):
            raise UserError(_('Đơn đã xác nhận không sửa được.'))
        return super().write(vals)


class LfoodSaleInvoice(models.Model):
    _inherit = 'lfood.sale.invoice'

    sale_order_id = fields.Many2one('lfood.sale.order', 'Đơn bán', index=True, readonly=True, copy=False)

    def action_post(self):
        for inv in self.filtered(lambda i: i.sale_order_id and i.state == 'draft' and i.kind == 'invoice'):
            for line in inv.line_ids.filtered('sale_order_line_id'):
                if line.quantity > line.sale_order_line_id.qty_to_invoice + 1e-6:
                    raise UserError(_('Mặt hàng %s: đơn %s chỉ còn %s chưa lập hóa đơn.')
                                    % (line.name, inv.sale_order_id.name, line.sale_order_line_id.qty_to_invoice))
        res = super().action_post()
        self.env.flush_all()
        self.mapped('sale_order_id').line_ids.invalidate_recordset()
        self.mapped('sale_order_id')._update_done()
        return res


class LfoodSaleInvoiceLine(models.Model):
    _inherit = 'lfood.sale.invoice.line'

    sale_order_line_id = fields.Many2one('lfood.sale.order.line', 'Dòng đơn bán', index=True, readonly=True)


class LfoodStockPicking(models.Model):
    _inherit = 'lfood.stock.picking'

    def _fefo_lot_domain(self, line):
        """Bỏ qua lô còn hạn ít hơn số ngày khách yêu cầu khi xuất bán."""
        domain = super()._fefo_lot_domain(line)
        days = self.partner_id.lfood_min_shelf_days if self.purpose == 'sale' else 0
        if days:
            domain += ['|', ('expiry_date', '=', False), ('expiry_date', '>=', self.date + timedelta(days=days))]
        return domain
