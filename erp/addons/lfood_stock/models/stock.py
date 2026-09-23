"""Kho: hàng hóa, nguyên vật liệu, lô và hạn dùng, phiếu nhập, xuất, chuyển kho, kiểm kê.

Giá xuất kho: bình quân gia quyền tính theo từng lần phát sinh (một trong các phương pháp nêu tại Thông tư 99/2025/TT-BTC,
phần thuyết minh chính sách kế toán hàng tồn kho). Không cho xuất âm và không cho ghi phiếu có ngày trước lần nhập xuất
gần nhất của mặt hàng, để giá bình quân luôn đúng."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd

KIND_ACCOUNT = {'material': '152', 'tool': '153', 'finished': '155', 'goods': '156'}
PURPOSES = [
    ('purchase', 'Mua hàng'), ('sale', 'Xuất bán'), ('internal', 'Xuất dùng nội bộ'), ('return_in', 'Hàng bán bị trả lại nhập kho'),
    ('return_out', 'Trả lại hàng mua'), ('transfer', 'Chuyển kho'), ('count', 'Kiểm kê'), ('opening', 'Tồn đầu kỳ'), ('factory', 'Nhập thành phẩm từ nhà máy'),
]
IN_PURPOSES = ('purchase', 'return_in', 'count', 'opening', 'factory')
DEFAULT_COUNTER = {('in', 'purchase'): '3311', ('in', 'return_in'): '632', ('in', 'count'): '3381',
                   ('in', 'factory'): '154', ('out', 'sale'): '632', ('out', 'internal'): '6428', ('out', 'return_out'): '3311',
                   ('out', 'count'): '1381'}


class LfoodProduct(models.Model):
    _name = 'lfood.product'
    _description = 'Hàng hóa, vật tư'
    _order = 'code'
    _rec_names_search = ['code', 'name']

    code = fields.Char('Mã hàng', required=True, index=True)
    name = fields.Char('Tên hàng', required=True)
    uom = fields.Char('Đơn vị tính', required=True, default='cái')
    kind = fields.Selection([('goods', 'Hàng hóa'), ('finished', 'Thành phẩm'), ('material', 'Nguyên liệu, vật liệu'), ('tool', 'Công cụ, dụng cụ')],
                            'Loại', required=True, default='goods')
    account = fields.Char('TK kho', compute='_compute_account', store=True, readonly=False)
    track_lot = fields.Boolean('Theo dõi lô, hạn dùng', default=True)
    shelf_life_days = fields.Integer('Hạn dùng (ngày)')
    vat_rate_id = fields.Many2one('lfood.vat.rate', 'Thuế suất mặc định')
    company_id = fields.Many2one('res.company', 'Công ty', default=lambda s: s.env.company, index=True)
    active = fields.Boolean(default=True)
    qty_on_hand = fields.Float('Tồn kho', digits=(16, 3), compute='_compute_stock')
    value_on_hand = fields.Float('Giá trị tồn', digits=(16, 0), compute='_compute_stock')
    avg_cost = fields.Float('Giá bình quân', digits=(16, 2), compute='_compute_stock')

    _code_uniq = models.Constraint('unique(company_id, code)', 'Mã hàng đã tồn tại.')

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '[%s] %s' % (rec.code, rec.name) if rec.code else rec.name

    @api.depends('kind')
    def _compute_account(self):
        for rec in self:
            rec.account = KIND_ACCOUNT.get(rec.kind)

    def _stock_account(self, company):
        """Tài khoản kho theo pháp nhân: pháp nhân không sản xuất mua thành phẩm về thì ghi hàng hóa 156."""
        self.ensure_one()
        if self.kind == 'finished' and not company.lfood_manufacturer:
            return '156'
        return self.account

    def _compute_stock(self):
        for rec in self:
            qty, value = rec._position()
            rec.qty_on_hand, rec.value_on_hand = qty, value
            rec.avg_cost = value / qty if qty else 0

    def _position(self, warehouse=None, lot=None, upto=None):
        self.ensure_one()
        if not self._origin.id:  # biểu mẫu mới, chưa lưu
            return 0, 0
        self.env['lfood.stock.valuation'].flush_model()
        sql = 'SELECT COALESCE(SUM(qty), 0), COALESCE(SUM(value), 0) FROM lfood_stock_valuation WHERE product_id = %s'
        args = [self._origin.id]
        if warehouse:
            sql += ' AND warehouse_id = %s'
            args.append(warehouse.id)
        if lot is not None:
            sql += ' AND lot_id IS NOT DISTINCT FROM %s'
            args.append(lot.id or None)
        if upto:
            sql += ' AND date <= %s'
            args.append(upto)
        self.env.cr.execute(sql, args)
        qty, value = self.env.cr.fetchone()
        return round(qty, 3), round(value)


class ResCompany(models.Model):
    _inherit = 'res.company'

    lfood_manufacturer = fields.Boolean('Có sản xuất', help='Có thì thành phẩm ghi TK 155; không thì hàng mua về ghi TK 156')


class LfoodWarehouse(models.Model):
    _name = 'lfood.warehouse'
    _description = 'Kho'
    _order = 'code'

    code = fields.Char('Mã kho', required=True)
    name = fields.Char('Tên kho', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    active = fields.Boolean(default=True)


class LfoodStockLot(models.Model):
    _name = 'lfood.stock.lot'
    _description = 'Lô hàng'
    _order = 'expiry_date, name'

    name = fields.Char('Số lô', required=True)
    product_id = fields.Many2one('lfood.product', 'Mặt hàng', required=True, index=True)
    production_date = fields.Date('Ngày sản xuất')
    expiry_date = fields.Date('Hạn dùng', index=True)
    qty_on_hand = fields.Float('Tồn', digits=(16, 3), compute='_compute_qty')
    days_left = fields.Integer('Còn hạn (ngày)', compute='_compute_qty')

    _lot_uniq = models.Constraint('unique(product_id, name)', 'Số lô đã tồn tại cho mặt hàng này.')

    def _compute_qty(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.qty_on_hand = rec.product_id._position(lot=rec)[0]
            rec.days_left = (rec.expiry_date - today).days if rec.expiry_date else 0


class LfoodStockValuation(models.Model):
    _name = 'lfood.stock.valuation'
    _description = 'Thẻ kho'
    _order = 'date, id'

    product_id = fields.Many2one('lfood.product', 'Mặt hàng', required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    warehouse_id = fields.Many2one('lfood.warehouse', 'Kho', required=True, index=True)
    lot_id = fields.Many2one('lfood.stock.lot', 'Lô', index=True)
    date = fields.Date('Ngày', required=True, index=True)
    picking_id = fields.Many2one('lfood.stock.picking', 'Phiếu', index=True, ondelete='restrict')
    qty = fields.Float('Số lượng (+ nhập, - xuất)', digits=(16, 3))
    value = fields.Float('Giá trị', digits=(16, 0))
    unit_cost = fields.Float('Đơn giá', digits=(16, 2), compute='_compute_unit_cost')

    def _compute_unit_cost(self):
        for rec in self:
            rec.unit_cost = rec.value / rec.qty if rec.qty else 0


class LfoodStockPicking(models.Model):
    _name = 'lfood.stock.picking'
    _description = 'Phiếu nhập, xuất kho'
    _order = 'date desc, id desc'

    name = fields.Char('Số phiếu', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    kind = fields.Selection([('in', 'Nhập kho'), ('out', 'Xuất kho'), ('transfer', 'Chuyển kho')], 'Loại', required=True, default='in')
    purpose = fields.Selection(PURPOSES, 'Nội dung', required=True, default='purchase')
    date = fields.Date('Ngày', required=True, default=fields.Date.context_today, index=True)
    warehouse_id = fields.Many2one('lfood.warehouse', 'Kho', required=True)
    dest_warehouse_id = fields.Many2one('lfood.warehouse', 'Kho nhận')
    partner_id = fields.Many2one('res.partner', 'Đối tượng')
    memo = fields.Char('Diễn giải')
    counterpart_account = fields.Char('TK đối ứng', compute='_compute_counterpart', store=True, readonly=False)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP')
    invoice_symbol = fields.Char('Ký hiệu hóa đơn')
    invoice_number = fields.Char('Số hóa đơn')
    invoice_date = fields.Date('Ngày hóa đơn')
    payment_method = fields.Selection([('cash', 'Tiền mặt'), ('bank', 'Chuyển khoản'), ('credit', 'Mua chịu')], 'Thanh toán', default='credit')
    sale_invoice_id = fields.Many2one('lfood.sale.invoice', 'Hóa đơn bán ra', index=True)
    line_ids = fields.One2many('lfood.stock.picking.line', 'picking_id', 'Hàng hóa', copy=True)
    amount = fields.Float('Giá trị hàng', digits=(16, 0), compute='_compute_amount', store=True)
    amount_tax = fields.Float('Thuế GTGT', digits=(16, 0), compute='_compute_amount', store=True)
    state = fields.Selection([('draft', 'Nháp'), ('done', 'Đã ghi'), ('cancel', 'Đã hủy')], 'Trạng thái', default='draft',
                             readonly=True, copy=False, index=True)
    done_by = fields.Many2one('res.users', 'Người ghi', readonly=True, copy=False)

    @api.depends('kind', 'purpose')
    def _compute_counterpart(self):
        for rec in self:
            rec.counterpart_account = DEFAULT_COUNTER.get((rec.kind, rec.purpose), rec.counterpart_account)

    @api.depends('line_ids.amount', 'line_ids.tax', 'line_ids.cost')
    def _compute_amount(self):
        for rec in self:
            rec.amount = sum(rec.line_ids.mapped('amount' if rec.kind == 'in' else 'cost'))
            rec.amount_tax = sum(rec.line_ids.mapped('tax'))

    def write(self, vals):
        if not self.env.context.get('lfood_stock_system'):
            if {'state', 'name', 'done_by'} & set(vals):
                raise UserError(_('Trạng thái phiếu kho chỉ đổi bằng nút Ghi phiếu, Hủy.'))
            if self.filtered(lambda p: p.state != 'draft'):
                raise UserError(_('Phiếu kho đã ghi không sửa được. Hủy phiếu rồi lập phiếu mới.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda p: p.state != 'draft'):
            raise UserError(_('Phiếu kho đã ghi không xóa được.'))
        return super().unlink()

    # ------------------------------------------------------------ ghi phiếu
    def _check_date_order(self, product):
        last = self.env['lfood.stock.valuation'].sudo().search([('product_id', '=', product.id)], order='date desc', limit=1)
        if last and self.date < last.date:
            raise UserError(_('Mặt hàng %s đã có phiếu ngày %s. Không ghi phiếu có ngày trước đó vì làm sai giá xuất kho bình quân.')
                            % (product.display_name, last.date.strftime('%d/%m/%Y')))

    def _lot_for(self, line):
        if not line.product_id.track_lot:
            return self.env['lfood.stock.lot']
        if line.lot_id:
            return line.lot_id
        if self.kind == 'in' and line.lot_name:
            Lot = self.env['lfood.stock.lot'].sudo()
            lot = Lot.search([('product_id', '=', line.product_id.id), ('name', '=', line.lot_name)], limit=1)
            return lot or Lot.create({'product_id': line.product_id.id, 'name': line.lot_name, 'expiry_date': line.expiry_date,
                                      'production_date': line.production_date})
        raise UserError(_('Mặt hàng %s theo dõi lô: chọn hoặc nhập số lô.') % line.product_id.display_name)

    def _fefo_lot_domain(self, line):
        """Điều kiện thêm khi chọn lô xuất tự động; phân hệ bán hàng thêm hạn dùng tối thiểu của khách."""
        return []

    def _fefo_split(self, line):
        """Xuất theo lô hết hạn trước; trả về [(lô, số lượng)]."""
        if not line.product_id.track_lot:
            return [(self.env['lfood.stock.lot'], line.quantity)]
        if line.lot_id:
            return [(line.lot_id, line.quantity)]
        need, out = line.quantity, []
        domain = [('product_id', '=', line.product_id.id)] + self._fefo_lot_domain(line)
        for lot in self.env['lfood.stock.lot'].sudo().search(domain, order='expiry_date, id'):
            avail = line.product_id._position(self.warehouse_id, lot)[0]
            if avail <= 0:
                continue
            take = min(avail, need)
            out.append((lot, take))
            need = round(need - take, 3)
            if need <= 0:
                break
        if need > 0:
            raise UserError(_('Kho %s không đủ %s để xuất: thiếu %s %s.') % (self.warehouse_id.name, line.product_id.display_name,
                                                                          need, line.product_id.uom))
        return out

    def action_done(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán, thủ kho được giao quyền kế toán mới ghi phiếu kho.'))
        Valuation = self.env['lfood.stock.valuation'].sudo()
        for rec in self.filtered(lambda p: p.state == 'draft'):
            if not rec.line_ids:
                raise UserError(_('Phiếu chưa có hàng hóa.'))
            if rec.kind == 'transfer' and (not rec.dest_warehouse_id or rec.dest_warehouse_id == rec.warehouse_id):
                raise UserError(_('Chọn kho nhận khác kho xuất.'))
            prefix = {'in': 'lfood.stock.in', 'out': 'lfood.stock.out', 'transfer': 'lfood.stock.transfer'}[rec.kind]
            name = self.env['ir.sequence'].with_company(rec.company_id).next_by_code(prefix) or '/'
            rec.with_context(lfood_stock_system=True).write({'name': name, 'state': 'done', 'done_by': self.env.uid})
            by_account = {}
            for line in rec.line_ids:
                product = line.product_id
                rec._check_date_order(product)
                if rec.kind == 'in':
                    lot = rec._lot_for(line)
                    value = line.amount
                    if rec.purpose in ('count', 'return_in') and not line.price_unit:
                        qty, val = product._position()
                        value = round(line.quantity * (val / qty)) if qty else 0
                        line.with_context(lfood_stock_system=True).write({'price_unit': value / line.quantity if line.quantity else 0})
                    Valuation.create({'product_id': product.id, 'company_id': rec.company_id.id, 'warehouse_id': rec.warehouse_id.id,
                                      'lot_id': lot.id, 'date': rec.date, 'picking_id': rec.id, 'qty': line.quantity, 'value': value})
                    line.with_context(lfood_stock_system=True).write({'cost': value, 'lot_id': lot.id})
                    acc = product._stock_account(rec.company_id)
                    by_account[acc] = by_account.get(acc, 0) + value
                else:
                    total_qty, total_value = product._position()
                    cost_total = 0
                    for lot, qty in rec._fefo_split(line):
                        if product._position(rec.warehouse_id, lot if product.track_lot else None)[0] < qty:
                            raise UserError(_('Kho %s không đủ %s để xuất.') % (rec.warehouse_id.name, product.display_name))
                        remaining_qty = round(total_qty - qty, 3)
                        cost = total_value if remaining_qty <= 0 else round(qty * total_value / total_qty)
                        total_qty, total_value = remaining_qty, total_value - cost
                        cost_total += cost
                        Valuation.create({'product_id': product.id, 'company_id': rec.company_id.id, 'warehouse_id': rec.warehouse_id.id,
                                          'lot_id': lot.id, 'date': rec.date, 'picking_id': rec.id, 'qty': -qty, 'value': -cost})
                        if rec.kind == 'transfer':
                            Valuation.create({'product_id': product.id, 'company_id': rec.company_id.id, 'warehouse_id': rec.dest_warehouse_id.id,
                                              'lot_id': lot.id, 'date': rec.date, 'picking_id': rec.id, 'qty': qty, 'value': cost})
                            total_qty, total_value = total_qty + qty, total_value + cost
                    line.with_context(lfood_stock_system=True).write({'cost': cost_total})
                    acc = product._stock_account(rec.company_id)
                    by_account[acc] = by_account.get(acc, 0) + cost_total
            rec._post_move(by_account)
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=name, company_id=rec.company_id.id,
                                                      summary=_('Ghi %s %s (%s), giá trị %s') % (dict(self._fields['kind'].selection)[rec.kind].lower(),
                                                                                              name, dict(rec._fields['purpose'].selection)[rec.purpose], vnd(rec.amount)))
        return True

    def _cost_extra(self):
        """Giá trị bổ sung cho dòng chi phí, ví dụ đối tượng tính giá thành; phân hệ giá thành ghi đè."""
        return None

    def _post_move(self, by_account):
        # chuyển kho không đổi tài khoản; tồn đầu kỳ đã có số dư trên sổ qua Số dư đầu kỳ nên không ghi sổ lại
        if self.kind == 'transfer' or self.purpose == 'opening':
            return
        Acc = self.env['lfood.account']
        counter = self.counterpart_account
        partner = self.partner_id if Acc.by_code(counter).track_partner else None
        label = '%s %s' % (self.name, self.memo or dict(self._fields['purpose'].selection)[self.purpose])
        lines = []
        for account, value in by_account.items():
            if self.kind == 'in':
                lines += [(account, value, 0, None, label, None), (counter, 0, value, partner, label, None)]
            else:
                lines += [(counter, value, 0, partner, label, self.cost_item_id, self._cost_extra()),
                          (account, 0, value, None, label, None)]
        if self.kind == 'in' and self.amount_tax:
            lines += [('1331', self.amount_tax, 0, None, _('Thuế GTGT %s') % label, None), (counter, 0, self.amount_tax, partner, label, None)]
        if self.kind == 'out' and self.purpose == 'return_out' and self.amount_tax:
            lines += [(counter, self.amount_tax, 0, partner, label, None), ('1331', 0, self.amount_tax, None, _('Thuế GTGT %s') % label, None)]
        journal = 'purchase' if self.purpose in ('purchase', 'return_out') else 'stock'
        self.env['lfood.move']._create_from_source(self, journal, self.date, lines, memo=label, ref=self.invoice_number or self.name)

    def action_cancel(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được hủy phiếu kho đã ghi.'))
        Valuation = self.env['lfood.stock.valuation'].sudo()
        for rec in self.filtered(lambda p: p.state == 'done'):
            layers = Valuation.search([('picking_id', '=', rec.id)])
            later = Valuation.search([('product_id', 'in', layers.product_id.ids), ('id', '>', max(layers.ids)),
                                      ('picking_id', '!=', rec.id)], limit=1)
            if later:
                raise UserError(_('%s đã có phiếu %s ghi sau. Hủy từ phiếu mới nhất trở về để giá bình quân không sai.')
                                % (later.product_id.display_name, later.picking_id.name))
            layers.unlink()
            self.env['lfood.move']._active_for(rec)._reverse(memo=_('Hủy phiếu %s') % rec.name)
            rec.with_context(lfood_stock_system=True).write({'state': 'cancel'})
            for p in layers.product_id:
                if p._position()[0] < 0:
                    raise UserError(_('Hủy phiếu làm tồn kho %s âm.') % p.display_name)
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=rec.name,
                                                      company_id=rec.company_id.id, summary=_('Hủy phiếu kho %s') % rec.name)
        return True

    def action_view_moves(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Bút toán'), 'res_model': 'lfood.move', 'view_mode': 'list,form',
                'domain': [('source_model', '=', self._name), ('source_id', '=', self.id)]}


class LfoodStockPickingLine(models.Model):
    _name = 'lfood.stock.picking.line'
    _description = 'Dòng phiếu kho'

    picking_id = fields.Many2one('lfood.stock.picking', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='picking_id.company_id', store=True)
    product_id = fields.Many2one('lfood.product', 'Mặt hàng', required=True)
    uom = fields.Char(related='product_id.uom')
    lot_id = fields.Many2one('lfood.stock.lot', 'Lô', domain="[('product_id', '=', product_id)]")
    lot_name = fields.Char('Số lô mới')
    production_date = fields.Date('Ngày sản xuất')
    expiry_date = fields.Date('Hạn dùng')
    quantity = fields.Float('Số lượng', digits=(16, 3), required=True, default=1)
    price_unit = fields.Float('Đơn giá nhập', digits=(16, 2))
    amount = fields.Float('Thành tiền', digits=(16, 0), compute='_compute_amount', store=True, readonly=False)
    vat_rate_id = fields.Many2one('lfood.vat.rate', 'Thuế suất')
    tax = fields.Float('Tiền thuế', digits=(16, 0), compute='_compute_tax', store=True, readonly=False)
    cost = fields.Float('Giá vốn xuất', digits=(16, 0), readonly=True)

    @api.depends('quantity', 'price_unit')
    def _compute_amount(self):
        for rec in self:
            rec.amount = round(rec.quantity * rec.price_unit)

    @api.depends('amount', 'vat_rate_id')
    def _compute_tax(self):
        for rec in self:
            rec.tax = round(rec.amount * (rec.vat_rate_id.rate or 0) / 100)

    @api.constrains('quantity')
    def _check_qty(self):
        for rec in self:
            if rec.quantity <= 0:
                raise UserError(_('Số lượng phải lớn hơn 0.'))

    def write(self, vals):
        if not self.env.context.get('lfood_stock_system') and self.filtered(lambda l: l.picking_id.state != 'draft'):
            raise UserError(_('Phiếu kho đã ghi không sửa được.'))
        return super().write(vals)
