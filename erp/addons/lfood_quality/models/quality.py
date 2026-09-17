"""Truy xuất nguồn gốc lô (CL05) và thu hồi sản phẩm (CL06).

Căn cứ: Luật An toàn thực phẩm 55/2010/QH12, Điều 54, 55; Nghị định 46/2026/NĐ-CP, Điều 42, 43 (hiệu lực 26/01/2026):
cơ sở phải lưu đủ thông tin về sản phẩm (tên, nhãn hiệu, số lô, thời hạn sử dụng, thời gian và địa điểm sản xuất),
cơ sở cung cấp, phân phối và khách hàng để truy xuất khi sản phẩm không bảo đảm an toàn hoặc khi cơ quan có thẩm quyền
yêu cầu. Thu hồi theo hình thức tự nguyện hoặc bắt buộc; xử lý bằng khắc phục lỗi, chuyển mục đích, tái xuất, tiêu hủy.
Số liệu truy xuất lấy từ thẻ kho theo lô nên gồm cả nhập mua, nhập thành phẩm, chuyển kho, xuất bán, xuất khuyến mại,
xuất hủy, bán giữa hai pháp nhân.
"""
from markupsafe import escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd

UPSTREAM = ('purchase', 'factory', 'opening')
DOWNSTREAM = ('sale', 'promotion')


def _d(value):
    return value.strftime('%d/%m/%Y') if value else ''


class LfoodStockLot(models.Model):
    _inherit = 'lfood.stock.lot'

    def _trace_moves(self):
        """Thẻ kho của lô, mọi công ty, theo ngày."""
        self.ensure_one()
        return self.env['lfood.stock.valuation'].sudo().search([('lot_id', '=', self.id)], order='date, id')

    def _shipments(self):
        """{khách hàng: số lượng đã giao} của lô, trừ số khách đã trả lại."""
        out = {}
        for v in self._trace_moves().filtered(lambda v: v.picking_id.partner_id):
            p = v.picking_id
            if p.purpose in DOWNSTREAM and v.qty < 0:
                out[p.partner_id] = out.get(p.partner_id, 0) - v.qty
            elif p.purpose == 'return_in' and v.qty > 0:
                out[p.partner_id] = out.get(p.partner_id, 0) - v.qty
        return out

    def action_trace(self):
        self.ensure_one()
        wiz = self.env['lfood.trace'].create({'lot_id': self.id})
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.trace', 'res_id': wiz.id, 'view_mode': 'form'}


class LfoodTrace(models.TransientModel):
    _name = 'lfood.trace'
    _description = 'Truy xuất nguồn gốc lô'

    lot_id = fields.Many2one('lfood.stock.lot', 'Lô hàng', required=True)
    html = fields.Html('Kết quả truy xuất', compute='_compute_html', sanitize=False)

    @api.depends('lot_id')
    def _compute_html(self):
        for rec in self:
            lot = rec.lot_id
            if not lot:
                rec.html = False
                continue
            product = lot.product_id
            moves = lot._trace_moves()
            rows_up, rows_down, rows_other = [], [], []
            for v in moves:
                p = v.picking_id
                row = '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td class="text-end">%s</td></tr>' % (
                    _d(v.date), escape(p.name or ''), escape(v.company_id.name or ''), escape(v.warehouse_id.name or ''),
                    escape(dict(p._fields['purpose'].selection).get(p.purpose, '')),
                    escape(' '.join(filter(None, [p.partner_id.name, p.partner_id.vat and '(MST %s)' % p.partner_id.vat,
                                                  p.invoice_number and 'HĐ %s' % p.invoice_number]))),
                    '%g' % v.qty)
                if p.purpose in UPSTREAM and v.qty > 0:
                    rows_up.append(row)
                elif p.purpose in DOWNSTREAM:
                    rows_down.append(row)
                else:
                    rows_other.append(row)
            stock = {}
            for v in moves:
                stock[v.warehouse_id] = stock.get(v.warehouse_id, 0) + v.qty
            rows_stock = ''.join('<tr><td>%s</td><td>%s</td><td class="text-end">%s</td></tr>' % (
                escape(wh.company_id.name or ''), escape(wh.name), '%g' % q) for wh, q in stock.items() if round(q, 3))
            head = ('<thead><tr><th>Ngày</th><th>Phiếu</th><th>Pháp nhân</th><th>Kho</th><th>Nội dung</th>'
                    '<th>Đối tượng, hóa đơn</th><th>Số lượng</th></tr></thead>')
            table = lambda rows: '<table class="table table-sm">%s<tbody>%s</tbody></table>' % (
                head, ''.join(rows) or '<tr><td colspan="7">Không có</td></tr>')
            rec.html = (
                '<h3>TRUY XUẤT NGUỒN GỐC LÔ %s</h3>'
                '<p>Sản phẩm: <b>%s</b>, đơn vị tính %s. Ngày sản xuất: %s. Hạn sử dụng: %s. Hạn dùng chuẩn: %s ngày. %s</p>'
                '<h4>1. Nguồn cung cấp (một bước trước)</h4>%s'
                '<h4>2. Khách hàng, nơi phân phối (một bước sau)</h4>%s'
                '<h4>3. Luân chuyển nội bộ, trả lại, kiểm kê, hủy</h4>%s'
                '<h4>4. Tồn hiện tại theo kho</h4><table class="table table-sm"><tbody>%s</tbody></table>'
                '<p class="text-muted">Luật An toàn thực phẩm, Điều 54; Nghị định 46/2026/NĐ-CP, Điều 43.</p>') % (
                escape(lot.name), escape(product.display_name), escape(product.uom or ''), _d(lot.production_date),
                _d(lot.expiry_date), product.shelf_life_days or '',
                _('Đang cách ly: %s.') % escape(lot.hold_reason or '') if lot.hold else '',
                table(rows_up), table(rows_down), table(rows_other),
                rows_stock or '<tr><td>Không còn tồn</td></tr>')


