from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LfoodServiceVoucherLine(models.Model):
    _name = 'lfood.service.voucher.line'
    _description = 'Dòng hạch toán chứng từ mua dịch vụ'
    _order = 'version_id, sequence, id'

    voucher_id = fields.Many2one('lfood.service.voucher', 'Chứng từ', required=True, ondelete='cascade', index=True)
    version_id = fields.Many2one('lfood.service.voucher.version', 'Phiên bản', ondelete='cascade', index=True)
    company_id = fields.Many2one(related='voucher_id.company_id', store=True)
    is_current = fields.Boolean('Thuộc phiên bản hiện hành', compute='_compute_is_current', store=True, index=True)
    origin_line_id = fields.Many2one('lfood.service.voucher.line', 'Dòng gốc lúc mua vào', index=True, copy=False)
    sequence = fields.Integer(default=10)

    service_code = fields.Char('Mã dịch vụ')
    name = fields.Char('Tên dịch vụ', required=True)
    acc_expense = fields.Char('TK chi phí', default='6277')
    acc_payable = fields.Char('TK công nợ', default='3311')
    uom = fields.Char('ĐVT')
    quantity = fields.Float('Số lượng', digits=(16, 5), default=1.0)
    price_unit = fields.Float('Đơn giá', digits=(16, 2))
    amount = fields.Float('Thành tiền', digits=(16, 0))
    vat_rate_id = fields.Many2one('lfood.vat.rate', 'Thuế suất')
    vat_amount = fields.Float('Tiền thuế', digits=(16, 0), compute='_compute_vat', store=True)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP', index=True)
    locked = fields.Boolean('Khóa', help='Dòng khóa giữ nguyên số tiền khi phân bổ lại tổng')

    @api.depends('version_id', 'voucher_id.current_version_id')
    def _compute_is_current(self):
        for rec in self:
            rec.is_current = bool(rec.version_id) and rec.version_id == rec.voucher_id.current_version_id

    @api.depends('amount', 'vat_rate_id.rate')
    def _compute_vat(self):
        for rec in self:
            rec.vat_amount = round((rec.amount or 0) * (rec.vat_rate_id.rate or 0) / 100)

    # ------------------------------------------------------------ tự tính trên màn hình
    @api.onchange('quantity', 'price_unit')
    def _onchange_qty_price(self):
        for rec in self:
            rec.amount = round((rec.quantity or 0) * (rec.price_unit or 0))

    @api.onchange('amount')
    def _onchange_amount(self):
        for rec in self:
            if rec.quantity and round(rec.quantity * rec.price_unit) != round(rec.amount or 0):
                rec.price_unit = round((rec.amount or 0) / rec.quantity, 2)

    # ------------------------------------------------------------ bảo vệ phiên bản đã lưu
    def _check_editable(self):
        if self.env.context.get('lfood_version_system'):
            return
        for rec in self:
            if rec.version_id.state == 'saved':
                raise UserError(_('Chứng từ %s đã cất. Bấm Sửa để tạo phiên bản mới rồi mới sửa được.') % rec.voucher_id.name)

    @api.model_create_multi
    def create(self, vals_list):
        Voucher = self.env['lfood.service.voucher']
        for vals in vals_list:
            if not vals.get('version_id') and vals.get('voucher_id'):
                vals['version_id'] = Voucher.browse(vals['voucher_id']).current_version_id.id
            if 'amount' not in vals and ('quantity' in vals or 'price_unit' in vals):
                vals['amount'] = round((vals.get('quantity', 1) or 0) * (vals.get('price_unit') or 0))
        lines = super().create(vals_list)
        lines._check_editable()
        return lines

    def write(self, vals):
        self._check_editable()
        if 'amount' not in vals and ('quantity' in vals or 'price_unit' in vals):
            for rec in self:
                q = vals.get('quantity', rec.quantity)
                p = vals.get('price_unit', rec.price_unit)
                super(LfoodServiceVoucherLine, rec).write(dict(vals, amount=round((q or 0) * (p or 0))))
            return True
        if 'amount' in vals and 'price_unit' not in vals:
            for rec in self:
                q = vals.get('quantity', rec.quantity)
                extra = {'price_unit': round(vals['amount'] / q, 2)} if q else {}
                super(LfoodServiceVoucherLine, rec).write(dict(vals, **extra))
            return True
        return super().write(vals)

    def unlink(self):
        self._check_editable()
        return super().unlink()
