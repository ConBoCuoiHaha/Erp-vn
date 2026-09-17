"""Kiểm soát kho: cách ly lô (KHO09), hủy hàng hư hỏng, hết hạn (KHO08), tồn tối thiểu và đề xuất mua (KHO10).

Hủy hàng: hồ sơ theo Thông tư 20/2026/TT-BTC (điểm b9) để chi phí được trừ khi tính thuế TNDN: quyết định hủy của
người có thẩm quyền, biên bản kiểm kê giá trị ghi nguyên nhân, chủng loại, số lượng, giá trị, phương án xử lý,
quyết định thành lập hội đồng xử lý. Hạch toán theo Thông tư 99/2025/TT-BTC: giá trị hàng hủy ghi Nợ 632 / Có 152,
155, 156; phần bồi thường của người có lỗi ghi Nợ 1388 / Có 632. Dự phòng giảm giá đã trích cho lô hủy được hoàn nhập
khi xác định dự phòng cuối kỳ (phân hệ dự phòng), không hoàn nhập ngay tại đây.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd

# nội dung xuất được phép lấy lô đang cách ly
HOLD_ALLOWED = ('disposal', 'return_out', 'count', 'transfer')
REASONS = [('expired', 'Hết hạn sử dụng'), ('damaged', 'Hư hỏng, biến đổi sinh hóa tự nhiên'),
           ('quality', 'Không đạt chất lượng, không đủ điều kiện lưu thông'), ('obsolete', 'Lỗi thời, không còn nhu cầu sử dụng')]


class LfoodStockLot(models.Model):
    _inherit = 'lfood.stock.lot'

    hold = fields.Boolean('Đang cách ly', readonly=True, index=True)
    hold_reason = fields.Char('Lý do cách ly', readonly=True)
    hold_date = fields.Date('Ngày cách ly', readonly=True)
    hold_by = fields.Many2one('res.users', 'Người cách ly', readonly=True)

    def action_hold(self, reason):
        if not reason:
            raise UserError(_('Nhập lý do cách ly.'))
        for lot in self.filtered(lambda l: not l.hold):
            lot.write({'hold': True, 'hold_reason': reason, 'hold_by': self.env.uid,
                       'hold_date': fields.Date.context_today(self)})
            self.env['lfood.audit.log']._record_event(
                'state', model=lot._name, res_id=lot.id, res_name=lot.display_name,
                summary=_('Cách ly lô %s của %s: %s') % (lot.name, lot.product_id.display_name, reason))
        return True

    def action_open_hold(self):
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.stock.hold.wizard', 'view_mode': 'form',
                'target': 'new', 'context': {'default_lot_ids': [(6, 0, self.ids)]}}

    def action_release(self):
        if not (self.env.user.has_group('lfood_base.group_chief_accountant')
                or self.env.user.has_group('lfood_base.group_director')):
            raise UserError(_('Chỉ Kế toán trưởng hoặc Giám đốc được giải phóng lô cách ly.'))
        for lot in self.filtered('hold'):
            lot.sudo().write({'hold': False})
            self.env['lfood.audit.log']._record_event(
                'state', model=lot._name, res_id=lot.id, res_name=lot.display_name,
                summary=_('Giải phóng lô %s của %s (đã cách ly vì: %s)') % (
                    lot.name, lot.product_id.display_name, lot.hold_reason))
        return True


class LfoodStockHoldWizard(models.TransientModel):
    _name = 'lfood.stock.hold.wizard'
    _description = 'Cách ly lô'

    lot_ids = fields.Many2many('lfood.stock.lot', string='Lô', required=True)
    reason = fields.Char('Lý do', required=True)

    def action_apply(self):
        self.lot_ids.action_hold(self.reason)
        return {'type': 'ir.actions.act_window_close'}


class LfoodProduct(models.Model):
    _inherit = 'lfood.product'

    min_qty = fields.Float('Tồn tối thiểu', digits=(16, 3), help='Tồn các kho của công ty dưới mức này thì đề xuất mua')
    max_qty = fields.Float('Tồn tối đa', digits=(16, 3), help='Đề xuất mua đủ lên mức này; để 0 thì mua bù về tồn tối thiểu')


class LfoodStockPicking(models.Model):
    _inherit = 'lfood.stock.picking'

    purpose = fields.Selection(selection_add=[('disposal', 'Xuất hủy')],
                               ondelete={'disposal': lambda recs: recs.write({'purpose': 'internal'})})
    disposal_id = fields.Many2one('lfood.stock.disposal', 'Biên bản hủy', index=True, readonly=True)

    @api.depends('kind', 'purpose')
    def _compute_counterpart(self):
        super()._compute_counterpart()
        for rec in self.filtered(lambda r: r.purpose == 'disposal'):
            rec.counterpart_account = '632'

    def _fefo_lot_domain(self, line):
        domain = super()._fefo_lot_domain(line)
        if self.purpose not in HOLD_ALLOWED:
            domain += [('hold', '=', False)]
        return domain

    def action_done(self):
        for rec in self.filtered(lambda r: r.state == 'draft' and r.kind == 'out'):
            if rec.purpose == 'disposal' and not rec.disposal_id:
                raise UserError(_('Xuất hủy phải lập từ biên bản hủy hàng đã được duyệt.'))
            if rec.purpose not in HOLD_ALLOWED:
                held = rec.line_ids.mapped('lot_id').filtered('hold')
                if held:
                    raise UserError(_('Lô đang cách ly, không được xuất: %s.') % ', '.join(held.mapped('name')))
        return super().action_done()


class LfoodStockDisposal(models.Model):
    _name = 'lfood.stock.disposal'
    _description = 'Biên bản hủy hàng'
    _order = 'date desc, id desc'

    name = fields.Char('Số biên bản', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    date = fields.Date('Ngày hủy', required=True, default=fields.Date.context_today, index=True)
    warehouse_id = fields.Many2one('lfood.warehouse', 'Kho', required=True)
    reason = fields.Selection(REASONS, 'Nguyên nhân', required=True, default='expired')
    reason_detail = fields.Text('Mô tả nguyên nhân')
    method = fields.Char('Phương án xử lý', default='Tiêu hủy', required=True)
    decision_ref = fields.Char('Số quyết định hủy')
    decision_date = fields.Date('Ngày quyết định hủy')
    committee_ref = fields.Char('Số quyết định thành lập hội đồng')
    members = fields.Text('Thành viên hội đồng')
    compensation = fields.Float('Bồi thường của người có lỗi', digits=(16, 0))
    compensation_partner_id = fields.Many2one('res.partner', 'Người bồi thường')
    line_ids = fields.One2many('lfood.stock.disposal.line', 'disposal_id', 'Hàng hủy', copy=True)
    amount = fields.Float('Giá trị hàng hủy', digits=(16, 0), compute='_compute_amount', store=True)
    picking_id = fields.Many2one('lfood.stock.picking', 'Phiếu xuất hủy', readonly=True, copy=False)
    approved_by = fields.Many2one('res.users', 'Người duyệt', readonly=True, copy=False)
    state = fields.Selection([('draft', 'Nháp'), ('approved', 'Đã duyệt'), ('done', 'Đã hủy, ghi sổ'), ('cancel', 'Đã bỏ')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)
    missing_docs = fields.Char('Hồ sơ còn thiếu', compute='_compute_missing_docs')
    report_html = fields.Html('Biên bản', compute='_compute_report_html', sanitize=False)

    @api.depends('line_ids.value', 'line_ids.quantity', 'state')
    def _compute_amount(self):
        for rec in self:
            rec.amount = sum(rec.line_ids.mapped('value'))

    @api.depends('decision_ref', 'decision_date', 'committee_ref', 'members', 'line_ids')
    def _compute_missing_docs(self):
        for rec in self:
            missing = []
            if not (rec.decision_ref and rec.decision_date):
                missing.append(_('quyết định hủy'))
            if not rec.committee_ref:
                missing.append(_('quyết định thành lập hội đồng'))
            if not rec.members:
                missing.append(_('thành viên hội đồng'))
            if not rec.line_ids:
                missing.append(_('danh mục hàng hủy'))
            rec.missing_docs = ', '.join(missing)

    @api.constrains('compensation')
    def _check_compensation(self):
        for rec in self:
            if rec.compensation < 0:
                raise ValidationError(_('Tiền bồi thường không âm.'))
            if rec.compensation and not rec.compensation_partner_id:
                raise ValidationError(_('Chọn người bồi thường.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.stock.disposal') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_disposal_system') and self.filtered(lambda r: r.state != 'draft'):
            raise UserError(_('Biên bản đã duyệt không sửa được.'))
        return super().write(vals)

    def action_load_holds(self):
        """Lấy các lô đang cách ly hoặc đã hết hạn còn tồn tại kho."""
        self.ensure_one()
        Lot = self.env['lfood.stock.lot']
        lots = Lot.search(['|', ('hold', '=', True), ('expiry_date', '<=', self.date)])
        vals = []
        for lot in lots - self.line_ids.mapped('lot_id'):
            qty = lot.product_id._position(self.warehouse_id, lot)[0]
            if qty > 0:
                vals.append((0, 0, {'product_id': lot.product_id.id, 'lot_id': lot.id, 'quantity': qty}))
        self.write({'line_ids': vals})
        return True

    def action_approve(self):
        if not self.env.user.has_group('lfood_base.group_director'):
            raise UserError(_('Chỉ Giám đốc (người có thẩm quyền) được duyệt hủy hàng.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if rec.missing_docs:
                raise UserError(_('Chưa đủ hồ sơ hủy hàng theo Thông tư 20/2026/TT-BTC: %s.') % rec.missing_docs)
            rec._check_available()
            rec.with_context(lfood_disposal_system=True).write({'state': 'approved', 'approved_by': self.env.uid})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Giám đốc duyệt hủy hàng %s theo quyết định %s') % (rec.name, rec.decision_ref))
        return True

    def _check_available(self):
        for line in self.line_ids:
            avail = line.product_id._position(self.warehouse_id, line.lot_id if line.product_id.track_lot else None)[0]
            if line.quantity > avail:
                raise UserError(_('%s lô %s chỉ còn %s tại kho %s.') % (
                    line.product_id.display_name, line.lot_id.name or '', avail, self.warehouse_id.name))

    def action_post(self):
        """Kế toán xuất kho hủy và ghi sổ sau khi Giám đốc duyệt."""
        for rec in self.filtered(lambda r: r.state == 'approved'):
            rec._check_available()
            memo = _('Hủy hàng theo biên bản %s, quyết định %s') % (rec.name, rec.decision_ref)
            picking = self.env['lfood.stock.picking'].create({
                'company_id': rec.company_id.id, 'kind': 'out', 'purpose': 'disposal', 'date': rec.date,
                'warehouse_id': rec.warehouse_id.id, 'disposal_id': rec.id, 'memo': memo,
                'line_ids': [(0, 0, {'product_id': l.product_id.id, 'lot_id': l.lot_id.id, 'quantity': l.quantity})
                             for l in rec.line_ids]})
            picking.action_done()
            for line, pline in zip(rec.line_ids, picking.line_ids):
                line.with_context(lfood_disposal_system=True).value = pline.cost
            if rec.compensation:
                if rec.compensation > rec.amount:
                    raise UserError(_('Tiền bồi thường lớn hơn giá trị hàng hủy.'))
                label = _('Bồi thường hàng hủy %s') % rec.name
                self.env['lfood.move']._create_from_source(
                    rec, 'stock', rec.date,
                    [('1388', rec.compensation, 0, rec.compensation_partner_id, label, None),
                     ('632', 0, rec.compensation, None, label, None)],
                    memo=label, ref=rec.name)
            rec.with_context(lfood_disposal_system=True).write({'state': 'done', 'picking_id': picking.id})
            held = rec.line_ids.mapped('lot_id').filtered('hold')
            held.write({'hold_reason': _('Đã hủy theo %s') % rec.name})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Ghi sổ hủy hàng %s: giá trị %s, bồi thường %s') % (rec.name, vnd(rec.amount), vnd(rec.compensation)))
        return True

    def action_cancel(self):
        self.filtered(lambda r: r.state in ('draft', 'approved')).with_context(lfood_disposal_system=True).write({'state': 'cancel'})
        return True

    @api.depends('line_ids.quantity', 'line_ids.value', 'members', 'reason', 'reason_detail', 'method', 'state',
                 'decision_ref', 'committee_ref', 'compensation')
    def _compute_report_html(self):
        for rec in self:
            rows = ''.join(
                '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td class="text-end">%s</td><td class="text-end">%s</td></tr>' % (
                    i, l.product_id.display_name, l.lot_id.name or '',
                    l.lot_id.expiry_date.strftime('%d/%m/%Y') if l.lot_id.expiry_date else '',
                    ('%g' % l.quantity), vnd(l.value) if rec.state == 'done' else '')
                for i, l in enumerate(rec.line_ids, 1))
            members = '<br/>'.join((rec.members or '').splitlines())
            rec.report_html = (
                '<h3 style="text-align:center">BIÊN BẢN KIỂM KÊ VÀ HỦY HÀNG HÓA</h3>'
                '<p>Số: %s. Ngày: %s. Kho: %s.</p>'
                '<p>Căn cứ quyết định hủy số %s; quyết định thành lập hội đồng số %s.</p>'
                '<p>Thành viên hội đồng:<br/>%s</p>'
                '<p>Nguyên nhân: %s. %s</p><p>Phương án xử lý: %s.</p>'
                '<table class="table table-sm table-bordered"><thead><tr><th>STT</th><th>Hàng hóa</th><th>Số lô</th>'
                '<th>Hạn dùng</th><th>Số lượng</th><th>Giá trị</th></tr></thead><tbody>%s</tbody></table>'
                '<p>Tổng giá trị: %s. Bồi thường: %s.</p>') % (
                rec.name, rec.date.strftime('%d/%m/%Y') if rec.date else '', rec.warehouse_id.name or '',
                rec.decision_ref or '....', rec.committee_ref or '....', members,
                dict(REASONS).get(rec.reason, ''), rec.reason_detail or '', rec.method or '', rows,
                vnd(rec.amount) if rec.state == 'done' else '', vnd(rec.compensation))


class LfoodStockDisposalLine(models.Model):
    _name = 'lfood.stock.disposal.line'
    _description = 'Dòng hàng hủy'

    disposal_id = fields.Many2one('lfood.stock.disposal', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('lfood.product', 'Mặt hàng', required=True)
    lot_id = fields.Many2one('lfood.stock.lot', 'Lô', domain="[('product_id', '=', product_id)]")
    uom = fields.Char(related='product_id.uom')
    quantity = fields.Float('Số lượng', digits=(16, 3), required=True)
    value = fields.Float('Giá trị', digits=(16, 0), readonly=True)

    @api.constrains('quantity', 'lot_id', 'product_id')
    def _check_line(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError(_('Số lượng hủy phải lớn hơn 0.'))
            if rec.product_id.track_lot and not rec.lot_id:
                raise ValidationError(_('%s theo dõi lô: chọn lô hủy.') % rec.product_id.display_name)

    def write(self, vals):
        if not self.env.context.get('lfood_disposal_system') and self.filtered(lambda l: l.disposal_id.state != 'draft'):
            raise UserError(_('Biên bản đã duyệt không sửa được.'))
        return super().write(vals)


class LfoodStockReorder(models.TransientModel):
    _name = 'lfood.stock.reorder'
    _description = 'Đề xuất đặt hàng theo tồn tối thiểu'

    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company)
    line_ids = fields.One2many('lfood.stock.reorder.line', 'reorder_id', 'Mặt hàng dưới tồn tối thiểu')

    def _suggest(self):
        """[(mặt hàng, tồn, đang đặt, đề xuất)] cho hàng có tồn cộng đang đặt dưới tồn tối thiểu."""
        self.ensure_one()
        products = self.env['lfood.product'].search([('min_qty', '>', 0), ('company_id', 'in', (self.company_id.id, False))])
        warehouses = self.env['lfood.warehouse'].search([('company_id', '=', self.company_id.id)])
        order_lines = self.env['lfood.purchase.order.line'].search([
            ('company_id', '=', self.company_id.id), ('product_id', 'in', products.ids),
            ('order_id.state', 'in', ('waiting', 'confirmed'))])
        out = []
        for product in products:
            on_hand = sum(product._position(wh)[0] for wh in warehouses)
            on_order = sum(max(l.quantity - l.qty_received, 0) for l in order_lines if l.product_id == product)
            if on_hand + on_order < product.min_qty:
                target = product.max_qty if product.max_qty > product.min_qty else product.min_qty
                out.append((product, on_hand, on_order, round(target - on_hand - on_order, 3)))
        return out

    def action_compute(self):
        self.ensure_one()
        self.line_ids.unlink()
        self.write({'line_ids': [(0, 0, {'product_id': p.id, 'on_hand': h, 'on_order': o, 'quantity': q})
                                 for p, h, o, q in self._suggest()]})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form',
                'target': 'new'}

    def action_make_request(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: l.quantity > 0)
        if not lines:
            raise UserError(_('Không có mặt hàng nào cần đặt.'))
        request = self.env['lfood.purchase.request'].create({
            'company_id': self.company_id.id, 'reason': _('Bổ sung hàng dưới tồn tối thiểu'), 'department': _('Kho'),
            'line_ids': [(0, 0, {'product_id': l.product_id.id, 'name': l.product_id.name, 'quantity': l.quantity,
                                 'price_unit': l.product_id.avg_cost}) for l in lines]})
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.purchase.request', 'res_id': request.id,
                'view_mode': 'form'}


class LfoodStockReorderLine(models.TransientModel):
    _name = 'lfood.stock.reorder.line'
    _description = 'Dòng đề xuất đặt hàng'

    reorder_id = fields.Many2one('lfood.stock.reorder', required=True, ondelete='cascade')
    product_id = fields.Many2one('lfood.product', 'Mặt hàng', required=True)
    min_qty = fields.Float(related='product_id.min_qty')
    on_hand = fields.Float('Tồn hiện tại', digits=(16, 3))
    on_order = fields.Float('Đang đặt chưa về', digits=(16, 3))
    quantity = fields.Float('Đề xuất mua', digits=(16, 3))
