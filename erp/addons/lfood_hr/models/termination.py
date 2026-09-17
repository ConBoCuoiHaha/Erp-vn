"""Chấm dứt hợp đồng lao động và trợ cấp thôi việc, mất việc làm (NSU14).

Căn cứ (đã tra trước khi viết):
- Bộ luật Lao động 2019, Điều 46: làm việc thường xuyên từ đủ 12 tháng, mỗi năm làm việc được trợ cấp
  một nửa tháng tiền lương; Điều 47: mất việc làm mỗi năm làm việc trả 01 tháng tiền lương, ít nhất 02 tháng.
  Thời gian tính trợ cấp là tổng thời gian làm việc thực tế trừ thời gian đã tham gia bảo hiểm thất nghiệp và
  thời gian đã được chi trả trợ cấp. Tiền lương tính trợ cấp là bình quân 06 tháng liền kề theo hợp đồng
  lao động trước khi thôi việc, mất việc.
- Nghị định 145/2020/NĐ-CP, Điều 8 khoản 3: tính theo năm đủ 12 tháng, tháng lẻ đến 6 tháng tính 1/2 năm,
  trên 6 tháng tính 1 năm.

App gợi ý số tháng đã đóng BHTN từ các bảng lương đã ghi sổ và lương bình quân từ lịch sử hợp đồng;
kế toán sửa lại theo hồ sơ thực tế (thời gian trước khi dùng app, phụ cấp lương trong hợp đồng).
Việc xác định trường hợp chấm dứt nào được hưởng trợ cấp theo Điều 34 do người lập chịu trách nhiệm.
"""
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd
from .hr_calc import months_between, allowance_years, severance

KINDS = [('resign', 'Thôi việc, hưởng trợ cấp thôi việc (Điều 46)'),
         ('redundancy', 'Mất việc làm, hưởng trợ cấp mất việc (Điều 47)'),
         ('none', 'Không thuộc diện hưởng trợ cấp')]


def month_end(year, month):
    return fields.Date.add(date(year, month, 1), months=1, days=-1)


