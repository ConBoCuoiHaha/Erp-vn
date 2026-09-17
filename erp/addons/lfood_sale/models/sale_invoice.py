"""Hóa đơn bán ra.

Hóa đơn điện tử phải lập trên hệ thống hóa đơn điện tử (nhà cung cấp dịch vụ hoặc cơ quan thuế) theo Nghị định
254/2026/NĐ-CP. App không phát hành hóa đơn: kế toán ghi nhận hóa đơn đã phát hành (ký hiệu, số, mã của cơ quan thuế)
để ghi sổ doanh thu, công nợ, thuế GTGT đầu ra và lập bảng kê bán ra.

Hóa đơn đã lập sai hoặc có thay đổi sau khi lập (Thông tư 91/2026/TT-BTC, Điều 10):
- sai tên, địa chỉ... nhưng không sai mã số thuế, tiền, thuế suất, hàng hóa: không lập lại, thông báo mẫu 04/SS-HĐĐT
  (ghi nhận ngày thông báo trên hóa đơn gốc);
- sai mã số thuế, tiền, thuế suất, tiền thuế, hàng hóa: chọn điều chỉnh (tăng: hóa đơn có hóa đơn gốc; giảm: hàng bán trả
  lại, giảm giá) hoặc thay thế (hóa đơn gốc chuyển Bị thay thế, bút toán gốc được đảo); người mua là tổ chức, hộ kinh
  doanh thì phải có văn bản thỏa thuận; đã chọn hình thức nào thì các lần sau dùng hình thức đó (khoản 6 điểm a);
- trả lại hàng, chiết khấu thương mại, quyết toán: lập hóa đơn điều chỉnh, kê khai vào kỳ lập hóa đơn điều chỉnh
  (khoản 6 điểm d)."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd


CORRECTION_REASONS = [('error', 'Hóa đơn lập sai (mã số thuế, tiền, thuế suất, hàng hóa)'), ('return', 'Trả lại hàng'),
                      ('discount', 'Chiết khấu thương mại, giảm giá'), ('settlement', 'Quyết toán, thay đổi giá trị')]


class LfoodSaleInvoice(models.Model):
    _name = 'lfood.sale.invoice'
    _description = 'Hóa đơn bán ra'
    _order = 'date desc, id desc'

    name = fields.Char('Số chứng từ', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    kind = fields.Selection([('invoice', 'Hóa đơn bán hàng'), ('refund', 'Hàng bán trả lại, giảm giá')], 'Loại',
                            required=True, default='invoice')
    correction = fields.Selection([('none', 'Hóa đơn thường'), ('adjust', 'Điều chỉnh tăng'), ('replace', 'Thay thế')],
                                  'Hóa đơn bán hàng là', default='none', required=True)
    correction_reason = fields.Selection(CORRECTION_REASONS, 'Lý do điều chỉnh, thay thế')
    agreement_file = fields.Binary('Văn bản thỏa thuận với người mua', attachment=True)
    agreement_name = fields.Char()
    error_notice_date = fields.Date('Ngày thông báo sai sót 04/SS-HĐĐT', copy=False,
                                    help='Sai tên, địa chỉ... không phải lập lại hóa đơn')
    error_notice_note = fields.Char('Nội dung sai đã thông báo', copy=False)
    origin_id = fields.Many2one('lfood.sale.invoice', 'Điều chỉnh cho hóa đơn', domain="[('kind', '=', 'invoice'), ('partner_id', '=', partner_id)]")
    partner_id = fields.Many2one('res.partner', 'Khách hàng', required=True, index=True)
    partner_vat = fields.Char(related='partner_id.vat', string='Mã số thuế')
    date = fields.Date('Ngày hạch toán', required=True, default=fields.Date.context_today, index=True)
    invoice_date = fields.Date('Ngày lập hóa đơn', default=fields.Date.context_today)
    invoice_template = fields.Char('Ký hiệu mẫu số')
    invoice_symbol = fields.Char('Ký hiệu hóa đơn')
    invoice_number = fields.Char('Số hóa đơn')
    tax_authority_code = fields.Char('Mã của cơ quan thuế')
    memo = fields.Char('Diễn giải')
    due_date = fields.Date('Hạn thanh toán')
    receivable_account = fields.Char('TK phải thu', default='1311', required=True)
    line_ids = fields.One2many('lfood.sale.invoice.line', 'invoice_id', 'Hàng hóa, dịch vụ', copy=True)
    amount_untaxed = fields.Float('Tiền hàng', digits=(16, 0), compute='_compute_amounts', store=True)
    amount_tax = fields.Float('Thuế GTGT', digits=(16, 0), compute='_compute_amounts', store=True)
    amount_total = fields.Float('Tổng thanh toán', digits=(16, 0), compute='_compute_amounts', store=True)
    amount_paid = fields.Float('Đã thu', digits=(16, 0), compute='_compute_paid')
    amount_residual = fields.Float('Còn phải thu', digits=(16, 0), compute='_compute_paid')
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ'), ('replaced', 'Bị thay thế'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             default='draft', readonly=True, copy=False, index=True)
    posted_by = fields.Many2one('res.users', 'Người ghi sổ', readonly=True, copy=False)

    _invoice_uniq = models.Constraint('unique(company_id, invoice_template, invoice_symbol, invoice_number)',
                                      'Hóa đơn (mẫu số, ký hiệu, số) đã được ghi nhận.')

    @api.depends('line_ids.amount', 'line_ids.tax')
    def _compute_amounts(self):
        for rec in self:
            rec.amount_untaxed = sum(rec.line_ids.mapped('amount'))
            rec.amount_tax = sum(rec.line_ids.mapped('tax'))
            rec.amount_total = rec.amount_untaxed + rec.amount_tax

    def _compute_paid(self):
        Payment = self.env['lfood.payment'].sudo()
        for rec in self:
            # hóa đơn thay thế nhận luôn số đã thu của các hóa đơn bị thay thế
            chain, cur = rec, rec
            while cur.correction == 'replace' and cur.origin_id.state == 'replaced':
                cur = cur.origin_id
                chain |= cur
            paid = sum(Payment.search([('sale_invoice_id', 'in', chain.ids), ('state', '=', 'posted')]).mapped(
                lambda p: p.amount if p.kind == 'in' else -p.amount))
            refunds = sum(self.sudo().search([('origin_id', '=', rec.id), ('state', '=', 'posted'),
                                              ('kind', '=', 'refund')]).mapped('amount_total'))
            rec.amount_paid = paid
            total = rec.amount_total if rec.kind == 'invoice' else 0
            rec.amount_residual = total - refunds - paid if rec.state == 'posted' else 0

    def write(self, vals):
        if not self.env.context.get('lfood_ledger_system'):
            if {'state', 'name', 'posted_by'} & set(vals):
                raise UserError(_('Trạng thái hóa đơn chỉ đổi bằng nút Ghi sổ, Hủy.'))
            if self.filtered(lambda r: r.state != 'draft') and set(vals) - {'error_notice_date', 'error_notice_note'}:
                raise UserError(_('Hóa đơn đã ghi sổ không sửa được. Sai sót thì lập hóa đơn điều chỉnh trên hệ thống hóa đơn điện tử '
                                  'và ghi nhận ở đây bằng Hàng bán trả lại, giảm giá; hoặc Hủy nếu hóa đơn đã bị hủy.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda r: r.state != 'draft'):
            raise UserError(_('Hóa đơn đã ghi sổ không xóa được.'))
        return super().unlink()

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được ghi sổ hóa đơn.'))
        Move = self.env['lfood.move']
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.line_ids or rec.amount_untaxed <= 0:
                raise UserError(_('Hóa đơn chưa có dòng hàng hóa, dịch vụ.'))
            if not (rec.invoice_symbol and rec.invoice_number):
                raise UserError(_('Nhập ký hiệu và số hóa đơn đã phát hành trên hệ thống hóa đơn điện tử.'))
            rec._check_correction()
            name = self.env['ir.sequence'].with_company(rec.company_id).next_by_code('lfood.sale.invoice') or '/'
            rec.with_context(lfood_ledger_system=True).write({'name': name, 'state': 'posted', 'posted_by': self.env.uid})
            if rec.correction == 'replace':
                old = rec.origin_id
                self.env['lfood.move']._active_for(old)._reverse(
                    memo=_('Hóa đơn %s bị thay thế bởi %s') % (old.invoice_number, rec.invoice_number))
                old.with_context(lfood_ledger_system=True).write({'state': 'replaced'})
            label = '%s %s' % (_('Hóa đơn') if rec.kind == 'invoice' else _('Điều chỉnh giảm'), rec.invoice_number)
            lines = []
            for l in rec.line_ids:
                if rec.kind == 'invoice':
                    lines += [(l.revenue_account, 0, l.amount, None, l.name, None), ('33311', 0, l.tax, None, _('Thuế GTGT %s') % l.name, None)]
                else:
                    lines += [('521', l.amount, 0, None, l.name, None), ('33311', l.tax, 0, None, _('Thuế GTGT %s') % l.name, None)]
            if rec.kind == 'invoice':
                lines.append((rec.receivable_account, rec.amount_total, 0, rec.partner_id, label, None))
            else:
                lines.append((rec.receivable_account, 0, rec.amount_total, rec.partner_id, label, None))
            Move._create_from_source(rec, 'sale', rec.date, lines, memo=rec.memo or label, ref=rec.invoice_number)
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=name,
                                                      company_id=rec.company_id.id,
                                                      summary=_('Ghi sổ %s số %s, tổng %s') % (dict(self._fields['kind'].selection)[rec.kind],
                                                                                            rec.invoice_number, vnd(rec.amount_total)))
        return True

    def _check_correction(self):
        self.ensure_one()
        origin = self.origin_id
        if self.kind == 'invoice' and self.correction == 'none':
            if origin:
                raise UserError(_('Hóa đơn thường không chọn hóa đơn gốc; chọn Điều chỉnh tăng hoặc Thay thế.'))
            return
        if not origin:
            raise UserError(_('Chọn hóa đơn gốc được điều chỉnh, thay thế.'))
        if origin.state != 'posted':
            raise UserError(_('Hóa đơn gốc %s không còn hiệu lực (đã hủy hoặc bị thay thế).') % origin.invoice_number)
        if self.kind == 'refund' and self.correction == 'replace':
            raise UserError(_('Hóa đơn thay thế là hóa đơn bán hàng, không phải hàng bán trả lại.'))
        reason = self.correction_reason or ('discount' if self.kind == 'refund' else False)
        if not reason:
            raise UserError(_('Chọn lý do điều chỉnh, thay thế.'))
        if self.correction == 'replace' and reason != 'error':
            raise UserError(_('Chỉ thay thế hóa đơn lập sai; trả lại hàng, chiết khấu, quyết toán thì lập hóa đơn điều chỉnh '
                              '(Thông tư 91/2026/TT-BTC, Điều 10 khoản 5).'))
        if reason == 'error':
            if self.partner_id.commercial_partner_id.is_company and not self.agreement_file:
                raise UserError(_('Người mua là tổ chức: đính kèm văn bản thỏa thuận ghi rõ nội dung sai '
                                  '(Thông tư 91/2026/TT-BTC, Điều 10 khoản 1 điểm b).'))
            # khoản 6 điểm a: đã điều chỉnh thì tiếp tục điều chỉnh, đã thay thế thì tiếp tục thay thế
            if self.correction == 'replace' and self.sudo().search_count([
                    ('origin_id', '=', origin.id), ('state', '=', 'posted'), ('correction_reason', '=', 'error'),
                    ('id', '!=', self.id)]):
                raise UserError(_('Hóa đơn %s đã được điều chỉnh sai sót; lần sau tiếp tục lập hóa đơn điều chỉnh '
                                  '(Thông tư 91/2026/TT-BTC, Điều 10 khoản 6).') % origin.invoice_number)
            if self.correction != 'replace' and origin.correction == 'replace':
                raise UserError(_('Hóa đơn %s là hóa đơn thay thế; sai sót tiếp theo phải lập hóa đơn thay thế '
                                  '(Thông tư 91/2026/TT-BTC, Điều 10 khoản 6).') % origin.invoice_number)

    def action_error_notice(self):
        """Ghi nhận đã thông báo sai sót không phải lập lại hóa đơn (mẫu 04/SS-HĐĐT)."""
        for rec in self.filtered(lambda r: r.state == 'posted'):
            if not rec.error_notice_note:
                raise UserError(_('Ghi nội dung sai đã thông báo.'))
            rec.error_notice_date = rec.error_notice_date or fields.Date.context_today(self)
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Thông báo sai sót 04/SS-HĐĐT hóa đơn %s: %s') % (rec.invoice_number, rec.error_notice_note))
        return True

    def action_cancel(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được hủy hóa đơn đã ghi sổ.'))
        for rec in self.filtered(lambda r: r.state == 'posted'):
            if self.env['lfood.payment'].sudo().search_count([('sale_invoice_id', '=', rec.id), ('state', '=', 'posted')]):
                raise UserError(_('Hóa đơn %s đã có phiếu thu. Hủy phiếu thu trước.') % rec.invoice_number)
            self.env['lfood.move']._active_for(rec)._reverse(memo=_('Hủy hóa đơn %s') % rec.invoice_number)
            rec.with_context(lfood_ledger_system=True).write({'state': 'cancel'})
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=rec.name,
                                                      company_id=rec.company_id.id, summary=_('Hủy hóa đơn %s') % rec.invoice_number)
        return True

    def action_view_moves(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Bút toán'), 'res_model': 'lfood.move', 'view_mode': 'list,form',
                'domain': [('source_model', '=', self._name), ('source_id', '=', self.id)]}


class LfoodSaleInvoiceLine(models.Model):
    _name = 'lfood.sale.invoice.line'
    _description = 'Dòng hóa đơn bán ra'

    invoice_id = fields.Many2one('lfood.sale.invoice', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='invoice_id.company_id', store=True)
    name = fields.Char('Tên hàng hóa, dịch vụ', required=True)
    uom = fields.Char('Đơn vị tính')
    quantity = fields.Float('Số lượng', digits=(16, 3), default=1)
    price_unit = fields.Float('Đơn giá', digits=(16, 2))
    amount = fields.Float('Thành tiền', digits=(16, 0), compute='_compute_amount', store=True, readonly=False)
    vat_rate_id = fields.Many2one('lfood.vat.rate', 'Thuế suất', required=True)
    tax = fields.Float('Tiền thuế', digits=(16, 0), compute='_compute_tax', store=True, readonly=False)
    revenue_account = fields.Char('TK doanh thu', default='511', required=True)

    @api.depends('quantity', 'price_unit')
    def _compute_amount(self):
        for rec in self:
            rec.amount = round(rec.quantity * rec.price_unit)

    @api.depends('amount', 'vat_rate_id')
    def _compute_tax(self):
        for rec in self:
            rec.tax = round(rec.amount * (rec.vat_rate_id.rate or 0) / 100)

    def write(self, vals):
        if self.filtered(lambda l: l.invoice_id.state != 'draft'):
            raise UserError(_('Hóa đơn đã ghi sổ không sửa được.'))
        return super().write(vals)


class LfoodPayment(models.Model):
    _inherit = 'lfood.payment'

    sale_invoice_id = fields.Many2one('lfood.sale.invoice', 'Thu tiền cho hóa đơn',
                                      domain="[('partner_id', '=', partner_id), ('state', '=', 'posted'), ('kind', '=', 'invoice')]")


class LfoodVatReturn(models.Model):
    _inherit = 'lfood.vat.return'

    def _sale_lines(self):
        """Bảng kê bán ra lấy từ hóa đơn bán ra đã ghi sổ; bút toán khác có thuế đầu ra (phiếu kế toán) vẫn lấy từ sổ."""
        vals = []
        kct = self.env.ref('lfood_voucher.vat_kct', raise_if_not_found=False)
        invoices = self.env['lfood.sale.invoice'].sudo().search([
            ('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
            ('date', '>=', self.date_from), ('date', '<=', self.date_to)])
        for inv in invoices:
            sign = 1 if inv.kind == 'invoice' else -1
            by_rate = {}
            for l in inv.line_ids:
                base, tax = by_rate.get(l.vat_rate_id, (0, 0))
                by_rate[l.vat_rate_id] = (base + l.amount, tax + l.tax)
            for rate, (base, tax) in by_rate.items():
                if rate == kct:
                    group, reduced = 'none', False
                elif rate.rate == 5:
                    group, reduced = '5', False
                elif rate.rate == 8:
                    group, reduced = '10', True
                elif rate.rate == 10:
                    group, reduced = '10', False
                else:
                    group, reduced = '0', False
                vals.append({'kind': 'out', 'date': inv.invoice_date or inv.date, 'ref': '%s %s' % (inv.invoice_symbol or '', inv.invoice_number or ''),
                             'partner_id': inv.partner_id.id, 'name': inv.memo or inv.name, 'base': sign * base, 'tax': sign * tax,
                             'rate': rate.rate, 'rate_name': rate.name, 'group': group, 'reduced': reduced,
                             'source_model': inv._name, 'source_id': inv.id,
                             'reason': _('Điều chỉnh giảm cho hóa đơn %s') % inv.origin_id.invoice_number if inv.kind == 'refund' else ''})
        invoice_moves = self.env['lfood.move'].sudo().search([('source_model', '=', 'lfood.sale.invoice')]).ids
        vals += [v for v in super()._sale_lines() if v['source_id'] not in invoice_moves]
        return vals
