"""Chương trình khuyến mại (BH05, BH11) theo Luật Thương mại 2005, Nghị định 81/2018/NĐ-CP đã sửa bởi
Nghị định 128/2024/NĐ-CP và Nghị định 239/2026/NĐ-CP.

- Tặng hàng kèm mua (Điều 9 khoản 1): giá trị hàng tặng cho một đơn vị hàng được khuyến mại không quá 50% giá bán
  ngay trước khuyến mại (Điều 6 khoản 1); thông báo Sở Công Thương ít nhất 3 ngày làm việc trước khi thực hiện.
  Hàng tặng ghi trên hóa đơn với thành tiền 0 (giá tính thuế GTGT bằng 0, Nghị định 181/2025/NĐ-CP Điều 6 khoản 2),
  xuất kho cùng hàng bán nên giá vốn vào 632 (Thông tư 99/2025/TT-BTC: khuyến mại kèm điều kiện mua hàng).
- Giảm giá (Điều 10): mức giảm không quá 50% giá bán ngay trước khuyến mại (Điều 7); không phải thông báo.
  Giá tính thuế là giá đã giảm.
- Tặng hàng không kèm mua, hàng mẫu (Điều 8, Điều 9 khoản 2): không áp hạn mức, không phải thông báo;
  xuất kho ghi Nợ 6418 / Có 155, 156 (chi phí bán hàng).
Các hình thức may rủi, phiếu mua hàng, khách hàng thường xuyên chưa làm.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .promo_calc import gift_ratio, gift_quantity

KINDS = [('gift', 'Tặng hàng kèm mua'), ('discount', 'Giảm giá'),
         ('free_gift', 'Tặng hàng không kèm mua'), ('sample', 'Hàng mẫu dùng thử')]
NOTICE_KINDS = ('gift',)
ISSUE_KINDS = ('free_gift', 'sample')
PROMO_ACCOUNT = '6418'


class LfoodPromotion(models.Model):
    _name = 'lfood.promotion'
    _description = 'Chương trình khuyến mại'
    _order = 'date_from desc, id desc'

    name = fields.Char('Số chương trình', default='/', readonly=True, copy=False, index=True)
    title = fields.Char('Tên chương trình', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    kind = fields.Selection(KINDS, 'Hình thức', required=True, default='gift')
    channel_id = fields.Many2one('lfood.sale.channel', 'Chỉ áp dụng cho kênh')
    date_from = fields.Date('Từ ngày', required=True)
    date_to = fields.Date('Đến ngày', required=True)
    needs_notice = fields.Boolean('Phải thông báo Sở Công Thương', compute='_compute_needs_notice')
    notice_ref = fields.Char('Số hồ sơ thông báo')
    notice_date = fields.Date('Ngày nộp thông báo')
    line_ids = fields.One2many('lfood.promotion.line', 'promotion_id', 'Nội dung', copy=True)
    state = fields.Selection([('draft', 'Nháp'), ('active', 'Đang áp dụng'), ('closed', 'Đã kết thúc')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)
    picking_ids = fields.One2many('lfood.stock.picking', 'promotion_id', 'Phiếu xuất khuyến mại')

    @api.depends('kind')
    def _compute_needs_notice(self):
        for rec in self:
            rec.needs_notice = rec.kind in NOTICE_KINDS

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_to < rec.date_from:
                raise ValidationError(_('Ngày kết thúc phải sau ngày bắt đầu.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.promotion') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_promo_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái chương trình chỉ đổi bằng nút Áp dụng, Kết thúc.'))
            if self.filtered(lambda r: r.state != 'draft') and set(vals) - {'notice_ref'}:
                raise UserError(_('Chương trình đã áp dụng không sửa được. Kết thúc rồi lập chương trình mới.'))
        return super().write(vals)

    def _param(self, code, default):
        return self.env['lfood.legal.param'].get_value(code, self.date_from, default)

    def _check_rules(self):
        """Danh sách lỗi so với quy định; rỗng là hợp lệ."""
        self.ensure_one()
        errors = []
        if not self.line_ids:
            errors.append(_('Chưa có hàng hóa áp dụng.'))
        if self.kind in NOTICE_KINDS:
            need = int(self._param('KM_NGAY_THONG_BAO', 3))
            if not (self.notice_ref and self.notice_date):
                errors.append(_('Nhập số hồ sơ và ngày nộp thông báo khuyến mại cho Sở Công Thương.'))
            elif self.env['lfood.holiday'].working_days_between(self.notice_date, self.date_from) < need:
                errors.append(_('Thông báo phải nộp trước ngày bắt đầu ít nhất %s ngày làm việc.') % need)
        limit = self._param('KM_HAN_MUC_GIA_TRI', 50)
        for line in self.line_ids:
            label = line.product_id.display_name
            if self.kind == 'gift':
                if not (line.buy_qty > 0 and line.gift_qty > 0 and line.gift_product_id):
                    errors.append(_('%s: nhập số lượng mua, hàng tặng và số lượng tặng.') % label)
                elif not (line.price_before and line.gift_price_before):
                    errors.append(_('%s: nhập giá bán ngay trước khuyến mại của hàng mua và hàng tặng.') % label)
                elif line.ratio > limit:
                    errors.append(_('%s: hàng tặng bằng %s%% giá bán một đơn vị, vượt hạn mức %s%%.')
                                  % (label, line.ratio, limit))
            elif self.kind == 'discount':
                if not 0 < line.discount <= limit:
                    errors.append(_('%s: mức giảm %s%% phải lớn hơn 0 và không quá %s%%.') % (label, line.discount, limit))
        return errors

    def action_activate(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ áp dụng chương trình ở trạng thái Nháp.'))
            errors = rec._check_rules()
            if errors:
                raise UserError('\n'.join(errors))
            rec.with_context(lfood_promo_system=True).write({'state': 'active'})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Áp dụng chương trình khuyến mại %s (%s) từ %s đến %s') % (
                    rec.title, dict(KINDS)[rec.kind], rec.date_from.strftime('%d/%m/%Y'), rec.date_to.strftime('%d/%m/%Y')))
        return True

    def action_close(self):
        self.filtered(lambda r: r.state == 'active').with_context(lfood_promo_system=True).write({'state': 'closed'})
        return True

    def action_issue(self):
        """Mở phiếu xuất kho hàng tặng không kèm mua hoặc hàng mẫu."""
        self.ensure_one()
        if self.kind not in ISSUE_KINDS or self.state != 'active':
            raise UserError(_('Chỉ xuất kho cho chương trình tặng không kèm mua, hàng mẫu đang áp dụng.'))
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.stock.picking', 'view_mode': 'form',
                'context': {'default_kind': 'out', 'default_purpose': 'promotion', 'default_promotion_id': self.id,
                            'default_company_id': self.company_id.id,
                            'default_memo': _('Khuyến mại %s') % self.title,
                            'default_line_ids': [(0, 0, {'product_id': l.product_id.id, 'quantity': l.gift_qty or 1})
                                                 for l in self.line_ids]}}

    @api.model
    def _active_for(self, order):
        return self.search([('state', '=', 'active'), ('company_id', '=', order.company_id.id),
                            ('date_from', '<=', order.date), ('date_to', '>=', order.date),
                            ('kind', 'in', ('gift', 'discount')),
                            '|', ('channel_id', '=', False), ('channel_id', '=', order.channel_id.id)])


class LfoodPromotionLine(models.Model):
    _name = 'lfood.promotion.line'
    _description = 'Hàng hóa khuyến mại'

    promotion_id = fields.Many2one('lfood.promotion', required=True, ondelete='cascade', index=True)
    kind = fields.Selection(related='promotion_id.kind')
    product_id = fields.Many2one('lfood.product', 'Hàng hóa', required=True,
                                 help='Hàng được khuyến mại; với tặng không kèm mua, hàng mẫu là hàng đem tặng')
    price_before = fields.Float('Giá bán ngay trước khuyến mại', digits=(16, 2))
    buy_qty = fields.Float('Mua đủ', digits=(16, 3))
    gift_product_id = fields.Many2one('lfood.product', 'Hàng tặng')
    gift_price_before = fields.Float('Giá bán hàng tặng', digits=(16, 2))
    gift_qty = fields.Float('Số lượng tặng', digits=(16, 3))
    discount = fields.Float('Mức giảm (%)', digits=(6, 2))
    ratio = fields.Float('Giá trị tặng / giá một đơn vị (%)', digits=(6, 2), compute='_compute_ratio', store=True)

    @api.depends('buy_qty', 'price_before', 'gift_qty', 'gift_price_before')
    def _compute_ratio(self):
        for rec in self:
            rec.ratio = gift_ratio(rec.buy_qty, rec.price_before, rec.gift_qty, rec.gift_price_before)


class LfoodSaleOrder(models.Model):
    _inherit = 'lfood.sale.order'

    def action_apply_promotions(self):
        """Áp giảm giá và thêm hàng tặng theo chương trình đang áp dụng; bấm lại sẽ tính lại từ đầu."""
        for order in self:
            if order.state != 'draft':
                raise UserError(_('Chỉ áp khuyến mại cho báo giá.'))
            order.line_ids.filtered('is_promo_gift').unlink()
            order.line_ids.filtered('promotion_id').write({'promotion_id': False, 'discount': 0})
            if order.pricelist_id:
                order.action_apply_prices()
            new_lines = []
            for promo in self.env['lfood.promotion']._active_for(order):
                for rule in promo.line_ids:
                    for line in order.line_ids.filtered(lambda l: l.product_id == rule.product_id and not l.is_promo_gift):
                        if promo.kind == 'discount':
                            line.write({'discount': rule.discount, 'promotion_id': promo.id})
                            continue
                        qty = gift_quantity(line.quantity, rule.buy_qty, rule.gift_qty)
                        if qty:
                            gift = rule.gift_product_id
                            new_lines.append((0, 0, {
                                'product_id': gift.id, 'quantity': qty, 'price_unit': 0, 'is_promo_gift': True,
                                'promotion_id': promo.id, 'vat_rate_id': (gift.vat_rate_id or line.vat_rate_id).id}))
            if new_lines:
                order.write({'line_ids': new_lines})
        return True

    def action_create_invoice(self):
        res = super().action_create_invoice()
        invoice = self.env['lfood.sale.invoice'].browse(res['res_id'])
        for line in invoice.line_ids.filtered(lambda l: l.sale_order_line_id.is_promo_gift):
            line.name = _('%s (hàng khuyến mại, không thu tiền - %s)') % (
                line.name, line.sale_order_line_id.promotion_id.name)
        return res


class LfoodSaleOrderLine(models.Model):
    _inherit = 'lfood.sale.order.line'

    promotion_id = fields.Many2one('lfood.promotion', 'Chương trình khuyến mại', readonly=True)
    is_promo_gift = fields.Boolean('Hàng tặng', readonly=True)

    @api.constrains('is_promo_gift', 'price_unit')
    def _check_gift_price(self):
        for rec in self:
            if rec.is_promo_gift and rec.price_unit:
                raise ValidationError(_('Hàng tặng khuyến mại không thu tiền, đơn giá phải bằng 0.'))


class LfoodStockPicking(models.Model):
    _inherit = 'lfood.stock.picking'

    purpose = fields.Selection(selection_add=[('promotion', 'Xuất khuyến mại, hàng mẫu')],
                               ondelete={'promotion': lambda recs: recs.write({'purpose': 'internal'})})
    promotion_id = fields.Many2one('lfood.promotion', 'Chương trình khuyến mại', index=True,
                                   domain="[('kind', 'in', ('free_gift', 'sample')), ('state', '=', 'active')]")

    @api.depends('kind', 'purpose')
    def _compute_counterpart(self):
        super()._compute_counterpart()
        for rec in self.filtered(lambda r: r.purpose == 'promotion'):
            rec.counterpart_account = PROMO_ACCOUNT

    def action_done(self):
        for rec in self.filtered(lambda r: r.state == 'draft' and r.purpose == 'promotion'):
            promo = rec.promotion_id
            if rec.kind != 'out' or not promo or promo.kind not in ISSUE_KINDS:
                raise UserError(_('Phiếu xuất khuyến mại phải chọn chương trình tặng không kèm mua hoặc hàng mẫu.'))
            if promo.state != 'active' or not promo.date_from <= rec.date <= promo.date_to:
                raise UserError(_('Ngày xuất ngoài thời gian áp dụng của chương trình %s.') % promo.name)
        return super().action_done()
