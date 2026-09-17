"""Mua hàng: yêu cầu mua, đơn mua, nhận hàng và đối chiếu 3 bên.

Luồng: phòng ban lập Yêu cầu mua (kiểm soát ngân sách theo khoản mục) -> Kế toán trưởng duyệt ->
lập Đơn mua gửi nhà cung cấp -> nhận hàng bằng phiếu nhập kho của phân hệ kho -> đối chiếu
số lượng và đơn giá giữa đơn mua, phiếu nhận và hóa đơn trước khi ghi phiếu.
Hạch toán vẫn do phiếu nhập kho và chứng từ mua dịch vụ đảm nhận; đơn mua không ghi sổ.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd

REQUEST_STATES = [('draft', 'Nháp'), ('waiting', 'Chờ duyệt'), ('approved', 'Đã duyệt'),
                  ('refused', 'Từ chối'), ('ordered', 'Đã đặt hàng'), ('cancel', 'Đã hủy')]
ORDER_STATES = [('draft', 'Nháp'), ('waiting', 'Chờ duyệt'), ('confirmed', 'Đã xác nhận'),
                ('done', 'Đã nhận đủ'), ('cancel', 'Đã hủy')]


class LfoodPurchaseRequest(models.Model):
    _name = 'lfood.purchase.request'
    _description = 'Yêu cầu mua'
    _order = 'date desc, id desc'

    name = fields.Char('Số yêu cầu', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    date = fields.Date('Ngày lập', required=True, default=fields.Date.context_today, index=True)
    date_needed = fields.Date('Ngày cần hàng')
    department = fields.Char('Bộ phận đề nghị')
    user_id = fields.Many2one('res.users', 'Người đề nghị', default=lambda s: s.env.user, readonly=True)
    reason = fields.Char('Lý do')
    line_ids = fields.One2many('lfood.purchase.request.line', 'request_id', 'Nội dung', copy=True)
    quote_ids = fields.One2many('lfood.purchase.quote', 'request_id', 'Báo giá')
    quote_count = fields.Integer('Số báo giá', compute='_compute_quote_count')
    amount = fields.Float('Giá trị dự kiến', digits=(16, 0), compute='_compute_amount', store=True)
    budget_warning = fields.Text('Cảnh báo ngân sách', readonly=True, copy=False)
    state = fields.Selection(REQUEST_STATES, 'Trạng thái', default='draft', required=True, readonly=True,
                             copy=False, index=True)
    approved_by = fields.Many2one('res.users', 'Người duyệt', readonly=True, copy=False)
    order_ids = fields.One2many('lfood.purchase.order', 'request_id', 'Đơn mua')

    @api.depends('line_ids.amount')
    def _compute_amount(self):
        for rec in self:
            rec.amount = sum(rec.line_ids.mapped('amount'))

    @api.depends('quote_ids')
    def _compute_quote_count(self):
        for rec in self:
            rec.quote_count = len(rec.quote_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.purchase.request') or '/'
        return super().create(vals_list)

    def _check_quote_policy(self):
        """Quy chế công ty: yêu cầu mua từ một mức tiền phải có đủ số báo giá tối thiểu."""
        self.ensure_one()
        company = self.company_id
        if company.lfood_min_quotes and self.amount >= company.lfood_quote_threshold \
                and self.quote_count < company.lfood_min_quotes:
            raise UserError(_('Yêu cầu mua %s có giá trị %s, từ mức %s phải có ít nhất %s báo giá; hiện có %s.')
                            % (self.name, vnd(self.amount), vnd(company.lfood_quote_threshold),
                               company.lfood_min_quotes, self.quote_count))

    def write(self, vals):
        if not self.env.context.get('lfood_purchase_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái yêu cầu mua chỉ đổi bằng các nút trên màn hình.'))
            if self.filtered(lambda r: r.state not in ('draft', 'refused')):
                raise UserError(_('Yêu cầu mua đã trình duyệt không sửa được.'))
        return super().write(vals)

    def _check_budget(self):
        """Kiểm soát ngân sách theo khoản mục (NS03): cảnh báo, không chặn."""
        self.ensure_one()
        Budget = self.env['lfood.budget'].with_company(self.company_id)
        messages = []
        for item in self.line_ids.mapped('cost_item_id'):
            warning = Budget.check_over(item, self.date_needed or self.date)
            if warning:
                messages.append(warning)
        return '\n'.join(messages)

    def action_confirm(self):
        for rec in self:
            if rec.state not in ('draft', 'refused'):
                raise UserError(_('Chỉ trình duyệt yêu cầu đang ở trạng thái Nháp.'))
            if not rec.line_ids:
                raise UserError(_('Yêu cầu mua chưa có nội dung.'))
            rec.with_context(lfood_purchase_system=True).write({
                'state': 'waiting', 'budget_warning': rec._check_budget()})
        return True

    def action_approve(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng trở lên được duyệt yêu cầu mua.'))
        for rec in self.filtered(lambda r: r.state == 'waiting'):
            rec.with_context(lfood_purchase_system=True).write({'state': 'approved', 'approved_by': self.env.uid})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name,
                summary=_('Duyệt yêu cầu mua %s, giá trị dự kiến %s') % (rec.name, vnd(rec.amount)))
        return True

    def action_refuse(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng trở lên được từ chối yêu cầu mua.'))
        self.filtered(lambda r: r.state == 'waiting').with_context(lfood_purchase_system=True).write({'state': 'refused'})
        return True

    def action_cancel(self):
        self.filtered(lambda r: r.state != 'ordered').with_context(lfood_purchase_system=True).write({'state': 'cancel'})
        return True

    def action_make_order(self):
        """Lập đơn mua từ yêu cầu đã duyệt."""
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('Chỉ lập đơn mua từ yêu cầu đã duyệt.'))
        self._check_quote_policy()
        order = self.env['lfood.purchase.order'].create({
            'company_id': self.company_id.id,
            'request_id': self.id,
            'line_ids': [(0, 0, {'product_id': l.product_id.id, 'name': l.name, 'quantity': l.quantity,
                                 'price_unit': l.price_unit, 'cost_item_id': l.cost_item_id.id})
                         for l in self.line_ids],
        })
        self.with_context(lfood_purchase_system=True).write({'state': 'ordered'})
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.purchase.order', 'res_id': order.id,
                'view_mode': 'form'}


class LfoodPurchaseRequestLine(models.Model):
    _name = 'lfood.purchase.request.line'
    _description = 'Dòng yêu cầu mua'

    request_id = fields.Many2one('lfood.purchase.request', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='request_id.company_id', store=True)
    product_id = fields.Many2one('lfood.product', 'Mặt hàng')
    name = fields.Char('Nội dung', required=True)
    quantity = fields.Float('Số lượng', digits=(16, 3), required=True, default=1)
    price_unit = fields.Float('Đơn giá dự kiến', digits=(16, 2))
    amount = fields.Float('Thành tiền', digits=(16, 0), compute='_compute_amount', store=True, readonly=False)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP')

    @api.depends('quantity', 'price_unit')
    def _compute_amount(self):
        for rec in self:
            rec.amount = round(rec.quantity * rec.price_unit)

    @api.onchange('product_id')
    def _onchange_product(self):
        if self.product_id and not self.name:
            self.name = self.product_id.name


class LfoodPurchaseQuote(models.Model):
    """Báo giá nhà cung cấp gửi về cho một yêu cầu mua, dùng để so sánh trước khi đặt hàng (MH02)."""
    _name = 'lfood.purchase.quote'
    _description = 'Báo giá nhà cung cấp'
    _order = 'request_id, amount_total'

    request_id = fields.Many2one('lfood.purchase.request', 'Yêu cầu mua', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='request_id.company_id', store=True, index=True)
    partner_id = fields.Many2one('res.partner', 'Nhà cung cấp', required=True, index=True)
    date = fields.Date('Ngày báo giá', required=True, default=fields.Date.context_today)
    valid_until = fields.Date('Hiệu lực đến')
    lead_days = fields.Integer('Thời gian giao (ngày)')
    note = fields.Char('Ghi chú')
    line_ids = fields.One2many('lfood.purchase.quote.line', 'quote_id', 'Chi tiết', copy=True)
    amount = fields.Float('Tiền hàng', digits=(16, 0), compute='_compute_amount', store=True)
    amount_tax = fields.Float('Thuế GTGT', digits=(16, 0), compute='_compute_amount', store=True)
    amount_total = fields.Float('Tổng thanh toán', digits=(16, 0), compute='_compute_amount', store=True)
    chosen = fields.Boolean('Đã chọn', readonly=True, copy=False)
    order_id = fields.Many2one('lfood.purchase.order', 'Đơn mua đã lập', readonly=True, copy=False)

    @api.depends('line_ids.amount', 'line_ids.tax')
    def _compute_amount(self):
        for rec in self:
            rec.amount = sum(rec.line_ids.mapped('amount'))
            rec.amount_tax = sum(rec.line_ids.mapped('tax'))
            rec.amount_total = rec.amount + rec.amount_tax

    @api.depends('partner_id', 'amount_total')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - %s' % (rec.partner_id.name or '', vnd(rec.amount_total))

    def action_choose(self):
        """Chọn báo giá này và lập đơn mua theo đúng giá đã báo."""
        self.ensure_one()
        request = self.request_id
        if request.state != 'approved':
            raise UserError(_('Chỉ chọn báo giá của yêu cầu mua đã duyệt.'))
        request._check_quote_policy()
        order = self.env['lfood.purchase.order'].create({
            'company_id': request.company_id.id, 'request_id': request.id, 'partner_id': self.partner_id.id,
            'date_expected': fields.Date.add(fields.Date.context_today(self), days=self.lead_days or 0),
            'memo': _('Theo báo giá của %s ngày %s') % (self.partner_id.name, self.date.strftime('%d/%m/%Y')),
            'line_ids': [(0, 0, {'product_id': l.product_id.id, 'name': l.name, 'quantity': l.quantity,
                                 'price_unit': l.price_unit, 'vat_rate_id': l.vat_rate_id.id,
                                 'cost_item_id': l.cost_item_id.id}) for l in self.line_ids],
        })
        self.write({'chosen': True, 'order_id': order.id})
        request.with_context(lfood_purchase_system=True).write({'state': 'ordered'})
        cheapest = min(request.quote_ids.mapped('amount_total') or [0])
        self.env['lfood.audit.log']._record_event(
            'state', model=request._name, res_id=request.id, res_name=request.name,
            summary=_('Chọn báo giá %s cho %s: %s, báo giá thấp nhất %s')
                    % (self.partner_id.name, request.name, vnd(self.amount_total), vnd(cheapest)))
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.purchase.order', 'res_id': order.id,
                'view_mode': 'form'}


class LfoodPurchaseQuoteLine(models.Model):
    _name = 'lfood.purchase.quote.line'
    _description = 'Dòng báo giá'

    quote_id = fields.Many2one('lfood.purchase.quote', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='quote_id.company_id', store=True)
    product_id = fields.Many2one('lfood.product', 'Mặt hàng')
    name = fields.Char('Nội dung', required=True)
    quantity = fields.Float('Số lượng', digits=(16, 3), required=True, default=1)
    price_unit = fields.Float('Đơn giá báo', digits=(16, 2))
    amount = fields.Float('Thành tiền', digits=(16, 0), compute='_compute_amount', store=True, readonly=False)
    vat_rate_id = fields.Many2one('lfood.vat.rate', 'Thuế suất')
    tax = fields.Float('Tiền thuế', digits=(16, 0), compute='_compute_tax', store=True, readonly=False)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP')

    @api.depends('quantity', 'price_unit')
    def _compute_amount(self):
        for rec in self:
            rec.amount = round(rec.quantity * rec.price_unit)

    @api.depends('amount', 'vat_rate_id')
    def _compute_tax(self):
        for rec in self:
            rec.tax = round(rec.amount * (rec.vat_rate_id.rate or 0) / 100)


class LfoodPurchaseOrder(models.Model):
    _name = 'lfood.purchase.order'
    _description = 'Đơn mua hàng'
    _order = 'date desc, id desc'

    name = fields.Char('Số đơn mua', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    partner_id = fields.Many2one('res.partner', 'Nhà cung cấp', index=True,
                                 help='Chọn trước khi xác nhận đơn; lập từ yêu cầu mua thì để trống tới khi chọn được nhà cung cấp')
    date = fields.Date('Ngày đặt', required=True, default=fields.Date.context_today, index=True)
    date_expected = fields.Date('Ngày giao dự kiến')
    request_id = fields.Many2one('lfood.purchase.request', 'Từ yêu cầu mua', readonly=True, index=True)
    warehouse_id = fields.Many2one('lfood.warehouse', 'Kho nhận')
    memo = fields.Char('Diễn giải')
    line_ids = fields.One2many('lfood.purchase.order.line', 'order_id', 'Hàng hóa, dịch vụ', copy=True)
    amount = fields.Float('Tiền hàng', digits=(16, 0), compute='_compute_amount', store=True)
    amount_tax = fields.Float('Thuế GTGT', digits=(16, 0), compute='_compute_amount', store=True)
    amount_total = fields.Float('Tổng thanh toán', digits=(16, 0), compute='_compute_amount', store=True)
    state = fields.Selection(ORDER_STATES, 'Trạng thái', default='draft', required=True, readonly=True,
                             copy=False, index=True)
    confirmed_by = fields.Many2one('res.users', 'Người duyệt', readonly=True, copy=False)
    picking_ids = fields.One2many('lfood.stock.picking', 'purchase_order_id', 'Phiếu nhập kho')
    picking_count = fields.Integer('Số phiếu nhập', compute='_compute_picking_count')
    match_note = fields.Text('Đối chiếu 3 bên', compute='_compute_match_note')

    @api.depends('line_ids.amount', 'line_ids.tax')
    def _compute_amount(self):
        for rec in self:
            rec.amount = sum(rec.line_ids.mapped('amount'))
            rec.amount_tax = sum(rec.line_ids.mapped('tax'))
            rec.amount_total = rec.amount + rec.amount_tax

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for rec in self:
            rec.picking_count = len(rec.picking_ids)

    @api.depends('line_ids.quantity', 'line_ids.qty_received', 'line_ids.qty_billed')
    def _compute_match_note(self):
        for rec in self:
            rows = []
            for line in rec.line_ids:
                if line.qty_received != line.quantity or line.qty_billed != line.qty_received:
                    rows.append(_('%s: đặt %s, đã nhận %s, đã có hóa đơn %s')
                                % (line.name, line.quantity, line.qty_received, line.qty_billed))
            rec.match_note = '\n'.join(rows) or _('Đơn mua, phiếu nhận và hóa đơn khớp nhau.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.purchase.order') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_purchase_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái đơn mua chỉ đổi bằng các nút trên màn hình.'))
            if self.filtered(lambda r: r.state not in ('draft',)):
                raise UserError(_('Đơn mua đã xác nhận không sửa được. Hủy đơn rồi lập đơn mới.'))
        return super().write(vals)

    def action_confirm(self):
        """Xác nhận đơn; vượt hạn mức duyệt của công ty thì phải Kế toán trưởng duyệt."""
        for rec in self:
            if rec.state not in ('draft', 'waiting'):
                raise UserError(_('Chỉ xác nhận đơn mua đang ở trạng thái Nháp.'))
            if not rec.line_ids:
                raise UserError(_('Đơn mua chưa có hàng hóa.'))
            if not rec.partner_id:
                raise UserError(_('Chọn nhà cung cấp trước khi xác nhận đơn mua.'))
            over = rec.amount_total > rec.company_id.lfood_voucher_approval_limit
            if over and not self.env.user.has_group('lfood_base.group_chief_accountant'):
                rec.with_context(lfood_purchase_system=True).write({'state': 'waiting'})
                self.env['lfood.audit.log']._record_event(
                    'state', model=rec._name, res_id=rec.id, res_name=rec.name,
                    summary=_('Đơn mua %s tổng %s vượt hạn mức %s: chờ duyệt')
                            % (rec.name, vnd(rec.amount_total), vnd(rec.company_id.lfood_voucher_approval_limit)))
                continue
            rec.with_context(lfood_purchase_system=True).write({
                'state': 'confirmed', 'confirmed_by': self.env.uid if over else False})
        return True

    def action_cancel(self):
        for rec in self:
            if rec.picking_ids.filtered(lambda p: p.state == 'done'):
                raise UserError(_('Đơn mua %s đã có phiếu nhập kho đã ghi, không hủy được.') % rec.name)
            rec.with_context(lfood_purchase_system=True).write({'state': 'cancel'})
        return True

    def action_receive(self):
        """Lập phiếu nhập kho nháp cho phần còn lại chưa nhận."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_('Chỉ nhận hàng của đơn mua đã xác nhận.'))
        if not self.warehouse_id:
            raise UserError(_('Chọn kho nhận trên đơn mua.'))
        lines = []
        for line in self.line_ids:
            remain = line.quantity - line.qty_received
            if remain <= 0 or not line.product_id:
                continue
            lines.append((0, 0, {'product_id': line.product_id.id, 'quantity': remain,
                                 'price_unit': line.price_unit, 'vat_rate_id': line.vat_rate_id.id}))
        if not lines:
            raise UserError(_('Đơn mua đã nhận đủ hàng, hoặc các dòng là dịch vụ nên dùng chứng từ mua dịch vụ.'))
        picking = self.env['lfood.stock.picking'].create({
            'company_id': self.company_id.id, 'kind': 'in', 'purpose': 'purchase',
            'warehouse_id': self.warehouse_id.id, 'partner_id': self.partner_id.id,
            'purchase_order_id': self.id, 'memo': _('Nhận hàng theo đơn mua %s') % self.name,
            'line_ids': lines,
        })
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.stock.picking', 'res_id': picking.id,
                'view_mode': 'form'}

    def action_view_pickings(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Phiếu nhập kho'), 'res_model': 'lfood.stock.picking',
                'view_mode': 'list,form', 'domain': [('purchase_order_id', '=', self.id)]}

    def _update_state(self):
        for rec in self:
            if rec.state == 'confirmed' and all(l.qty_received >= l.quantity for l in rec.line_ids):
                rec.with_context(lfood_purchase_system=True).write({'state': 'done'})
        return True


