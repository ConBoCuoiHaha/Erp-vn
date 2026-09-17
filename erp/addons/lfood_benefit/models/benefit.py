"""Hồ sơ hưởng chế độ ốm đau, thai sản (NSU09).

Doanh nghiệp lập danh sách đề nghị (qua phần mềm giao dịch BHXH), chi trả cho người lao động hoặc cơ quan BHXH chi trực
tiếp. App tính số ngày, mức hưởng để đối chiếu và ghi sổ số phải trả người lao động do quỹ BHXH chi: Nợ 3383 / Có 334
(khi doanh nghiệp chi hộ); khi cơ quan BHXH chuyển tiền: Nợ 112 / Có 3383 bằng phiếu thu.
Chưa làm: trừ ngày công trên bảng lương, bệnh cần chữa trị dài ngày, nghỉ sinh con của lao động nữ nhận con nuôi, mang thai hộ.
"""
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd
from .benefit_calc import sick_limit, child_sick_limit, miscarriage_days, male_birth_days, daily_amount

KINDS = [('sick', 'Ốm đau'), ('child_sick', 'Chăm con ốm'), ('recovery', 'Dưỡng sức sau ốm đau'),
         ('prenatal', 'Khám thai'), ('miscarriage', 'Sảy thai, phá thai bệnh lý'), ('birth', 'Lao động nữ sinh con'),
         ('male_birth', 'Lao động nam nghỉ khi vợ sinh con')]
WORKDAY_KINDS = ('sick', 'child_sick', 'prenatal', 'male_birth')


