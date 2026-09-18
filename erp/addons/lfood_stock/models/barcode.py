"""Quét mã vạch và in tem lô (KHO11).

Máy quét mã vạch cắm USB gõ mã như bàn phím: đặt con trỏ vào ô "Quét mã" trên phiếu nhập, xuất hoặc đợt kiểm kê rồi
quét. Mã là mã vạch của mặt hàng (hoặc mã hàng), hoặc mã trên tem lô dạng "MÃ HÀNG/SỐ LÔ". Mỗi lần quét cộng 1 đơn vị
vào dòng cùng mặt hàng, cùng lô; chưa có dòng thì thêm dòng. Tem lô in mã vạch Code128 kèm tên hàng, số lô, hạn dùng.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

SEP = '/'


class LfoodProduct(models.Model):
    _inherit = 'lfood.product'

    barcode = fields.Char('Mã vạch', copy=False, index=True, help='Mã EAN, UPC in trên bao bì')

    _barcode_uniq = models.Constraint('unique(barcode)', 'Mã vạch đã gán cho mặt hàng khác.')


class LfoodStockLot(models.Model):
    _inherit = 'lfood.stock.lot'

    label_code = fields.Char('Mã trên tem lô', compute='_compute_label_code')

    def _compute_label_code(self):
        for rec in self:
            rec.label_code = '%s%s%s' % (rec.product_id.code, SEP, rec.name)


def lookup(env, code):
    """(mặt hàng, lô, số đơn vị gốc mỗi lần quét) theo mã quét; báo lỗi nếu không nhận ra.

    Mã vạch của đơn vị lớn (thùng, lốc) trả về hệ số quy đổi, nên quét một thùng cộng đủ số đơn vị gốc."""
    code = (code or '').strip()
    Product = env['lfood.product']
    lot = env['lfood.stock.lot']
    part, _sep, lot_name = code.partition(SEP)
    product = Product.search([('barcode', '=', part)], limit=1) or Product.search([('code', '=', part)], limit=1)
    factor = 1
    if not product:
        product, factor = env['lfood.uom.lookup'].by_barcode(part)
    if not product:
        raise UserError(_('Không tìm thấy mặt hàng có mã "%s".') % part)
    if lot_name:
        lot = lot.search([('product_id', '=', product.id), ('name', '=', lot_name)], limit=1)
        if not lot:
            raise UserError(_('Mặt hàng %s không có lô %s.') % (product.display_name, lot_name))
    return product, lot, factor


class ScanMixin(models.AbstractModel):
    _name = 'lfood.scan.mixin'
    _description = 'Quét mã vạch vào chứng từ kho'

    scan_code = fields.Char('Quét mã', store=False, help='Đặt con trỏ vào đây rồi quét mã vạch mặt hàng hoặc tem lô')

    def _scan_add(self, product, lot, qty=1):
        raise NotImplementedError

    @api.onchange('scan_code')
    def _onchange_scan_code(self):
        if self.scan_code:
            code, self.scan_code = self.scan_code, False
            self.scan(code)

    def scan(self, code):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ quét vào chứng từ đang ở trạng thái Nháp.'))
            rec._scan_add(*lookup(self.env, code))
        return True


class LfoodStockPicking(models.Model):
    _name = 'lfood.stock.picking'
    _inherit = ['lfood.stock.picking', 'lfood.scan.mixin']

    def _scan_add(self, product, lot, qty=1):
        line = self.line_ids.filtered(lambda l: l.product_id == product and l.lot_id == lot and not l.lot_name)[:1]
        if line:
            line.quantity += qty
        else:
            self.update({'line_ids': [(0, 0, {'product_id': product.id, 'lot_id': lot.id, 'quantity': qty,
                                              'vat_rate_id': product.vat_rate_id.id})]})


class LfoodStockCount(models.Model):
    _name = 'lfood.stock.count'
    _inherit = ['lfood.stock.count', 'lfood.scan.mixin']

    def action_scan_mode(self):
        """Đếm bằng máy quét: đưa số thực tế về 0 rồi mỗi lần quét cộng 1."""
        for rec in self.filtered(lambda r: r.state == 'draft'):
            rec.line_ids.write({'real_qty': 0})
        return True

    def _scan_add(self, product, lot, qty=1):
        line = self.line_ids.filtered(lambda l: l.product_id == product and l.lot_id == lot)[:1]
        if line:
            line.real_qty += qty
            return
        qty_total, value_all = product._position(upto=self.date)
        self.update({'line_ids': [(0, 0, {
            'product_id': product.id, 'lot_id': lot.id, 'real_qty': qty, 'book_qty': self._book_qty(product, lot),
            'unit_cost': round(value_all / qty_total, 2) if qty_total else 0})]})
