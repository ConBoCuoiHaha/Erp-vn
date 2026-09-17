"""Điều chỉnh giá nhập kho: chi phí mua hàng và giảm giá, chiết khấu hàng mua.

Căn cứ: giá gốc hàng tồn kho gồm giá mua và chi phí thu mua (vận chuyển, bốc xếp, lưu kho,
bảo hiểm hàng...); chi phí thu mua liên quan nhiều loại hàng thì phân bổ theo tiêu thức thích hợp
và áp dụng nhất quán. Chiết khấu thương mại, giảm giá hàng mua ghi giảm giá gốc hàng tồn kho
(Chuẩn mực kế toán Việt Nam số 02 Hàng tồn kho; nguyên tắc kế toán hàng tồn kho tại Thông tư
99/2025/TT-BTC).

Cách làm: chứng từ này không tạo nhập xuất mới, chỉ ghi thêm một lớp giá trị (số lượng 0,
giá trị + hoặc −) lên thẻ kho của từng dòng hàng của phiếu nhập gốc, nên giá bình quân
đổi theo đúng phần điều chỉnh; đồng thời ghi bút toán tương ứng.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import allocate, vnd

KINDS = [('landed', 'Chi phí mua hàng'), ('rebate', 'Giảm giá, chiết khấu hàng mua')]
METHODS = [('value', 'Theo giá trị hàng'), ('qty', 'Theo số lượng')]


class LfoodPurchaseAdjust(models.Model):
    _name = 'lfood.purchase.adjust'
    _description = 'Điều chỉnh giá nhập kho'
    _order = 'date desc, id desc'

    name = fields.Char('Số chứng từ', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    kind = fields.Selection(KINDS, 'Loại', required=True, default='landed')
    date = fields.Date('Ngày', required=True, default=fields.Date.context_today, index=True)
    picking_id = fields.Many2one('lfood.stock.picking', 'Phiếu nhập kho', required=True, index=True,
                                 domain="[('kind', '=', 'in'), ('state', '=', 'done')]")
    partner_id = fields.Many2one('res.partner', 'Đối tượng', required=True,
                                 help='Nhà cung cấp dịch vụ vận chuyển, bốc xếp hoặc nhà cung cấp hàng giảm giá')
    memo = fields.Char('Diễn giải')
    invoice_number = fields.Char('Số hóa đơn')
    method = fields.Selection(METHODS, 'Tiêu thức phân bổ', required=True, default='value')
    amount = fields.Float('Số tiền chưa thuế', digits=(16, 0), required=True)
    vat_rate_id = fields.Many2one('lfood.vat.rate', 'Thuế suất')
    tax = fields.Float('Tiền thuế GTGT', digits=(16, 0), compute='_compute_tax', store=True, readonly=False)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP')
    line_ids = fields.One2many('lfood.purchase.adjust.line', 'adjust_id', 'Phân bổ', readonly=True)
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)

    @api.depends('amount', 'vat_rate_id')
    def _compute_tax(self):
        for rec in self:
            rec.tax = round(rec.amount * (rec.vat_rate_id.rate or 0) / 100)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.purchase.adjust') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_purchase_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái chứng từ chỉ đổi bằng nút Ghi sổ, Hủy.'))
            if self.filtered(lambda r: r.state != 'draft'):
                raise UserError(_('Chứng từ đã ghi sổ không sửa được. Hủy chứng từ rồi lập chứng từ mới.'))
        return super().write(vals)

    def _allocation(self):
        """Trả về [(dòng phiếu nhập, số tiền phân bổ)], tổng đúng bằng số tiền chứng từ."""
        self.ensure_one()
        lines = self.picking_id.line_ids
        if not lines:
            raise UserError(_('Phiếu nhập %s không có dòng hàng nào.') % self.picking_id.name)
        weights = [l.amount if self.method == 'value' else l.quantity for l in lines]
        return list(zip(lines, allocate(self.amount, weights)))

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán mới ghi sổ chứng từ này.'))
        Valuation = self.env['lfood.stock.valuation'].sudo()
        Line = self.env['lfood.purchase.adjust.line'].sudo()
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ ghi sổ chứng từ đang ở trạng thái Nháp.'))
            if rec.picking_id.state != 'done' or rec.picking_id.kind != 'in':
                raise UserError(_('Chỉ điều chỉnh giá nhập của phiếu nhập kho đã ghi.'))
            if rec.date < rec.picking_id.date:
                raise UserError(_('Ngày chứng từ không được trước ngày phiếu nhập %s.')
                                % rec.picking_id.date.strftime('%d/%m/%Y'))
            if rec.amount <= 0:
                raise UserError(_('Số tiền phải lớn hơn 0.'))
            sign = 1 if rec.kind == 'landed' else -1
            by_account = {}
            rec.line_ids.sudo().unlink()
            for pick_line, part in rec._allocation():
                if not part:
                    continue
                product = pick_line.product_id
                Valuation.create({
                    'product_id': product.id, 'company_id': rec.company_id.id,
                    'warehouse_id': rec.picking_id.warehouse_id.id, 'lot_id': pick_line.lot_id.id,
                    'date': rec.date, 'picking_id': rec.picking_id.id, 'qty': 0, 'value': sign * part})
                Line.create({'adjust_id': rec.id, 'product_id': product.id, 'lot_id': pick_line.lot_id.id,
                             'quantity': pick_line.quantity, 'base': pick_line.amount if rec.method == 'value' else pick_line.quantity,
                             'amount': sign * part})
                acc = product._stock_account(rec.company_id)
                by_account[acc] = by_account.get(acc, 0) + part
            rec._post_move(by_account, sign)
            rec.with_context(lfood_purchase_system=True).write({'state': 'posted'})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Ghi sổ %s %s cho phiếu %s, số tiền %s')
                        % (dict(KINDS)[rec.kind].lower(), rec.name, rec.picking_id.name, vnd(rec.amount)))
        return True

    def _post_move(self, by_account, sign):
        """landed: Nợ 152, 156..., Nợ 1331 / Có 3311. rebate: Nợ 3311 / Có 152, 156..., Có 1331."""
        self.ensure_one()
        label = '%s %s' % (self.name, self.memo or dict(KINDS)[self.kind])
        lines = []
        for account, value in by_account.items():
            if sign > 0:
                lines += [(account, value, 0, None, label, self.cost_item_id),
                          ('3311', 0, value, self.partner_id, label, None)]
            else:
                lines += [('3311', value, 0, self.partner_id, label, None),
                          (account, 0, value, None, label, self.cost_item_id)]
        if self.tax:
            if sign > 0:
                lines += [('1331', self.tax, 0, None, _('Thuế GTGT %s') % label, None),
                          ('3311', 0, self.tax, self.partner_id, label, None)]
            else:
                lines += [('3311', self.tax, 0, self.partner_id, label, None),
                          ('1331', 0, self.tax, None, _('Thuế GTGT %s') % label, None)]
        self.env['lfood.move']._create_from_source(self, 'purchase', self.date, lines, memo=label,
                                                   ref=self.invoice_number or self.name)

    def action_cancel(self):
        """Hủy: đảo bút toán và ghi lớp giá trị ngược lại, không xóa dấu vết."""
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được hủy chứng từ đã ghi sổ.'))
        Valuation = self.env['lfood.stock.valuation'].sudo()
        for rec in self.filtered(lambda r: r.state == 'posted'):
            move = self.env['lfood.move']._active_for(rec)
            if move:
                move._reverse(memo=_('Hủy %s') % rec.name)
            for line in rec.line_ids:
                Valuation.create({'product_id': line.product_id.id, 'company_id': rec.company_id.id,
                                  'warehouse_id': rec.picking_id.warehouse_id.id, 'lot_id': line.lot_id.id,
                                  'date': fields.Date.context_today(rec), 'picking_id': rec.picking_id.id,
                                  'qty': 0, 'value': -line.amount})
            rec.with_context(lfood_purchase_system=True).write({'state': 'cancel'})
        return True


class LfoodPurchaseAdjustLine(models.Model):
    _name = 'lfood.purchase.adjust.line'
    _description = 'Dòng phân bổ điều chỉnh giá nhập'

    adjust_id = fields.Many2one('lfood.purchase.adjust', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='adjust_id.company_id', store=True)
    product_id = fields.Many2one('lfood.product', 'Mặt hàng', required=True)
    lot_id = fields.Many2one('lfood.stock.lot', 'Lô')
    quantity = fields.Float('Số lượng nhập', digits=(16, 3))
    base = fields.Float('Tiêu thức phân bổ', digits=(16, 3))
    amount = fields.Float('Số tiền phân bổ', digits=(16, 0))