class LfoodRecall(models.Model):
    _name = 'lfood.recall'
    _description = 'Thu hồi sản phẩm'
    _order = 'date desc, id desc'

    name = fields.Char('Số', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    date = fields.Date('Ngày quyết định thu hồi', required=True, default=fields.Date.context_today)
    lot_ids = fields.Many2many('lfood.stock.lot', string='Lô thu hồi', required=True)
    reason = fields.Text('Lý do không bảo đảm an toàn', required=True)
    kind = fields.Selection([('voluntary', 'Tự nguyện'), ('mandatory', 'Bắt buộc theo yêu cầu cơ quan có thẩm quyền')],
                            'Hình thức', required=True, default='voluntary')
    authority_ref = fields.Char('Văn bản của cơ quan có thẩm quyền')
    deadline = fields.Date('Thời hạn hoàn thành thu hồi')
    handling = fields.Selection([('fix', 'Khắc phục lỗi'), ('repurpose', 'Chuyển mục đích sử dụng'),
                                 ('reexport', 'Tái xuất'), ('destroy', 'Tiêu hủy')], 'Biện pháp xử lý')
    line_ids = fields.One2many('lfood.recall.line', 'recall_id', 'Khách hàng phải thu hồi')
    qty_shipped = fields.Float('Đã giao', digits=(16, 3), compute='_compute_totals')
    qty_returned = fields.Float('Đã thu hồi', digits=(16, 3), compute='_compute_totals')
    rate = fields.Float('Tỷ lệ thu hồi (%)', digits=(5, 1), compute='_compute_totals')
    result = fields.Text('Kết quả, báo cáo cơ quan quản lý')
    report_html = fields.Html('Báo cáo thu hồi', compute='_compute_totals', sanitize=False)
    state = fields.Selection([('draft', 'Nháp'), ('running', 'Đang thu hồi'), ('done', 'Hoàn thành')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)

    @api.depends('line_ids.notified_on', 'line_ids.note', 'handling', 'result', 'kind', 'authority_ref', 'deadline',
                 'reason', 'lot_ids', 'state')
    def _compute_totals(self):
        for rec in self:
            rec.qty_shipped = sum(rec.line_ids.mapped('qty_shipped'))
            rec.qty_returned = sum(rec.line_ids.mapped('qty_returned'))
            rec.rate = rec.qty_returned / rec.qty_shipped * 100 if rec.qty_shipped else 0
            rows = ''.join('<tr><td>%s</td><td>%s</td><td>%s</td><td class="text-end">%s</td><td class="text-end">%s</td>'
                           '<td>%s</td></tr>' % (escape(l.partner_id.name), escape(l.lot_id.name), _d(l.notified_on),
                                                 '%g' % l.qty_shipped, '%g' % l.qty_returned, escape(l.note or ''))
                           for l in rec.line_ids)
            rec.report_html = (
                '<h3>BÁO CÁO KẾT QUẢ THU HỒI SẢN PHẨM</h3><p>Số %s, ngày %s. Hình thức: %s. %s</p>'
                '<p>Sản phẩm, lô: %s. Lý do: %s</p>'
                '<table class="table table-sm"><thead><tr><th>Khách hàng</th><th>Lô</th><th>Ngày thông báo</th>'
                '<th>Đã giao</th><th>Đã thu hồi</th><th>Ghi chú</th></tr></thead><tbody>%s</tbody></table>'
                '<p>Tổng đã giao %s, đã thu hồi %s (%.1f%%). Biện pháp xử lý: %s. %s</p>') % (
                escape(rec.name or ''), _d(rec.date), dict(rec._fields['kind'].selection).get(rec.kind, ''),
                escape(_('Theo văn bản %s, hạn %s.') % (rec.authority_ref, _d(rec.deadline))) if rec.authority_ref else '',
                escape(', '.join('%s lô %s' % (l.product_id.display_name, l.name) for l in rec.lot_ids)),
                escape(rec.reason or ''), rows, '%g' % rec.qty_shipped, '%g' % rec.qty_returned, rec.rate,
                dict(rec._fields['handling'].selection).get(rec.handling, ''), escape(rec.result or ''))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('lfood.recall') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_recall_system') and self.filtered(lambda r: r.state == 'done') \
                and set(vals) - {'result'}:
            raise UserError(_('Đợt thu hồi đã hoàn thành không sửa được.'))
        return super().write(vals)

    def action_start(self):
        """Cách ly các lô, lấy danh sách khách hàng đã nhận hàng."""
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if rec.kind == 'mandatory' and not (rec.authority_ref and rec.deadline):
                raise UserError(_('Thu hồi bắt buộc: ghi văn bản và thời hạn của cơ quan có thẩm quyền.'))
            rec.lot_ids.filtered(lambda l: not l.hold).action_hold(_('Thu hồi theo %s') % rec.name)
            lines = []
            for lot in rec.lot_ids:
                for partner, qty in lot._shipments().items():
                    lines.append((0, 0, {'partner_id': partner.id, 'lot_id': lot.id}))
            rec.with_context(lfood_recall_system=True).write({'state': 'running', 'line_ids': lines})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Bắt đầu thu hồi %s: %s khách hàng, lý do: %s') % (rec.name, len(rec.line_ids), rec.reason))
        return True

    def action_done(self):
        for rec in self.filtered(lambda r: r.state == 'running'):
            if not rec.handling:
                raise UserError(_('Chọn biện pháp xử lý sản phẩm thu hồi.'))
            if rec.line_ids.filtered(lambda l: not l.notified_on):
                raise UserError(_('Còn khách hàng chưa được thông báo thu hồi.'))
            rec.with_context(lfood_recall_system=True).write({'state': 'done'})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Hoàn thành thu hồi %s: đã thu %s/%s') % (rec.name, '%g' % rec.qty_returned, '%g' % rec.qty_shipped))
        return True


class LfoodRecallLine(models.Model):
    _name = 'lfood.recall.line'
    _description = 'Khách hàng trong đợt thu hồi'
    _order = 'partner_id'

    recall_id = fields.Many2one('lfood.recall', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one('res.partner', 'Khách hàng', required=True)
    lot_id = fields.Many2one('lfood.stock.lot', 'Lô', required=True)
    qty_shipped = fields.Float('Đã giao', digits=(16, 3), compute='_compute_qty')
    qty_returned = fields.Float('Đã trả về', digits=(16, 3), compute='_compute_qty')
    notified_on = fields.Date('Ngày thông báo khách')
    picking_ids = fields.Many2many('lfood.stock.picking', string='Phiếu nhập hàng thu hồi')
    note = fields.Char('Ghi chú')

    def _compute_qty(self):
        for rec in self:
            moves = rec.lot_id._trace_moves().filtered(lambda v: v.picking_id.partner_id == rec.partner_id)
            rec.qty_shipped = -sum(moves.filtered(lambda v: v.picking_id.purpose in DOWNSTREAM and v.qty < 0).mapped('qty'))
            rec.qty_returned = sum(moves.filtered(lambda v: v.picking_id.purpose == 'return_in' and v.qty > 0).mapped('qty'))

    def action_notify(self):
        self.filtered(lambda l: not l.notified_on).write({'notified_on': fields.Date.context_today(self)})
        return True

    def action_receive(self):
        """Lập phiếu nhập hàng thu hồi nháp theo số còn ở khách."""
        self.ensure_one()
        left = self.qty_shipped - self.qty_returned
        if left <= 0:
            raise UserError(_('Khách đã trả đủ.'))
        warehouse = self.env['lfood.warehouse'].search([('company_id', '=', self.recall_id.company_id.id)], limit=1)
        picking = self.env['lfood.stock.picking'].create({
            'company_id': self.recall_id.company_id.id, 'kind': 'in', 'purpose': 'return_in', 'partner_id': self.partner_id.id,
            'warehouse_id': warehouse.id, 'memo': _('Nhận hàng thu hồi theo %s') % self.recall_id.name,
            'line_ids': [(0, 0, {'product_id': self.lot_id.product_id.id, 'lot_id': self.lot_id.id, 'quantity': left})]})
        self.picking_ids = [(4, picking.id)]
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.stock.picking', 'res_id': picking.id, 'view_mode': 'form'}
