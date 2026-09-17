"""Tạm ứng lương giữa kỳ (LUONG09) và đưa khen thưởng vào bảng lương (LUONG10).

Tạm ứng lương cho người lao động ghi Nợ 334 / Có 111, 112 khi chi (Thông tư 99/2025/TT-BTC, tài khoản 334); khi tính
lương tháng, app thêm dòng "Trừ tạm ứng lương" vào phiếu lương để thực lĩnh còn lại đúng, dòng này không ghi sổ lại.
Khen thưởng có tiền (quyết định khen thưởng) được đưa vào bảng lương tháng có ngày khen thưởng bằng khoản Thưởng, tính
thuế TNCN cùng tiền lương tháng đó. Lương tháng 13 nhập bằng khoản Lương tháng 13.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd


class LfoodSalaryAdvance(models.Model):
    _name = 'lfood.salary.advance'
    _description = 'Tạm ứng lương'
    _order = 'date desc, id desc'

    employee_id = fields.Many2one('lfood.employee', 'Người lao động', required=True, index=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    date = fields.Date('Ngày chi', required=True, default=fields.Date.context_today)
    amount = fields.Float('Số tiền', digits=(16, 0), required=True)
    method = fields.Selection([('bank', 'Chuyển khoản'), ('cash', 'Tiền mặt')], 'Hình thức chi', default='bank', required=True)
    note = fields.Char('Lý do')
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã chi'), ('cancel', 'Đã hủy')], 'Trạng thái', default='draft',
                             required=True, readonly=True, copy=False, index=True)
    slip_line_id = fields.Many2one('lfood.payroll.slip.line', 'Đã trừ ở phiếu lương', readonly=True, copy=False,
                                   ondelete='set null')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('Tạm ứng lương %s %s') % (rec.employee_id.name or '', vnd(rec.amount))

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được chi tạm ứng lương.'))
        Move = self.env['lfood.move']
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if rec.amount <= 0:
                raise UserError(_('Số tiền phải lớn hơn 0.'))
            emp = rec.employee_id
            label = _('Tạm ứng lương %s') % emp.name
            Move._create_from_source(rec, 'cash' if rec.method == 'cash' else 'bank', rec.date, [
                ('334', rec.amount, 0, emp.partner_id, label, None),
                ('111' if rec.method == 'cash' else '112', 0, rec.amount, None, label, None)],
                memo=label, ref=emp.code, company=emp.company_id)
            rec.state = 'posted'
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=label, company_id=rec.company_id.id,
                summary=_('Chi %s: %s') % (label, vnd(rec.amount)))
        return True

    def action_cancel(self):
        for rec in self.filtered(lambda r: r.state == 'posted'):
            if rec.slip_line_id:
                raise UserError(_('Tạm ứng đã trừ ở %s; xóa dòng trên phiếu lương trước.') % rec.slip_line_id.slip_id.run_id.name)
            for move in self.env['lfood.move']._active_for(rec):
                move._reverse(memo=_('Hủy tạm ứng lương'))
            rec.state = 'cancel'
        self.filtered(lambda r: r.state == 'draft').write({'state': 'cancel'})
        return True


class LfoodHrReward(models.Model):
    _inherit = 'lfood.hr.reward'

    slip_line_id = fields.Many2one('lfood.payroll.slip.line', 'Đã đưa vào phiếu lương', readonly=True, copy=False,
                                   ondelete='set null')


class LfoodPayrollRun(models.Model):
    _inherit = 'lfood.payroll.run'

    def _load_extras(self):
        res = super()._load_extras()
        Line = self.env['lfood.payroll.slip.line']
        adv_comp = self.env.ref('lfood_pit.comp_salary_advance')
        bonus_comp = self.env.ref('lfood_payroll.comp_bonus')
        for rec in self:
            slips = {s.employee_id: s for s in rec.slip_ids}
            period = [('employee_id', 'in', list(e.id for e in slips)), ('slip_line_id', '=', False),
                      ('date', '>=', rec.date_from), ('date', '<=', rec.date_to)]
            for adv in self.env['lfood.salary.advance'].search(period + [('state', '=', 'posted')]):
                adv.slip_line_id = Line.create({'slip_id': slips[adv.employee_id].id, 'component_id': adv_comp.id,
                                                'amount': adv.amount})
            for rw in self.env['lfood.hr.reward'].search(period + [('amount', '>', 0)]):
                rw.slip_line_id = Line.create({'slip_id': slips[rw.employee_id].id, 'component_id': bonus_comp.id,
                                               'amount': rw.amount})
        return res