class LfoodHrTermination(models.Model):
    _name = 'lfood.hr.termination'
    _description = 'Chấm dứt hợp đồng lao động'
    _order = 'date_end desc, id desc'

    employee_id = fields.Many2one('lfood.employee', 'Nhân viên', required=True, index=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    date_end = fields.Date('Ngày chấm dứt hợp đồng', required=True, default=fields.Date.context_today)
    kind = fields.Selection(KINDS, 'Trường hợp', required=True, default='resign')
    reason = fields.Char('Lý do, căn cứ chấm dứt', required=True)
    months_worked = fields.Integer('Tổng thời gian làm việc thực tế (tháng)', compute='_compute_worked',
                                   store=True, readonly=False)
    months_ui = fields.Integer('Thời gian đã đóng BHTN (tháng)', compute='_compute_ui', store=True,
                               readonly=False, help='Gợi ý từ các bảng lương đã ghi sổ có đóng BHTN; cộng thêm thời gian trước khi dùng app')
    months_paid = fields.Integer('Thời gian đã được chi trả trợ cấp (tháng)', default=0)
    months_counted = fields.Integer('Thời gian tính trợ cấp (tháng)', compute='_compute_amount', store=True)
    years_counted = fields.Float('Số năm tính trợ cấp', digits=(6, 1), compute='_compute_amount', store=True)
    avg_salary = fields.Float('Tiền lương bình quân 06 tháng', digits=(16, 0), compute='_compute_avg',
                              store=True, readonly=False)
    amount = fields.Float('Tiền trợ cấp', digits=(16, 0), compute='_compute_amount', store=True)
    leave_remaining = fields.Float('Ngày phép chưa nghỉ', digits=(6, 1), compute='_compute_leave_left', store=True,
                                   readonly=False, help='Thanh toán bằng khoản Tiền lương những ngày không nghỉ phép trên bảng lương cuối')
    note = fields.Text('Ghi chú')
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)

    # mỗi gợi ý một hàm riêng: nhập tay một ô không làm mất gợi ý của các ô khác
    @api.depends('employee_id', 'date_end')
    def _compute_worked(self):
        for rec in self:
            start = rec.employee_id.date_start
            rec.months_worked = months_between(start, rec.date_end) if start and rec.date_end else 0

    @api.depends('employee_id')
    def _compute_ui(self):
        for rec in self:
            slips = self.env['lfood.payroll.slip'].sudo().search([
                ('employee_id', '=', rec.employee_id.id), ('ui_base', '>', 0),
                ('run_id.state', 'in', ('posted', 'paid'))]) if rec.employee_id else []
            rec.months_ui = len(set((s.run_id.year, s.run_id.month) for s in slips))

    @api.depends('employee_id', 'date_end')
    def _compute_avg(self):
        for rec in self:
            rec.avg_salary = rec._average_salary() if rec.employee_id and rec.date_end else 0

    @api.depends('employee_id', 'date_end')
    def _compute_leave_left(self):
        for rec in self:
            if rec.employee_id.id and rec.date_end:
                entitled, taken = rec.employee_id._leave_balance(rec.date_end.year)
                rec.leave_remaining = max(0.0, entitled - taken)
            else:
                rec.leave_remaining = 0.0

    def _average_salary(self):
        """Bình quân mức lương theo hợp đồng của 06 tháng liền kề trước ngày chấm dứt."""
        self.ensure_one()
        contracts = self.employee_id.contract_ids.filtered(lambda c: c.state in ('running', 'closed'))
        values = []
        y, m = self.date_end.year, self.date_end.month
        for _i in range(6):
            m -= 1
            if m == 0:
                y, m = y - 1, 12
            at = month_end(y, m)
            c = contracts.filtered(lambda c: c.date_start <= at and (not c.date_end or c.date_end >= at))[:1]
            if c:
                values.append(c.salary)
        if not values and contracts:
            values = [contracts.sorted('date_start')[-1].salary]
        return round(sum(values) / len(values)) if values else 0

    @api.depends('kind', 'months_worked', 'months_ui', 'months_paid', 'avg_salary')
    def _compute_amount(self):
        for rec in self:
            rec.months_counted = max(0, rec.months_worked - rec.months_ui - rec.months_paid)
            rec.years_counted = allowance_years(rec.months_counted)
            rec.amount = severance(rec.kind, rec.months_worked, rec.months_counted, rec.avg_salary)

    def write(self, vals):
        if not self.env.context.get('lfood_hr_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái chỉ đổi bằng nút Ghi sổ, Hủy.'))
            if self.filtered(lambda r: r.state != 'draft') and set(vals) - {'note'}:
                raise UserError(_('Quyết định chấm dứt đã ghi sổ không sửa được.'))
        return super().write(vals)

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được ghi sổ chấm dứt hợp đồng và trợ cấp.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            emp = rec.employee_id
            label = _('Trợ cấp %s %s') % ('thôi việc' if rec.kind == 'resign' else 'mất việc làm', emp.name)
            if rec.amount:
                self.env['lfood.move']._create_from_source(
                    rec, 'general', rec.date_end,
                    [(emp.cost_account, rec.amount, 0, None, label, emp.cost_item_id),
                     ('334', 0, rec.amount, emp.partner_id, label, None)],
                    memo=label, ref=emp.code, company=emp.company_id)
            emp.contract_ids.filtered(lambda c: c.state == 'running').with_context(
                lfood_hr_system=True).write({'state': 'closed'})
            emp.write({'date_end': rec.date_end})
            rec.with_context(lfood_hr_system=True).write({'state': 'posted'})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=emp.name, company_id=emp.company_id.id,
                summary=_('Chấm dứt hợp đồng %s ngày %s: tính %s năm, lương bình quân %s, trợ cấp %s')
                        % (emp.name, rec.date_end.strftime('%d/%m/%Y'), '%g' % rec.years_counted,
                           vnd(rec.avg_salary), vnd(rec.amount)))
        return True

    def action_cancel(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được hủy.'))
        for rec in self.filtered(lambda r: r.state == 'posted'):
            move = self.env['lfood.move']._active_for(rec)
            if move:
                move._reverse(memo=_('Hủy trợ cấp %s') % rec.employee_id.name)
            rec.with_context(lfood_hr_system=True).write({'state': 'cancel'})
        return True