class LfoodHrBenefit(models.Model):
    _name = 'lfood.hr.benefit'
    _description = 'Hồ sơ hưởng ốm đau, thai sản'
    _order = 'date_from desc, id desc'

    name = fields.Char('Số', default='/', readonly=True, copy=False, index=True)
    employee_id = fields.Many2one('lfood.employee', 'Người lao động', required=True, index=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    kind = fields.Selection(KINDS, 'Chế độ', required=True, default='sick')
    date_from = fields.Date('Nghỉ từ ngày', required=True)
    date_to = fields.Date('Đến ngày', required=True)
    half_days = fields.Float('Trừ số ngày nghỉ nửa ngày', digits=(4, 1), help='Nghỉ không trọn ngày tính nửa ngày')
    years_paid = fields.Float('Số năm đã đóng BHXH', digits=(4, 1))
    hard_job = fields.Boolean('Nghề nặng nhọc, độc hại hoặc nơi phụ cấp khu vực từ 0,7')
    child_birth = fields.Date('Ngày sinh của con (chăm con ốm)')
    gestation_weeks = fields.Integer('Tuổi thai (tuần)')
    children = fields.Integer('Số con sinh ra', default=1)
    surgery = fields.Boolean('Sinh phải phẫu thuật')
    preterm = fields.Boolean('Sinh con dưới 32 tuần tuổi')
    salary_base = fields.Float('Tiền lương làm căn cứ', digits=(16, 0),
                               help='Ốm đau: lương đóng BHXH tháng gần nhất; thai sản: bình quân 6 tháng gần nhất')
    days = fields.Float('Số ngày hưởng', digits=(6, 1), compute='_compute_amount', store=True)
    limit_days = fields.Float('Số ngày tối đa', digits=(6, 1), compute='_compute_amount', store=True)
    used_days = fields.Float('Đã hưởng trong năm', digits=(6, 1), compute='_compute_amount', store=True)
    amount = fields.Float('Tiền hưởng', digits=(16, 0), compute='_compute_amount', store=True)
    lump_sum = fields.Float('Trợ cấp một lần', digits=(16, 0), compute='_compute_amount', store=True)
    total = fields.Float('Tổng', digits=(16, 0), compute='_compute_amount', store=True)
    certificate = fields.Binary('Giấy chứng nhận nghỉ việc hưởng BHXH, giấy khai sinh', attachment=True)
    certificate_name = fields.Char()
    bhxh_ref = fields.Char('Số hồ sơ, kết quả duyệt của cơ quan BHXH')
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)

    def _param(self, code, default):
        return self.env['lfood.legal.param'].get_value(code, self.date_from, default=default)

    def _calendar_days(self):
        return (self.date_to - self.date_from).days + 1

    def _work_days(self):
        return self.env['lfood.holiday'].working_days_between(self.date_from - timedelta(days=1),
                                                              self.date_to + timedelta(days=1))

    def _used_in_year(self, kinds):
        others = self.search([('employee_id', '=', self.employee_id.id), ('kind', 'in', kinds), ('state', '=', 'posted'),
                              ('id', '!=', self.id or 0), ('date_from', '>=', self.date_from.replace(month=1, day=1)),
                              ('date_from', '<=', self.date_from.replace(month=12, day=31))])
        if self.kind == 'child_sick':
            others = others.filtered(lambda r: r.child_birth == self.child_birth)
        return sum(others.mapped('days'))

    @api.depends('kind', 'date_from', 'date_to', 'half_days', 'years_paid', 'hard_job', 'child_birth', 'gestation_weeks',
                 'children', 'surgery', 'preterm', 'salary_base')
    def _compute_amount(self):
        for rec in self:
            vals = {'days': 0, 'limit_days': 0, 'used_days': 0, 'amount': 0, 'lump_sum': 0}
            if rec.date_from and rec.date_to and rec.date_to >= rec.date_from:
                days = rec._work_days() if rec.kind in WORKDAY_KINDS else rec._calendar_days()
                days -= (rec.half_days or 0) / 2
                limit = 0
                if rec.kind == 'sick':
                    limit = sick_limit(rec.years_paid, rec.hard_job)
                elif rec.kind == 'child_sick' and rec.child_birth:
                    limit = child_sick_limit(relativedelta(rec.date_from, rec.child_birth).years)
                elif rec.kind == 'recovery':
                    limit = 10
                elif rec.kind == 'prenatal':
                    limit = 2
                elif rec.kind == 'miscarriage':
                    limit = miscarriage_days(rec.gestation_weeks)
                elif rec.kind == 'male_birth':
                    limit = male_birth_days(rec.surgery, (rec.children or 1) >= 2, rec.preterm)
                used = rec._used_in_year([rec.kind]) if rec.kind in ('sick', 'child_sick', 'recovery') else 0
                vals.update({'days': days, 'limit_days': limit, 'used_days': used})
                if rec.kind == 'sick' or rec.kind == 'child_sick':
                    vals['amount'] = round(daily_amount(rec.salary_base, rec._param('OM_DAU_TY_LE', 75)) * days)
                elif rec.kind == 'recovery':
                    ref = rec._param('LUONG_CO_SO', 0)
                    vals['amount'] = round(ref * rec._param('DUONG_SUC_TY_LE', 30) / 100 * days)
                elif rec.kind == 'birth':
                    months = 6 + max((rec.children or 1) - 1, 0)
                    vals['limit_days'] = 0
                    vals['amount'] = round(rec.salary_base * months)
                    vals['lump_sum'] = round(rec._param('LUONG_CO_SO', 0) *
                                             rec._param('TRO_CAP_SINH_CON_LAN_THAM_CHIEU', 2) * (rec.children or 1))
                else:
                    vals['amount'] = round(daily_amount(rec.salary_base, 100) * days)
            vals['total'] = vals['amount'] + vals['lump_sum']
            rec.update(vals)

    @api.onchange('employee_id')
    def _onchange_employee(self):
        if self.employee_id and not self.salary_base:
            self.salary_base = self.employee_id.insurance_salary

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('lfood.hr.benefit') or '/'
            if not vals.get('salary_base') and vals.get('employee_id'):
                vals['salary_base'] = self.env['lfood.employee'].browse(vals['employee_id']).insurance_salary
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_benefit_system') and self.filtered(lambda r: r.state != 'draft'):
            raise UserError(_('Hồ sơ đã ghi sổ không sửa được. Hủy rồi lập hồ sơ mới.'))
        return super().write(vals)

    def _check_rules(self):
        self.ensure_one()
        if not self.employee_id.insurance_enrolled:
            raise ValidationError(_('%s không tham gia BHXH bắt buộc.') % self.employee_id.name)
        if self.date_to < self.date_from:
            raise ValidationError(_('Ngày kết thúc phải sau ngày bắt đầu.'))
        if not self.salary_base:
            raise ValidationError(_('Nhập tiền lương làm căn cứ hưởng.'))
        if self.kind == 'child_sick' and not self.limit_days:
            raise ValidationError(_('Chỉ hưởng chăm con ốm khi con dưới 7 tuổi: nhập ngày sinh của con.'))
        if self.kind == 'recovery' and not self._used_in_year(['sick']) >= 30:
            raise ValidationError(_('Dưỡng sức chỉ áp dụng khi đã nghỉ ốm đau từ 30 ngày trong năm.'))
        if self.kind == 'birth':
            if self.employee_id.gender == 'male':
                raise ValidationError(_('Chế độ sinh con áp dụng cho lao động nữ; lao động nam chọn nghỉ khi vợ sinh.'))
            months = 6 + max((self.children or 1) - 1, 0)
            if self.date_to > self.date_from + relativedelta(months=months, days=-1):
                raise ValidationError(_('Nghỉ sinh con tối đa %s tháng.') % months)
            return
        if self.limit_days and self.used_days + self.days > self.limit_days:
            raise ValidationError(_('%s: đã hưởng %s ngày, lần này %s ngày, vượt tối đa %s ngày.') % (
                dict(KINDS)[self.kind], '%g' % self.used_days, '%g' % self.days, '%g' % self.limit_days))
        if self.kind == 'prenatal':
            count = self.search_count([('employee_id', '=', self.employee_id.id), ('kind', '=', 'prenatal'),
                                       ('state', '=', 'posted'),
                                       ('date_from', '>=', self.date_from - relativedelta(months=10))])
            if count >= 5:
                raise ValidationError(_('Khám thai tối đa 5 lần.'))

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được ghi sổ.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            rec._check_rules()
            if not rec.certificate:
                raise ValidationError(_('Đính kèm giấy chứng nhận nghỉ việc hưởng BHXH hoặc giấy tờ tương ứng.'))
            label = _('%s %s từ %s đến %s') % (dict(KINDS)[rec.kind], rec.employee_id.name,
                                                rec.date_from.strftime('%d/%m/%Y'), rec.date_to.strftime('%d/%m/%Y'))
            partner = rec.employee_id.partner_id
            self.env['lfood.move']._create_from_source(
                rec, 'general', rec.date_to, [('3383', rec.total, 0, None, label, None),
                                              ('334', 0, rec.total, partner, label, None)],
                memo=label, ref=rec.name, company=rec.company_id)
            rec.with_context(lfood_benefit_system=True).write({'state': 'posted'})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('%s: %s ngày, %s') % (label, '%g' % rec.days, vnd(rec.total)))
        return True

    def action_cancel(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được hủy hồ sơ đã ghi sổ.'))
        for rec in self.filtered(lambda r: r.state == 'posted'):
            move = self.env['lfood.move']._active_for(rec)
            if move:
                move._reverse(memo=_('Hủy %s') % rec.name)
            rec.with_context(lfood_benefit_system=True).write({'state': 'cancel'})
        return True
