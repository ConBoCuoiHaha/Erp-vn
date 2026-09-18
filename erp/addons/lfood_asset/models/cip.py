"""Xây dựng cơ bản dở dang (TS10).

Công trình, dự án đang đầu tư: mọi khoản chi tập hợp vào TK 241 (Nợ 2411, 2412... / Có 111, 112, 331). Khi nghiệm thu, bàn giao
đưa vào sử dụng: kết chuyển toàn bộ chi phí sang nguyên giá tài sản cố định (Nợ 211 / Có 241x) và tạo thẻ tài sản với
nguyên giá bằng chi phí đã tập hợp, kế toán chọn loại tài sản và thời gian sử dụng rồi Ghi tăng.
Chi phí lãi vay trong thời gian xây dựng, chi phí chạy thử... nếu được vốn hóa thì ghi thành một dòng chi phí ở đây.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd

COUNTERPARTS = [('3311', '3311 Phải trả người bán'), ('111', '111 Tiền mặt'), ('112', '112 Tiền gửi ngân hàng'),
                ('335', '335 Chi phí phải trả'), ('242', '242 Chi phí trả trước')]


class LfoodCip(models.Model):
    _name = 'lfood.cip'
    _description = 'Xây dựng cơ bản dở dang'
    _order = 'date_start desc, id desc'

    name = fields.Char('Công trình, hạng mục', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    date_start = fields.Date('Khởi công', required=True, default=fields.Date.context_today)
    account = fields.Selection([('2411', '2411 Mua sắm TSCĐ'), ('2412', '2412 Xây dựng cơ bản'),
                                ('2413', '2413 Sửa chữa, bảo dưỡng định kỳ TSCĐ'), ('2414', '2414 Nâng cấp, cải tạo TSCĐ')],
                               'TK tập hợp', default='2412', required=True)
    line_ids = fields.One2many('lfood.cip.line', 'cip_id', 'Chi phí')
    total = fields.Float('Chi phí đã tập hợp', digits=(16, 0), compute='_compute_total', store=True)
    category_id = fields.Many2one('lfood.asset.category', 'Loại tài sản khi nghiệm thu')
    life_months = fields.Integer('Thời gian sử dụng (tháng)')
    usage = fields.Selection([('production', 'Bộ phận sản xuất, nhà máy'), ('sales', 'Bộ phận bán hàng'),
                              ('admin', 'Bộ phận quản lý')], 'Bộ phận sử dụng', default='production')
    asset_id = fields.Many2one('lfood.asset', 'Thẻ tài sản', readonly=True, copy=False)
    accept_date = fields.Date('Ngày nghiệm thu, bàn giao', readonly=True, copy=False)
    state = fields.Selection([('draft', 'Đang xây dựng'), ('done', 'Đã nghiệm thu, ghi tăng tài sản'),
                              ('cancel', 'Đã hủy')], 'Trạng thái', default='draft', required=True, readonly=True)

    @api.depends('line_ids.amount', 'line_ids.state')
    def _compute_total(self):
        for rec in self:
            rec.total = sum(rec.line_ids.filtered(lambda l: l.state == 'posted').mapped('amount'))

    def action_accept(self, life_months=None):
        """Nghiệm thu: kết chuyển 241 sang nguyên giá và tạo thẻ tài sản nháp."""
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được nghiệm thu công trình.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.total:
                raise UserError(_('Công trình chưa có chi phí nào đã ghi sổ.'))
            if not (rec.category_id and (life_months or rec.life_months)):
                raise UserError(_('Chọn loại tài sản và thời gian sử dụng trước khi nghiệm thu.'))
            today = fields.Date.context_today(self)
            asset = self.env['lfood.asset'].create({
                'name': rec.name, 'category_id': rec.category_id.id, 'company_id': rec.company_id.id,
                'original_value': rec.total, 'life_months': life_months or rec.life_months,
                'date_start': today, 'purchase_date': today, 'usage': rec.usage or 'production'})
            label = _('Nghiệm thu %s, kết chuyển chi phí xây dựng cơ bản') % rec.name
            self.env['lfood.move']._create_from_source(rec, 'general', today, [
                (asset.account_asset, rec.total, 0, None, label, None),
                (rec.account, 0, rec.total, None, label, None)], memo=label, ref=rec.name, key='accept')
            rec.write({'state': 'done', 'asset_id': asset.id, 'accept_date': today})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Nghiệm thu %s: kết chuyển %s sang nguyên giá tài sản %s') % (rec.name, vnd(rec.total), asset.name))
        return True


class LfoodCipLine(models.Model):
    _name = 'lfood.cip.line'
    _description = 'Chi phí xây dựng cơ bản'
    _order = 'date, id'

    cip_id = fields.Many2one('lfood.cip', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='cip_id.company_id', store=True)
    date = fields.Date('Ngày', required=True, default=fields.Date.context_today)
    name = fields.Char('Nội dung', required=True)
    partner_id = fields.Many2one('res.partner', 'Nhà thầu, nhà cung cấp')
    amount = fields.Float('Số tiền', digits=(16, 0), required=True)
    counterpart_account = fields.Selection(COUNTERPARTS, 'TK đối ứng', default='3311', required=True)
    invoice_ref = fields.Char('Số hóa đơn')
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ')], 'Trạng thái', default='draft', required=True,
                             readonly=True)

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được ghi sổ chi phí.'))
        for rec in self.filtered(lambda l: l.state == 'draft'):
            if rec.cip_id.state != 'draft':
                raise UserError(_('Công trình đã nghiệm thu, không ghi thêm chi phí.'))
            label = '%s - %s' % (rec.cip_id.name, rec.name)
            self.env['lfood.move']._create_from_source(rec, 'general', rec.date, [
                (rec.cip_id.account, rec.amount, 0, None, label, None),
                (rec.counterpart_account, 0, rec.amount, rec.partner_id, label, None)],
                memo=label, ref=rec.invoice_ref or rec.cip_id.name)
            rec.state = 'posted'
        return True

    def write(self, vals):
        if self.filtered(lambda l: l.state == 'posted') and set(vals) - {'state'}:
            raise UserError(_('Chi phí đã ghi sổ không sửa được.'))
        return super().write(vals)
