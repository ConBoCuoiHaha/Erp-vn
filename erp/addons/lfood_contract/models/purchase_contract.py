"""Hợp đồng mua khung (MH04): giá, sản lượng cam kết, thời hạn; đơn mua gắn hợp đồng lấy giá hợp đồng và bị chặn
khi giá cao hơn hoặc ngoài thời hạn. Quy chế nội bộ, không phải mẫu pháp lý.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd


class LfoodPurchaseContract(models.Model):
    _name = 'lfood.purchase.contract'
    _description = 'Hợp đồng mua khung'
    _order = 'date_from desc, id desc'

    name = fields.Char('Số', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    partner_id = fields.Many2one('res.partner', 'Nhà cung cấp', required=True, index=True)
    contract_ref = fields.Char('Số hợp đồng ký', required=True)
    date_from = fields.Date('Hiệu lực từ', required=True)
    date_to = fields.Date('Đến', required=True)
    line_ids = fields.One2many('lfood.purchase.contract.line', 'contract_id', 'Hàng hóa, giá', copy=True)
    order_ids = fields.One2many('lfood.purchase.order', 'contract_id', 'Đơn mua theo hợp đồng')
    document = fields.Binary('Bản hợp đồng', attachment=True)
    document_name = fields.Char()
    state = fields.Selection([('draft', 'Nháp'), ('active', 'Đang hiệu lực'), ('closed', 'Đã thanh lý')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('lfood.purchase.contract') or '/'
        return super().create(vals_list)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_to < rec.date_from:
                raise ValidationError(_('Ngày kết thúc phải sau ngày bắt đầu.'))

    def write(self, vals):
        if not self.env.context.get('lfood_contract_system') and self.filtered(lambda r: r.state != 'draft') \
                and set(vals) - {'document', 'document_name'}:
            raise UserError(_('Hợp đồng đã hiệu lực không sửa được; ký phụ lục thành hợp đồng mới.'))
        return super().write(vals)

    def action_activate(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.line_ids or not rec.document:
                raise UserError(_('Hợp đồng cần có hàng hóa, giá và bản hợp đồng đã ký.'))
            rec.with_context(lfood_contract_system=True).write({'state': 'active'})
        return True

    def action_close(self):
        self.filtered(lambda r: r.state == 'active').with_context(lfood_contract_system=True).write({'state': 'closed'})
        return True


class LfoodPurchaseContractLine(models.Model):
    _name = 'lfood.purchase.contract.line'
    _description = 'Hàng hóa trong hợp đồng mua khung'

    contract_id = fields.Many2one('lfood.purchase.contract', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('lfood.product', 'Mặt hàng', required=True)
    price = fields.Float('Đơn giá hợp đồng', digits=(16, 2), required=True)
    qty_committed = fields.Float('Sản lượng cam kết', digits=(16, 3))
    qty_ordered = fields.Float('Đã đặt', digits=(16, 3), compute='_compute_ordered')

    def _compute_ordered(self):
        for rec in self:
            lines = self.env['lfood.purchase.order.line'].sudo().search([
                ('order_id.contract_id', '=', rec.contract_id.id), ('product_id', '=', rec.product_id.id),
                ('order_id.state', 'in', ('confirmed', 'done'))])
            rec.qty_ordered = sum(lines.mapped('quantity'))


class LfoodPurchaseOrder(models.Model):
    _inherit = 'lfood.purchase.order'

    contract_id = fields.Many2one('lfood.purchase.contract', 'Theo hợp đồng khung', index=True,
                                  domain="[('partner_id', '=', partner_id), ('state', '=', 'active')]")

    def action_apply_contract(self):
        for rec in self.filtered('contract_id'):
            prices = {l.product_id: l.price for l in rec.contract_id.line_ids}
            for line in rec.line_ids.filtered(lambda l: l.product_id in prices):
                line.price_unit = prices[line.product_id]
        return True

    def action_confirm(self):
        for rec in self.filtered(lambda r: r.state in ('draft', 'waiting')):
            if rec.partner_id.lfood_supplier_status == 'rejected':
                raise UserError(_('Nhà cung cấp %s đã bị loại theo đánh giá; không đặt hàng.') % rec.partner_id.name)
            contract = rec.contract_id
            if not contract:
                continue
            if contract.state != 'active' or not contract.date_from <= rec.date <= contract.date_to:
                raise UserError(_('Ngày đặt nằm ngoài thời hạn hợp đồng %s.') % contract.contract_ref)
            prices = {l.product_id: l.price for l in contract.line_ids}
            for line in rec.line_ids:
                if line.product_id not in prices:
                    raise UserError(_('%s không có trong hợp đồng %s.') % (line.name, contract.contract_ref))
                if line.price_unit > prices[line.product_id] + 0.005:
                    raise UserError(_('%s: đơn giá %s cao hơn giá hợp đồng %s.') % (
                        line.name, vnd(line.price_unit), vnd(prices[line.product_id])))
        return super().action_confirm()
