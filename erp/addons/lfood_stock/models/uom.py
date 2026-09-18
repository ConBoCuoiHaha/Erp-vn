"""Đơn vị tính và quy đổi (DM03).

Mỗi mặt hàng có một đơn vị tính gốc (đơn vị ghi sổ kho, ví dụ hũ) và các đơn vị quy đổi (lốc = 6 hũ, thùng = 24 hũ).
Nhập chứng từ kho theo đơn vị lớn: chọn đơn vị quy đổi và số lượng, app tự tính số lượng theo đơn vị gốc; sổ kho, giá
vốn luôn theo đơn vị gốc để không sai giá bình quân.
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LfoodUomConversion(models.Model):
    _name = 'lfood.uom.conversion'
    _description = 'Đơn vị quy đổi của mặt hàng'
    _order = 'product_id, factor desc'

    product_id = fields.Many2one('lfood.product', 'Mặt hàng', required=True, ondelete='cascade', index=True)
    name = fields.Char('Đơn vị quy đổi', required=True, help='Ví dụ thùng, lốc, kiện')
    factor = fields.Float('Bằng bao nhiêu đơn vị gốc', digits=(16, 4), required=True,
                          help='Ví dụ 1 thùng = 24 hũ thì ghi 24')
    base_uom = fields.Char(related='product_id.uom', string='Đơn vị gốc')
    barcode = fields.Char('Mã vạch của đơn vị này', help='Mã vạch in trên thùng, lốc (nếu có)')

    _uniq = models.Constraint('unique(product_id, name)', 'Mặt hàng đã có đơn vị quy đổi này.')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s (= %g %s)' % (rec.name, rec.factor, rec.base_uom or '')

    @api.constrains('factor')
    def _check_factor(self):
        for rec in self:
            if rec.factor <= 0:
                raise ValidationError(_('Hệ số quy đổi phải lớn hơn 0.'))


class LfoodProduct(models.Model):
    _inherit = 'lfood.product'

    conversion_ids = fields.One2many('lfood.uom.conversion', 'product_id', 'Đơn vị quy đổi')

    def to_base_qty(self, qty, uom_name):
        """Đổi số lượng theo đơn vị uom_name sang đơn vị gốc của mặt hàng."""
        self.ensure_one()
        if not uom_name or uom_name == self.uom:
            return qty
        conv = self.conversion_ids.filtered(lambda c: c.name == uom_name)[:1]
        if not conv:
            raise ValidationError(_('%s không có đơn vị quy đổi "%s".') % (self.display_name, uom_name))
        return qty * conv.factor


class LfoodStockPickingLine(models.Model):
    _inherit = 'lfood.stock.picking.line'

    pack_uom_id = fields.Many2one('lfood.uom.conversion', 'Nhập theo đơn vị',
                                  domain="[('product_id', '=', product_id)]",
                                  help='Để trống là nhập theo đơn vị gốc của mặt hàng')
    pack_qty = fields.Float('Số lượng theo đơn vị đó', digits=(16, 3))

    @api.onchange('pack_uom_id', 'pack_qty')
    def _onchange_pack(self):
        if self.pack_uom_id and self.pack_qty:
            self.quantity = round(self.pack_qty * self.pack_uom_id.factor, 3)

    @api.constrains('pack_uom_id', 'product_id')
    def _check_pack(self):
        for rec in self:
            if rec.pack_uom_id and rec.pack_uom_id.product_id != rec.product_id:
                raise ValidationError(_('Đơn vị quy đổi không thuộc mặt hàng %s.') % rec.product_id.display_name)


class LfoodEcomSku(models.AbstractModel):
    """Tìm mặt hàng theo mã vạch đơn vị lớn khi quét mã (dùng ở phân hệ quét mã vạch)."""
    _name = 'lfood.uom.lookup'
    _description = 'Tra đơn vị quy đổi theo mã vạch'

    @api.model
    def by_barcode(self, code):
        conv = self.env['lfood.uom.conversion'].search([('barcode', '=', code)], limit=1)
        return (conv.product_id, conv.factor) if conv else (self.env['lfood.product'], 1)
