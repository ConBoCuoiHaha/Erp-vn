"""Kiểm kê kho theo đợt (KHO07).

Một đợt kiểm kê: chốt số sổ sách theo từng mặt hàng, từng lô tại ngày kiểm kê; tổ kiểm kê nhập số đếm
thực tế; Kế toán trưởng duyệt thì app tự lập và ghi hai phiếu kho mục đích Kiểm kê:
- thừa: phiếu nhập theo giá bình quân hiện có, ghi Nợ TK kho / Có 3381 chờ xử lý;
- thiếu: phiếu xuất đúng lô, ghi Nợ 1381 chờ xử lý / Có TK kho.
Xử lý tiếp phần 1381, 3381 (bắt bồi thường, ghi chi phí, ghi thu nhập) theo quyết định của giám đốc,
kế toán lập bằng phiếu kế toán.
"""
from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd


class LfoodStockCount(models.Model):
    _name = 'lfood.stock.count'
    _description = 'Đợt kiểm kê kho'
    _order = 'date desc, id desc'

    name = fields.Char('Số đợt', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    warehouse_id = fields.Many2one('lfood.warehouse', 'Kho kiểm kê', required=True)
    date = fields.Date('Ngày kiểm kê', required=True, default=fields.Date.context_today, index=True)
    members = fields.Char('Thành phần tổ kiểm kê', required=True, help='Họ tên, chức vụ các thành viên')
    line_ids = fields.One2many('lfood.stock.count.line', 'count_id', 'Chi tiết')
    surplus_value = fields.Float('Giá trị thừa', digits=(16, 0), compute='_compute_totals', store=True)
    shortage_value = fields.Float('Giá trị thiếu', digits=(16, 0), compute='_compute_totals', store=True)
    conclusion = fields.Text('Ý kiến xử lý')
    state = fields.Selection([('draft', 'Đang đếm'), ('done', 'Đã duyệt, đã điều chỉnh'), ('cancel', 'Đã hủy')],
                             'Trạng thái', default='draft', required=True, readonly=True, copy=False, index=True)
    picking_ids = fields.One2many('lfood.stock.picking', 'count_id', 'Phiếu điều chỉnh', readonly=True)
    approved_by = fields.Many2one('res.users', 'Người duyệt', readonly=True, copy=False)
    report_html = fields.Html('Biên bản kiểm kê', compute='_compute_report', sanitize=False)

    @api.depends('line_ids.diff_value')
    def _compute_totals(self):
        for rec in self:
            rec.surplus_value = sum(v for v in rec.line_ids.mapped('diff_value') if v > 0)
            rec.shortage_value = -sum(v for v in rec.line_ids.mapped('diff_value') if v < 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.stock.count') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_stock_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái đợt kiểm kê chỉ đổi bằng nút Duyệt, Hủy.'))
            if self.filtered(lambda r: r.state != 'draft') and set(vals) - {'conclusion'}:
                raise UserError(_('Đợt kiểm kê đã duyệt không sửa được.'))
        return super().write(vals)

    def action_load(self):
        """Chốt số sổ sách theo mặt hàng và lô tại ngày kiểm kê; số thực tế mặc định bằng sổ sách."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Chỉ lấy số sổ sách khi đợt kiểm kê đang đếm.'))
        self.line_ids.unlink()
        Line = self.env['lfood.stock.count.line']
        Valuation = self.env['lfood.stock.valuation'].sudo()
        products = Valuation.search([('warehouse_id', '=', self.warehouse_id.id),
                                     ('date', '<=', self.date)]).mapped('product_id')
        for product in products.sorted('code'):
            # giá bình quân tính chung mọi kho, giống cách phiếu xuất tính giá vốn
            qty_total, value_all = product._position(upto=self.date)
            unit_cost = round(value_all / qty_total, 2) if qty_total else 0
            lots = Valuation.search([('product_id', '=', product.id), ('warehouse_id', '=', self.warehouse_id.id),
                                     ('date', '<=', self.date)]).mapped('lot_id')
            for lot in (lots if product.track_lot else [self.env['lfood.stock.lot']]):
                qty = self._book_qty(product, lot)
                if not qty:
                    continue
                Line.create({'count_id': self.id, 'product_id': product.id, 'lot_id': lot.id,
                             'book_qty': qty, 'real_qty': qty, 'unit_cost': unit_cost})
        return True

    def _book_qty(self, product, lot):
        self.env['lfood.stock.valuation'].flush_model()
        sql = ('SELECT COALESCE(SUM(qty), 0) FROM lfood_stock_valuation '
               'WHERE product_id = %s AND warehouse_id = %s AND date <= %s AND lot_id IS NOT DISTINCT FROM %s')
        self.env.cr.execute(sql, (product.id, self.warehouse_id.id, self.date, lot.id or None))
        return round(self.env.cr.fetchone()[0], 3)

    def action_approve(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được duyệt kết quả kiểm kê.'))
        Picking = self.env['lfood.stock.picking']
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.line_ids:
                raise UserError(_('Đợt kiểm kê chưa có dòng nào.'))
            surplus = rec.line_ids.filtered(lambda l: l.diff_qty > 0)
            shortage = rec.line_ids.filtered(lambda l: l.diff_qty < 0)
            memo = _('Điều chỉnh theo kiểm kê %s') % rec.name
            base = {'company_id': rec.company_id.id, 'purpose': 'count', 'date': rec.date,
                    'warehouse_id': rec.warehouse_id.id, 'count_id': rec.id, 'memo': memo}
            pickings = Picking
            if surplus:
                pickings |= Picking.create(dict(base, kind='in', line_ids=[
                    (0, 0, {'product_id': l.product_id.id, 'lot_id': l.lot_id.id, 'quantity': l.diff_qty,
                            'price_unit': l.unit_cost}) for l in surplus]))
            if shortage:
                pickings |= Picking.create(dict(base, kind='out', line_ids=[
                    (0, 0, {'product_id': l.product_id.id, 'lot_id': l.lot_id.id, 'quantity': -l.diff_qty})
                    for l in shortage]))
            pickings.action_done()
            rec.with_context(lfood_stock_system=True).write({'state': 'done', 'approved_by': self.env.uid})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Duyệt kiểm kê %s kho %s: thừa %s, thiếu %s') % (
                    rec.name, rec.warehouse_id.name, vnd(rec.surplus_value), vnd(rec.shortage_value)))
        return True

    def action_cancel(self):
        self.filtered(lambda r: r.state == 'draft').with_context(lfood_stock_system=True).write({'state': 'cancel'})
        return True

    @api.depends('line_ids.real_qty', 'members', 'conclusion', 'date', 'warehouse_id', 'state')
    def _compute_report(self):
        for rec in self:
            rows = Markup('').join(
                Markup('<tr><td>%s</td><td>%s</td><td>%s</td><td style="text-align:right">%s</td>'
                       '<td style="text-align:right">%s</td><td style="text-align:right">%s</td>'
                       '<td style="text-align:right">%s</td><td style="text-align:right">%s</td></tr>') % (
                    i, escape(l.product_id.display_name or ''), escape(l.lot_id.name or ''),
                    '%g' % l.book_qty, '%g' % l.real_qty, '%g' % l.diff_qty if l.diff_qty > 0 else '',
                    '%g' % -l.diff_qty if l.diff_qty < 0 else '', vnd(l.diff_value) if l.diff_value else '')
                for i, l in enumerate(rec.line_ids, start=1))
            rec.report_html = Markup(
                '<div class="o_lfood_changes"><h3 style="text-align:center">%s</h3>'
                '<p>%s</p><p>%s</p>'
                '<table><tr><th>STT</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th></tr>'
                '%s<tr style="font-weight:700"><td colspan="7" style="text-align:right">%s</td>'
                '<td style="text-align:right">%s</td></tr></table>'
                '<p>%s</p><table style="width:100%%;margin-top:16px"><tr>'
                '<td style="text-align:center">%s</td><td style="text-align:center">%s</td>'
                '<td style="text-align:center">%s</td></tr></table></div>') % (
                _('BIÊN BẢN KIỂM KÊ HÀNG TỒN KHO'),
                _('Kho: %s. Thời điểm kiểm kê: %s. Số: %s.') % (rec.warehouse_id.name or '',
                                                                rec.date.strftime('%d/%m/%Y') if rec.date else '',
                                                                rec.name),
                _('Tổ kiểm kê: %s') % (rec.members or ''),
                _('Mặt hàng'), _('Lô'), _('Sổ sách'), _('Thực tế'), _('Thừa'), _('Thiếu'), _('Giá trị chênh lệch'),
                rows, _('Thừa %s, thiếu %s') % (vnd(rec.surplus_value), vnd(rec.shortage_value)),
                vnd(rec.surplus_value - rec.shortage_value),
                _('Ý kiến xử lý: %s') % (rec.conclusion or ''),
                _('Thủ kho'), _('Kế toán trưởng'), _('Giám đốc'))


class LfoodStockCountLine(models.Model):
    _name = 'lfood.stock.count.line'
    _description = 'Dòng kiểm kê'
    _order = 'count_id, product_id, lot_id'

    count_id = fields.Many2one('lfood.stock.count', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='count_id.company_id', store=True)
    product_id = fields.Many2one('lfood.product', 'Mặt hàng', required=True)
    lot_id = fields.Many2one('lfood.stock.lot', 'Lô')
    uom = fields.Char(related='product_id.uom')
    book_qty = fields.Float('Số sổ sách', digits=(16, 3), readonly=True)
    real_qty = fields.Float('Số thực tế', digits=(16, 3))
    diff_qty = fields.Float('Chênh lệch', digits=(16, 3), compute='_compute_diff', store=True)
    unit_cost = fields.Float('Đơn giá bình quân', digits=(16, 2), readonly=True)
    diff_value = fields.Float('Giá trị chênh lệch', digits=(16, 0), compute='_compute_diff', store=True)
    note = fields.Char('Nguyên nhân')

    @api.depends('book_qty', 'real_qty', 'unit_cost')
    def _compute_diff(self):
        for rec in self:
            rec.diff_qty = round(rec.real_qty - rec.book_qty, 3)
            rec.diff_value = round(rec.diff_qty * rec.unit_cost)

    @api.constrains('real_qty')
    def _check_real(self):
        for rec in self:
            if rec.real_qty < 0:
                raise UserError(_('Số thực tế không được âm.'))

    def write(self, vals):
        if not self.env.context.get('lfood_stock_system') and self.filtered(lambda l: l.count_id.state != 'draft'):
            raise UserError(_('Đợt kiểm kê đã duyệt không sửa được.'))
        return super().write(vals)


class LfoodStockPicking(models.Model):
    _inherit = 'lfood.stock.picking'

    count_id = fields.Many2one('lfood.stock.count', 'Đợt kiểm kê', index=True, copy=False, readonly=True)
