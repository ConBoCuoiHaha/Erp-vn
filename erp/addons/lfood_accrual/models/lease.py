"""Thuê tài sản: kho, xe, mặt bằng (TS13).

Sổ hợp đồng thuê hoạt động: bên cho thuê, thời hạn, tiền thuê tháng, chu kỳ thanh toán, ký quỹ. App lập lịch các kỳ
thanh toán; kỳ trả trước nhiều tháng thì tạo chứng từ chi phí trả trước (Nợ 242 / Có 331) và phân bổ dần vào chi phí
theo tháng; kỳ một tháng thì kế toán ghi hóa đơn tiền thuê bằng chứng từ mua dịch vụ như thường. Ký quỹ ghi Nợ 244 /
Có 111, 112 (Thông tư 99/2025/TT-BTC). Nhắc kỳ thanh toán và hợp đồng sắp hết hạn.
Thuê của cá nhân: nghĩa vụ thuế của cá nhân cho thuê (khai thay nếu hợp đồng thỏa thuận) kế toán tự xác định.
"""
import calendar
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd

from .accrual import EXPENSE_ACCOUNTS


def add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


class LfoodLease(models.Model):
    _name = 'lfood.lease'
    _description = 'Hợp đồng thuê tài sản'
    _order = 'date_from desc, id desc'

    name = fields.Char('Tài sản thuê', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    kind = fields.Selection([('warehouse', 'Kho, mặt bằng'), ('vehicle', 'Xe'), ('equipment', 'Máy móc, thiết bị'),
                             ('other', 'Khác')], 'Loại', required=True, default='warehouse')
    partner_id = fields.Many2one('res.partner', 'Bên cho thuê', required=True)
    contract_ref = fields.Char('Số hợp đồng', required=True)
    date_from = fields.Date('Thuê từ', required=True)
    date_to = fields.Date('Đến', required=True)
    monthly_rent = fields.Float('Tiền thuê một tháng (chưa thuế)', digits=(16, 0), required=True)
    cycle = fields.Integer('Chu kỳ thanh toán (tháng)', default=1, required=True)
    expense_account = fields.Selection(EXPENSE_ACCOUNTS, 'TK chi phí', required=True, default='6427')
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP')
    deposit = fields.Float('Tiền ký quỹ, đặt cọc', digits=(16, 0))
    deposit_method = fields.Selection([('bank', 'Chuyển khoản'), ('cash', 'Tiền mặt')], 'Hình thức ký quỹ', default='bank')
    document = fields.Binary('Bản hợp đồng', attachment=True)
    document_name = fields.Char()
    period_ids = fields.One2many('lfood.lease.period', 'lease_id', 'Kỳ thanh toán', readonly=True)
    state = fields.Selection([('draft', 'Nháp'), ('running', 'Đang thuê'), ('closed', 'Đã kết thúc')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)

    @api.constrains('date_from', 'date_to', 'cycle', 'monthly_rent')
    def _check_values(self):
        for rec in self:
            if rec.date_to <= rec.date_from:
                raise ValidationError(_('Ngày kết thúc phải sau ngày bắt đầu.'))
            if rec.cycle <= 0 or rec.monthly_rent <= 0:
                raise ValidationError(_('Chu kỳ và tiền thuê phải lớn hơn 0.'))

    def _schedule(self):
        """[(ngày bắt đầu kỳ, số tháng)] đến hết hợp đồng; kỳ cuối có thể ngắn hơn chu kỳ."""
        self.ensure_one()
        out, start, i = [], self.date_from, 0
        while start <= self.date_to:
            i += self.cycle
            nxt = add_months(self.date_from, i)
            months = self.cycle
            if nxt - timedelta(days=1) > self.date_to:
                # đếm số tháng còn lại, phần lẻ tính một tháng
                months = 0
                while add_months(start, months) <= self.date_to:
                    months += 1
            out.append((start, months))
            start = nxt
        return out

    def action_start(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được ghi hợp đồng thuê.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.document:
                raise UserError(_('Đính kèm bản hợp đồng thuê.'))
            self.env['lfood.lease.period'].create([
                {'lease_id': rec.id, 'date': d, 'months': m, 'amount': rec.monthly_rent * m} for d, m in rec._schedule()])
            if rec.deposit:
                label = _('Ký quỹ thuê %s') % rec.name
                self.env['lfood.move']._create_from_source(rec, 'cash' if rec.deposit_method == 'cash' else 'bank', rec.date_from, [
                    ('244', rec.deposit, 0, rec.partner_id, label, None),
                    ('111' if rec.deposit_method == 'cash' else '112', 0, rec.deposit, None, label, None)],
                    memo=label, ref=rec.contract_ref, key='deposit', company=rec.company_id)
            rec.state = 'running'
        return True

    def action_close(self, refund_deposit=True):
        """Kết thúc thuê: hoàn ký quỹ (Nợ 112 / Có 244) nếu có."""
        for rec in self.filtered(lambda r: r.state == 'running'):
            if rec.deposit and refund_deposit:
                label = _('Nhận lại ký quỹ thuê %s') % rec.name
                self.env['lfood.move']._create_from_source(rec, 'bank', fields.Date.context_today(self), [
                    ('112', rec.deposit, 0, None, label, None),
                    ('244', 0, rec.deposit, rec.partner_id, label, None)],
                    memo=label, ref=rec.contract_ref, key='deposit_back', company=rec.company_id)
            rec.state = 'closed'
        return True


class LfoodLeasePeriod(models.Model):
    _name = 'lfood.lease.period'
    _description = 'Kỳ thanh toán tiền thuê'
    _order = 'date'

    lease_id = fields.Many2one('lfood.lease', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='lease_id.company_id', store=True, index=True)
    date = fields.Date('Kỳ từ ngày', required=True)
    months = fields.Integer('Số tháng')
    amount = fields.Float('Tiền thuê kỳ (chưa thuế)', digits=(16, 0))
    prepaid_id = fields.Many2one('lfood.prepaid', 'Chứng từ trả trước', readonly=True)
    done = fields.Boolean('Đã ghi nhận', readonly=True)

    def action_record(self):
        """Ghi nhận kỳ: nhiều tháng thì lập chi phí trả trước phân bổ theo tháng; một tháng thì chỉ đánh dấu
        (hóa đơn tiền thuê ghi bằng chứng từ mua dịch vụ)."""
        for p in self.filtered(lambda x: not x.done):
            lease = p.lease_id
            if lease.state != 'running':
                raise UserError(_('Hợp đồng %s không ở trạng thái Đang thuê.') % lease.contract_ref)
            if p.months > 1:
                pre = self.env['lfood.prepaid'].create({
                    'company_id': lease.company_id.id, 'label': _('Tiền thuê %s từ %s') % (lease.name, p.date.strftime('%d/%m/%Y')),
                    'partner_id': lease.partner_id.id, 'date': p.date, 'amount': p.amount, 'months': p.months,
                    'date_start': p.date, 'expense_account': lease.expense_account, 'cost_item_id': lease.cost_item_id.id,
                    'post_initial': True, 'counterpart_account': '3311'})
                pre.action_confirm()
                p.prepaid_id = pre
            p.done = True
        return True


class LfoodReminder(models.Model):
    _inherit = 'lfood.reminder'

    category = fields.Selection(selection_add=[('contract', 'Hợp đồng')], ondelete={'contract': 'cascade'})

    def _collect_extra(self, company, today, horizon):
        out = super()._collect_extra(company, today, horizon)
        leases = self.env['lfood.lease'].sudo().search([('company_id', '=', company.id), ('state', '=', 'running')])
        for lease in leases:
            if lease.date_to <= horizon:
                out.append({'key': 'lease-end-%s-%s' % (lease.id, lease.date_to), 'category': 'contract',
                            'title': _('Hợp đồng thuê %s (%s) hết hạn') % (lease.name, lease.contract_ref),
                            'due_date': lease.date_to, 'res_model': lease._name, 'res_id': lease.id})
            for p in lease.period_ids.filtered(lambda x: not x.done and x.date <= horizon):
                out.append({'key': 'lease-pay-%s' % p.id, 'category': 'contract',
                            'title': _('Thanh toán tiền thuê %s kỳ từ %s: %s') % (
                                lease.name, p.date.strftime('%d/%m/%Y'), vnd(p.amount)),
                            'due_date': p.date, 'res_model': lease._name, 'res_id': lease.id})
        return out