class LfoodPurchaseOrderLine(models.Model):
    _name = 'lfood.purchase.order.line'
    _description = 'Dòng đơn mua'

    order_id = fields.Many2one('lfood.purchase.order', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    product_id = fields.Many2one('lfood.product', 'Mặt hàng')
    name = fields.Char('Nội dung', required=True)
    quantity = fields.Float('Số lượng đặt', digits=(16, 3), required=True, default=1)
    price_unit = fields.Float('Đơn giá', digits=(16, 2))
    amount = fields.Float('Thành tiền', digits=(16, 0), compute='_compute_amount', store=True, readonly=False)
    vat_rate_id = fields.Many2one('lfood.vat.rate', 'Thuế suất')
    tax = fields.Float('Tiền thuế', digits=(16, 0), compute='_compute_tax', store=True, readonly=False)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP')
    qty_received = fields.Float('Đã nhận', digits=(16, 3), compute='_compute_progress', store=True)
    qty_billed = fields.Float('Đã có hóa đơn', digits=(16, 3), compute='_compute_progress', store=True)

    @api.depends('quantity', 'price_unit')
    def _compute_amount(self):
        for rec in self:
            rec.amount = round(rec.quantity * rec.price_unit)

    @api.depends('amount', 'vat_rate_id')
    def _compute_tax(self):
        for rec in self:
            rec.tax = round(rec.amount * (rec.vat_rate_id.rate or 0) / 100)

    @api.depends('order_id.picking_ids.state', 'order_id.picking_ids.kind', 'order_id.picking_ids.line_ids.quantity',
                 'order_id.picking_ids.invoice_number')
    def _compute_progress(self):
        """Đã nhận trừ đi phần đã trả lại nhà cung cấp (phiếu xuất trả lại hàng mua)."""
        for rec in self:
            done = rec.order_id.picking_ids.filtered(lambda p: p.state == 'done')
            rec.qty_received = rec._signed_qty(done)
            rec.qty_billed = rec._signed_qty(done.filtered('invoice_number'))

    def _signed_qty(self, pickings):
        self.ensure_one()
        total = 0.0
        for pick in pickings:
            sign = 1 if pick.kind == 'in' else -1
            total += sign * sum(pick.line_ids.filtered(lambda l: l.product_id == self.product_id).mapped('quantity'))
        return total

    @api.onchange('product_id')
    def _onchange_product(self):
        if self.product_id and not self.name:
            self.name = self.product_id.name

    def write(self, vals):
        if not self.env.context.get('lfood_purchase_system') and self.filtered(lambda l: l.order_id.state != 'draft'):
            raise UserError(_('Đơn mua đã xác nhận không sửa được.'))
        return super().write(vals)
