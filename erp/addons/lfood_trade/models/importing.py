"""Mua hàng nhập khẩu (MH12).

Tờ khai hải quan nhập khẩu: trị giá tính thuế (nguyên tệ x tỷ giá tính thuế), thuế nhập khẩu theo thuế suất từng dòng,
thuế GTGT hàng nhập khẩu tính trên trị giá cộng thuế nhập khẩu. Chi phí nhập khẩu (vận chuyển, bảo hiểm, phí thông quan)
phân bổ theo trị giá vào giá nhập kho. Ghi sổ:
- phiếu nhập kho theo giá vốn (trị giá + thuế nhập khẩu + chi phí): Nợ 152, 156 / Có 3388 (tài khoản trung gian);
- tờ khai: Nợ 3388 / Có 3311 người bán nước ngoài (có số nguyên tệ để đánh giá lại tỷ giá), Có 3333 thuế nhập khẩu,
  Có 3311 đơn vị cung cấp dịch vụ; thuế GTGT: Nợ 1331 / Có 33312 (Thông tư 99/2025/TT-BTC).
Thuế GTGT hàng nhập khẩu được khấu trừ khi có chứng từ nộp thuế ở khâu nhập khẩu (Luật Thuế GTGT, Điều 14 khoản 2 điểm a):
bảng kê mua vào chỉ đánh dấu được khấu trừ khi đã nhập số chứng từ nộp thuế. Nộp thuế bằng phiếu chi (Nợ 3333, 33312).
Mặt hàng cần kiểm tra chất lượng thì lô nhập khẩu cũng bị cách ly chờ kiểm tra như hàng mua trong nước.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_quality.models import qc as _qc
from odoo.addons.lfood_voucher.models.tools import allocate, vnd

# ponytail: bổ sung vào bảng dùng chung của phân hệ chất lượng khi nạp mã; nhiều cơ sở dữ liệu thì chuyển thành móc
_qc.QC_STAGES.setdefault('import', 'incoming')


class LfoodStockPicking(models.Model):
    _inherit = 'lfood.stock.picking'

    purpose = fields.Selection(selection_add=[('import', 'Nhập khẩu')], ondelete={'import': 'set default'})
    import_id = fields.Many2one('lfood.import.declaration', 'Tờ khai nhập khẩu', readonly=True, index=True)


class LfoodImportDeclaration(models.Model):
    _name = 'lfood.import.declaration'
    _description = 'Tờ khai nhập khẩu'
    _order = 'date desc, id desc'

    name = fields.Char('Số tờ khai', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    date = fields.Date('Ngày đăng ký tờ khai', required=True)
    partner_id = fields.Many2one('res.partner', 'Người bán nước ngoài', required=True)
    commercial_invoice = fields.Char('Hóa đơn thương mại')
    currency_id = fields.Many2one('res.currency', 'Nguyên tệ', required=True)
    rate = fields.Float('Tỷ giá tính thuế', digits=(16, 2), required=True)
    warehouse_id = fields.Many2one('lfood.warehouse', 'Nhập vào kho', required=True)
    line_ids = fields.One2many('lfood.import.line', 'declaration_id', 'Hàng nhập khẩu')
    cost_ids = fields.One2many('lfood.import.cost', 'declaration_id', 'Chi phí nhập khẩu')
    value_total = fields.Float('Trị giá tính thuế', digits=(16, 0), compute='_compute_totals', store=True)
    duty_total = fields.Float('Thuế nhập khẩu', digits=(16, 0), compute='_compute_totals', store=True)
    vat_total = fields.Float('Thuế GTGT hàng nhập khẩu', digits=(16, 0), compute='_compute_totals', store=True)
    cost_total = fields.Float('Chi phí nhập khẩu', digits=(16, 0), compute='_compute_totals', store=True)
    landed_total = fields.Float('Giá nhập kho', digits=(16, 0), compute='_compute_totals', store=True)
    tax_paid_ref = fields.Char('Số chứng từ nộp thuế', help='Có số chứng từ nộp thuế thì thuế GTGT nhập khẩu được khấu trừ')
    tax_paid_date = fields.Date('Ngày nộp thuế')
    document = fields.Binary('Tờ khai (bản điện tử)', attachment=True)
    document_name = fields.Char()
    picking_id = fields.Many2one('lfood.stock.picking', 'Phiếu nhập kho', readonly=True, copy=False)
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False)

    _uniq = models.Constraint('unique(company_id, name)', 'Số tờ khai đã được ghi nhận.')

    @api.depends('line_ids.value', 'line_ids.duty', 'line_ids.vat', 'cost_ids.amount')
    def _compute_totals(self):
        for rec in self:
            rec.value_total = sum(rec.line_ids.mapped('value'))
            rec.duty_total = sum(rec.line_ids.mapped('duty'))
            rec.vat_total = sum(rec.line_ids.mapped('vat'))
            rec.cost_total = sum(rec.cost_ids.mapped('amount'))
            rec.landed_total = rec.value_total + rec.duty_total + rec.cost_total

    def write(self, vals):
        if self.filtered(lambda r: r.state != 'draft') and set(vals) - {'tax_paid_ref', 'tax_paid_date', 'document', 'document_name'} \
                and not self.env.context.get('lfood_trade_system'):
            raise UserError(_('Tờ khai đã ghi sổ không sửa được.'))
        return super().write(vals)

    def _landed_units(self):
        """{dòng: giá vốn đơn vị} sau khi phân bổ chi phí theo trị giá."""
        shares = allocate(self.cost_total, self.line_ids.mapped('value'))
        return {l: (l.value + l.duty + share) / l.quantity for l, share in zip(self.line_ids, shares)}

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được ghi sổ tờ khai.'))
        Move = self.env['lfood.move']
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.line_ids or any(l.quantity <= 0 or l.value <= 0 for l in rec.line_ids):
                raise UserError(_('Tờ khai chưa có hàng hoặc có dòng số lượng, trị giá bằng 0.'))
            units = rec._landed_units()
            picking = self.env['lfood.stock.picking'].create({
                'company_id': rec.company_id.id, 'kind': 'in', 'purpose': 'import', 'date': rec.date,
                'warehouse_id': rec.warehouse_id.id, 'partner_id': rec.partner_id.id, 'counterpart_account': '3388',
                'memo': _('Nhập khẩu theo tờ khai %s') % rec.name, 'import_id': rec.id,
                'line_ids': [(0, 0, {'product_id': l.product_id.id, 'quantity': l.quantity, 'price_unit': round(units[l], 2),
                                     'lot_name': l.lot_name, 'production_date': l.production_date,
                                     'expiry_date': l.expiry_date}) for l in rec.line_ids]})
            picking.action_done()
            label = _('Tờ khai nhập khẩu %s') % rec.name
            fx = {'currency_id': rec.currency_id.id, 'amount_currency': -sum(rec.line_ids.mapped('amount_currency'))}
            lines = [('3388', picking.amount, 0, rec.partner_id, label, None),
                     ('3311', 0, rec.value_total, rec.partner_id, label, None, fx),
                     ('3333', 0, rec.duty_total, None, _('Thuế nhập khẩu %s') % rec.name, None),
                     ('1331', rec.vat_total, 0, None, _('Thuế GTGT hàng nhập khẩu %s') % rec.name, None),
                     ('33312', 0, rec.vat_total, None, _('Thuế GTGT hàng nhập khẩu %s') % rec.name, None)]
            for c in rec.cost_ids:
                lines += [('3311', 0, c.amount + c.vat, c.partner_id, c.name, None),
                          ('1331', c.vat, 0, None, _('Thuế GTGT %s') % c.name, None)]
            # chênh lệch làm tròn giá đơn vị trên phiếu kho
            diff = round(picking.amount - rec.landed_total)
            if diff > 0:
                lines.append(('711', 0, diff, None, _('Chênh lệch làm tròn giá nhập kho'), None))
            elif diff < 0:
                lines.append(('811', -diff, 0, None, _('Chênh lệch làm tròn giá nhập kho'), None))
            Move._create_from_source(rec, 'purchase', rec.date, lines, memo=label, ref=rec.name)
            rec.with_context(lfood_trade_system=True).write({'state': 'posted', 'picking_id': picking.id})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Ghi sổ %s: trị giá %s, thuế nhập khẩu %s, thuế GTGT %s, chi phí %s') % (
                    label, vnd(rec.value_total), vnd(rec.duty_total), vnd(rec.vat_total), vnd(rec.cost_total)))
        return True


class LfoodImportLine(models.Model):
    _name = 'lfood.import.line'
    _description = 'Dòng hàng nhập khẩu'

    declaration_id = fields.Many2one('lfood.import.declaration', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('lfood.product', 'Mặt hàng', required=True)
    hs_code = fields.Char('Mã HS')
    quantity = fields.Float('Số lượng', digits=(16, 3), required=True)
    price_currency = fields.Float('Đơn giá nguyên tệ', digits=(16, 4), required=True)
    amount_currency = fields.Float('Trị giá nguyên tệ', digits=(16, 2), compute='_compute_amounts', store=True)
    value = fields.Float('Trị giá tính thuế (đồng)', digits=(16, 0), compute='_compute_amounts', store=True)
    duty_rate = fields.Float('Thuế suất nhập khẩu (%)', digits=(5, 2))
    duty = fields.Float('Thuế nhập khẩu', digits=(16, 0), compute='_compute_amounts', store=True)
    vat_rate = fields.Float('Thuế suất GTGT (%)', digits=(5, 2), default=8)
    vat = fields.Float('Thuế GTGT', digits=(16, 0), compute='_compute_amounts', store=True)
    lot_name = fields.Char('Số lô')
    production_date = fields.Date('Ngày sản xuất')
    expiry_date = fields.Date('Hạn dùng')

    @api.depends('quantity', 'price_currency', 'duty_rate', 'vat_rate', 'declaration_id.rate')
    def _compute_amounts(self):
        for rec in self:
            rec.amount_currency = round(rec.quantity * rec.price_currency, 2)
            rec.value = round(rec.amount_currency * rec.declaration_id.rate)
            rec.duty = round(rec.value * rec.duty_rate / 100)
            rec.vat = round((rec.value + rec.duty) * rec.vat_rate / 100)


class LfoodImportCost(models.Model):
    _name = 'lfood.import.cost'
    _description = 'Chi phí nhập khẩu'

    declaration_id = fields.Many2one('lfood.import.declaration', required=True, ondelete='cascade', index=True)
    name = fields.Char('Nội dung', required=True)
    partner_id = fields.Many2one('res.partner', 'Đơn vị cung cấp', required=True)
    invoice_ref = fields.Char('Số hóa đơn')
    amount = fields.Float('Tiền chưa thuế', digits=(16, 0), required=True)
    vat = fields.Float('Thuế GTGT', digits=(16, 0))


class LfoodVatReturn(models.Model):
    _inherit = 'lfood.vat.return'

    def _purchase_lines(self):
        vals = super()._purchase_lines()
        decls = self.env['lfood.import.declaration'].sudo().search([
            ('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
            ('date', '>=', self.date_from), ('date', '<=', self.date_to)])
        for d in decls:
            ok = bool(d.tax_paid_ref)
            vals.append({'kind': 'in', 'date': d.tax_paid_date or d.date, 'ref': d.tax_paid_ref or d.name,
                         'partner_id': d.partner_id.id, 'name': _('Thuế GTGT hàng nhập khẩu, tờ khai %s') % d.name,
                         'base': d.value_total + d.duty_total, 'tax': d.vat_total,
                         'rate': round(d.vat_total * 100 / (d.value_total + d.duty_total), 2) if d.value_total else 0,
                         'rate_name': _('Hàng nhập khẩu'), 'deductible': ok,
                         'reason': '' if ok else _('Chưa có chứng từ nộp thuế GTGT khâu nhập khẩu'),
                         'source_model': d._name, 'source_id': d.id})
        return vals
