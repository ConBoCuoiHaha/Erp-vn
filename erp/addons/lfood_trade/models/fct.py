"""Thuế nhà thầu nước ngoài (THUE13).

Bên Việt Nam khai, nộp thay thuế GTGT và thuế TNDN khi trả tiền cho tổ chức nước ngoài không có cơ sở thường trú
(Thông tư 103/2014/TT-BTC hết hiệu lực từ 01/7/2026; khai thuế theo Thông tư 89/2026/TT-BTC Điều 30).
- Thuế TNDN = doanh thu tính thuế x tỷ lệ theo ngành nghề (Nghị định 320/2025/NĐ-CP, Điều 12 khoản 3); doanh thu tính
  thuế chưa trừ các khoản thuế phải nộp (Thông tư 20/2026/TT-BTC, Điều 7 khoản 3).
- Thuế GTGT = doanh thu x tỷ lệ % theo phương pháp tính trực tiếp (Luật Thuế GTGT 48/2024/QH15, Điều 12 khoản 2).
Hợp đồng giá đã gồm thuế: doanh thu tính thuế là giá hợp đồng. Hợp đồng giá chưa gồm thuế (bên Việt Nam chịu thuế):
doanh thu tính thuế = số tiền trả nhà thầu / (1 - tỷ lệ GTGT - tỷ lệ TNDN), mở rộng công thức Điều 7 khoản 4 điểm a
Thông tư 20/2026 khi bên Việt Nam chịu cả thuế GTGT - kế toán đối chiếu hướng dẫn của cơ quan thuế.
Ghi sổ: Nợ chi phí (doanh thu - thuế GTGT), Nợ 1331 (thuế GTGT nộp thay, được khấu trừ khi có chứng từ nộp thuế -
Luật Thuế GTGT Điều 14 khoản 2 điểm a) / Có 3311 nhà thầu (số thực trả), Có 33311 thuế GTGT, Có 3334 thuế TNDN.
Tỷ lệ lấy từ tham số pháp lý NHA_THAU_GTGT_*, NHA_THAU_TNDN_*; khoản không chịu thuế GTGT (bản quyền, lãi vay) để 0%.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd

FCT_TYPES = [('SERVICE', 'Dịch vụ'), ('HOTEL_MGMT', 'Quản lý nhà hàng, khách sạn, casino'), ('GOODS', 'Cung cấp hàng hóa tại Việt Nam'), ('ROYALTY', 'Tiền bản quyền'), ('RENTAL', 'Cho thuê máy móc, thiết bị, phương tiện vận tải'), ('INTEREST', 'Lãi tiền vay'), ('CONSTRUCTION', 'Xây dựng không bao thầu nguyên vật liệu'), ('TRANSPORT', 'Vận tải'), ('OTHER', 'Hoạt động khác')]


def fct_amounts(amount, vat_pct, cit_pct, net_contract):
    """(doanh thu tính thuế, thuế GTGT, thuế TNDN, số trả nhà thầu)."""
    base = amount / (1 - (vat_pct + cit_pct) / 100) if net_contract else amount
    base = round(base)
    vat, cit = round(base * vat_pct / 100), round(base * cit_pct / 100)
    return base, vat, cit, base - vat - cit


class LfoodFctPayment(models.Model):
    _name = 'lfood.fct.payment'
    _description = 'Thanh toán cho nhà thầu nước ngoài'
    _order = 'date desc, id desc'

    name = fields.Char('Nội dung', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    partner_id = fields.Many2one('res.partner', 'Nhà thầu nước ngoài', required=True)
    contract_ref = fields.Char('Số hợp đồng', required=True)
    date = fields.Date('Ngày thanh toán', required=True, default=fields.Date.context_today)
    service_type = fields.Selection(FCT_TYPES, 'Ngành nghề', required=True, default='SERVICE')
    amount = fields.Float('Số tiền theo hợp đồng (đồng)', digits=(16, 0), required=True)
    net_contract = fields.Boolean('Giá hợp đồng chưa gồm thuế (bên Việt Nam chịu thuế)')
    vat_pct = fields.Float('Tỷ lệ GTGT (%)', compute='_compute_rates', store=True, readonly=False)
    cit_pct = fields.Float('Tỷ lệ TNDN (%)', compute='_compute_rates', store=True, readonly=False)
    base = fields.Float('Doanh thu tính thuế', digits=(16, 0), compute='_compute_taxes', store=True)
    vat = fields.Float('Thuế GTGT nộp thay', digits=(16, 0), compute='_compute_taxes', store=True)
    cit = fields.Float('Thuế TNDN nộp thay', digits=(16, 0), compute='_compute_taxes', store=True)
    pay_amount = fields.Float('Trả nhà thầu', digits=(16, 0), compute='_compute_taxes', store=True)
    expense_account = fields.Char('TK chi phí', default='6427', required=True)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP')
    tax_paid_ref = fields.Char('Số chứng từ nộp thuế')
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ')], 'Trạng thái', default='draft',
                             required=True, readonly=True, copy=False)

    @api.depends('service_type', 'date')
    def _compute_rates(self):
        P = self.env['lfood.legal.param']
        for rec in self:
            d = rec.date or fields.Date.context_today(rec)
            rec.vat_pct = P.get_value('NHA_THAU_GTGT_%s' % rec.service_type, d)
            rec.cit_pct = P.get_value('NHA_THAU_TNDN_%s' % rec.service_type, d)

    @api.depends('amount', 'vat_pct', 'cit_pct', 'net_contract')
    def _compute_taxes(self):
        for rec in self:
            rec.base, rec.vat, rec.cit, rec.pay_amount = fct_amounts(rec.amount, rec.vat_pct, rec.cit_pct, rec.net_contract)

    def write(self, vals):
        if self.filtered(lambda r: r.state != 'draft') and set(vals) - {'tax_paid_ref'} \
                and not self.env.context.get('lfood_trade_system'):
            raise UserError(_('Chứng từ đã ghi sổ không sửa được.'))
        return super().write(vals)

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được ghi sổ.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if rec.amount <= 0:
                raise UserError(_('Số tiền phải lớn hơn 0.'))
            label = _('%s - nhà thầu %s') % (rec.name, rec.partner_id.name)
            self.env['lfood.move']._create_from_source(rec, 'purchase', rec.date, [
                (rec.expense_account, rec.base - rec.vat, 0, None, label, rec.cost_item_id),
                ('1331', rec.vat, 0, None, _('Thuế GTGT nộp thay %s') % label, None),
                ('3311', 0, rec.pay_amount, rec.partner_id, label, None),
                ('33311', 0, rec.vat, None, _('Thuế GTGT nộp thay %s') % label, None),
                ('3334', 0, rec.cit, None, _('Thuế TNDN nộp thay %s') % label, None)],
                memo=label, ref=rec.contract_ref)
            rec.with_context(lfood_trade_system=True).write({'state': 'posted'})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Ghi sổ %s: doanh thu tính thuế %s, GTGT %s, TNDN %s') % (
                    label, vnd(rec.base), vnd(rec.vat), vnd(rec.cit)))
        return True


class LfoodVatReturn(models.Model):
    _inherit = 'lfood.vat.return'

    def _purchase_lines(self):
        vals = super()._purchase_lines()
        for f in self.env['lfood.fct.payment'].sudo().search([
                ('company_id', '=', self.company_id.id), ('state', '=', 'posted'), ('vat', '>', 0),
                ('date', '>=', self.date_from), ('date', '<=', self.date_to)]):
            ok = bool(f.tax_paid_ref)
            vals.append({'kind': 'in', 'date': f.date, 'ref': f.tax_paid_ref or f.contract_ref, 'partner_id': f.partner_id.id,
                         'name': _('Thuế GTGT nộp thay nhà thầu nước ngoài: %s') % f.name, 'base': f.base, 'tax': f.vat,
                         'rate': f.vat_pct, 'rate_name': _('Nộp thay nhà thầu'), 'deductible': ok,
                         'reason': '' if ok else _('Chưa có chứng từ nộp thuế GTGT thay nhà thầu'),
                         'source_model': f._name, 'source_id': f.id})
        return vals
