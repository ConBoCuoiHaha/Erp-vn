"""Nhân sự: hợp đồng lao động, chấm công, làm thêm giờ, nghỉ phép; nối sang bảng lương.

Căn cứ và công thức ở hr_calc.py. Số ngày công và tiền làm thêm trên phiếu lương lấy từ chấm công
khi nhân viên có chấm công trong kỳ; nhân viên chưa chấm công thì bảng lương giữ cách tính cũ theo
ngày công chuẩn.
"""
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd
from .hr_calc import annual_leave, hourly_rate, overtime_pay, overtime_warnings, contract_months

PROBATION_LEVELS = [('manager', 'Người quản lý doanh nghiệp'),
                    ('college', 'Cần trình độ cao đẳng trở lên'),
                    ('intermediate', 'Trung cấp, công nhân kỹ thuật, nhân viên nghiệp vụ'),
                    ('other', 'Công việc khác')]
PROBATION_PARAMS = {'manager': 'THU_VIEC_QUAN_LY', 'college': 'THU_VIEC_CAO_DANG',
                    'intermediate': 'THU_VIEC_TRUNG_CAP', 'other': 'THU_VIEC_KHAC'}
LEAVE_CONDITIONS = [('normal', 'Điều kiện bình thường'), ('heavy', 'Nặng nhọc, độc hại, nguy hiểm; chưa thành niên; khuyết tật'),
                    ('special', 'Đặc biệt nặng nhọc, độc hại, nguy hiểm')]
LEAVE_PARAMS = {'normal': 'PHEP_NAM_BINH_THUONG', 'heavy': 'PHEP_NAM_NANG_NHOC', 'special': 'PHEP_NAM_DAC_BIET'}
LEAVE_KINDS = [('annual', 'Nghỉ phép năm'), ('paid', 'Nghỉ việc riêng có hưởng lương'),
               ('unpaid', 'Nghỉ không hưởng lương'), ('sick', 'Nghỉ ốm, thai sản hưởng BHXH')]


def param(env, code, at):
    return env['lfood.legal.param'].get_value(code, at)


class LfoodEmployee(models.Model):
    _inherit = 'lfood.employee'

    contract_ids = fields.One2many('lfood.hr.contract', 'employee_id', 'Hợp đồng lao động')
    contract_id = fields.Many2one('lfood.hr.contract', 'Hợp đồng đang hiệu lực', compute='_compute_contract')
    leave_condition = fields.Selection(LEAVE_CONDITIONS, 'Điều kiện làm việc tính phép năm', default='normal',
                                       required=True)
    leave_entitled = fields.Float('Phép năm nay', digits=(6, 1), compute='_compute_leave')
    leave_taken = fields.Float('Đã nghỉ phép năm nay', digits=(6, 1), compute='_compute_leave')
    leave_remaining = fields.Float('Phép còn lại', digits=(6, 1), compute='_compute_leave')

    def _compute_contract(self):
        for rec in self:
            rec.contract_id = rec.contract_ids.filtered(lambda c: c.state == 'running')[:1]

    def _leave_balance(self, year):
        self.ensure_one()
        at = date(year, 12, 31)
        base = param(self.env, LEAVE_PARAMS[self.leave_condition or 'normal'], at)
        step = int(param(self.env, 'PHEP_NAM_BUOC_THAM_NIEN', at))
        entitled = annual_leave(base, self.date_start, year, step)
        taken = sum(self.env['lfood.hr.leave'].search([
            ('employee_id', '=', self.id), ('kind', '=', 'annual'), ('state', '=', 'approved'),
            ('date_from', '>=', date(year, 1, 1)), ('date_from', '<=', at)]).mapped('days'))
        return entitled, taken

    def _compute_leave(self):
        year = fields.Date.context_today(self).year
        for rec in self:
            entitled, taken = rec._leave_balance(year) if rec.id else (0.0, 0.0)
            rec.leave_entitled, rec.leave_taken, rec.leave_remaining = entitled, taken, entitled - taken


class LfoodHrContract(models.Model):
    _name = 'lfood.hr.contract'
    _description = 'Hợp đồng lao động'
    _order = 'date_start desc, id desc'

    name = fields.Char('Số hợp đồng', default='/', readonly=True, copy=False, index=True)
    employee_id = fields.Many2one('lfood.employee', 'Nhân viên', required=True, index=True, ondelete='restrict')
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    kind = fields.Selection([('probation', 'Hợp đồng thử việc'), ('definite', 'Xác định thời hạn'),
                             ('indefinite', 'Không xác định thời hạn')], 'Loại hợp đồng', required=True,
                            default='definite')
    probation_level = fields.Selection(PROBATION_LEVELS, 'Tính chất công việc thử việc', default='other')
    job = fields.Char('Chức danh')
    date_start = fields.Date('Ngày bắt đầu', required=True, default=fields.Date.context_today)
    date_end = fields.Date('Ngày kết thúc')
    salary = fields.Float('Mức lương', digits=(16, 0), required=True)
    official_salary = fields.Float('Lương chính thức của công việc', digits=(16, 0),
                                   help='Chỉ dùng cho hợp đồng thử việc để kiểm tra mức tối thiểu')
    insurance_salary = fields.Float('Tiền lương đóng bảo hiểm', digits=(16, 0))
    state = fields.Selection([('draft', 'Nháp'), ('running', 'Đang hiệu lực'), ('closed', 'Đã kết thúc'),
                              ('cancel', 'Đã hủy')], 'Trạng thái', default='draft', required=True, readonly=True,
                             copy=False, index=True)
    note = fields.Text('Ghi chú')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('lfood.hr.contract') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_hr_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái hợp đồng chỉ đổi bằng các nút trên màn hình.'))
            if self.filtered(lambda r: r.state != 'draft') and set(vals) - {'note'}:
                raise UserError(_('Hợp đồng đã hiệu lực không sửa được. Ký phụ lục hoặc hợp đồng mới.'))
        return super().write(vals)

    def _check_rules(self):
        for rec in self:
            at = rec.date_start
            if rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_('Ngày kết thúc hợp đồng phải sau ngày bắt đầu.'))
            if rec.kind == 'definite':
                limit = int(param(self.env, 'HD_XAC_DINH_TOI_DA_THANG', at))
                if not rec.date_end:
                    raise ValidationError(_('Hợp đồng xác định thời hạn phải có ngày kết thúc.'))
                if contract_months(rec.date_start, rec.date_end) > limit:
                    raise ValidationError(_('Hợp đồng xác định thời hạn không quá %s tháng (Bộ luật Lao động 2019, Điều 20).')
                                          % limit)
            if rec.kind == 'probation':
                if not rec.date_end:
                    raise ValidationError(_('Hợp đồng thử việc phải có ngày kết thúc.'))
                max_days = int(param(self.env, PROBATION_PARAMS[rec.probation_level or 'other'], at))
                days = (rec.date_end - rec.date_start).days + 1
                if days > max_days:
                    raise ValidationError(_('Thời gian thử việc %s ngày vượt mức tối đa %s ngày cho %s '
                                            '(Bộ luật Lao động 2019, Điều 25).')
                                          % (days, max_days, dict(PROBATION_LEVELS)[rec.probation_level].lower()))
                ratio = param(self.env, 'THU_VIEC_TY_LE_LUONG', at)
                if not rec.official_salary:
                    raise ValidationError(_('Nhập lương chính thức của công việc để kiểm tra lương thử việc.'))
                if rec.salary < rec.official_salary * ratio / 100 - 0.5:
                    raise ValidationError(_('Lương thử việc %s thấp hơn %s%% lương chính thức %s '
                                            '(Bộ luật Lao động 2019, Điều 26).')
                                          % (vnd(rec.salary), '%g' % ratio, vnd(rec.official_salary)))

    def action_activate(self):
        """Hợp đồng có hiệu lực: kết thúc hợp đồng cũ, cập nhật lương vào hồ sơ tính lương."""
        basic = self.env.ref('lfood_payroll.comp_basic')
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ cho hiệu lực hợp đồng đang ở trạng thái Nháp.'))
            rec._check_rules()
            rec.employee_id.contract_ids.filtered(lambda c: c.state == 'running' and c != rec).with_context(
                lfood_hr_system=True).write({'state': 'closed'})
            rec.with_context(lfood_hr_system=True).write({'state': 'running'})
            emp = rec.employee_id
            vals = {}
            if rec.kind in ('definite', 'indefinite'):
                vals['contract_type'] = rec.kind
            if rec.insurance_salary:
                vals['insurance_salary'] = rec.insurance_salary
            if not emp.date_start:
                vals['date_start'] = rec.date_start
            if vals:
                emp.write(vals)
            line = emp.component_line_ids.filtered(lambda l: l.component_id == basic)
            if line:
                line.write({'amount': rec.salary})
            else:
                emp.write({'component_line_ids': [(0, 0, {'component_id': basic.id, 'amount': rec.salary})]})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Hợp đồng %s của %s có hiệu lực từ %s, lương %s')
                        % (rec.name, emp.name, rec.date_start.strftime('%d/%m/%Y'), vnd(rec.salary)))
        return True

    def action_close(self):
        self.filtered(lambda r: r.state == 'running').with_context(lfood_hr_system=True).write({'state': 'closed'})
        return True

    def action_cancel(self):
        self.filtered(lambda r: r.state == 'draft').with_context(lfood_hr_system=True).write({'state': 'cancel'})
        return True

    @api.model
    def _expiring(self, days=30):
        """Hợp đồng sắp hết hạn trong số ngày tới, để nhắc ký tiếp."""
        today = fields.Date.context_today(self)
        return self.search([('state', '=', 'running'), ('date_end', '!=', False),
                            ('date_end', '>=', today), ('date_end', '<=', fields.Date.add(today, days=days))])


class LfoodHrLeave(models.Model):
    _name = 'lfood.hr.leave'
    _description = 'Đơn nghỉ'
    _order = 'date_from desc, id desc'

    employee_id = fields.Many2one('lfood.employee', 'Nhân viên', required=True, index=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    kind = fields.Selection(LEAVE_KINDS, 'Loại nghỉ', required=True, default='annual')
    date_from = fields.Date('Từ ngày', required=True, default=fields.Date.context_today, index=True)
    date_to = fields.Date('Đến ngày', required=True, default=fields.Date.context_today)
    days = fields.Float('Số ngày nghỉ', digits=(6, 1), required=True, default=1,
                        help='Số ngày làm việc thực nghỉ, không tính ngày nghỉ hằng tuần và ngày lễ')
    reason = fields.Char('Lý do')
    state = fields.Selection([('draft', 'Chờ duyệt'), ('approved', 'Đã duyệt'), ('refused', 'Từ chối')],
                             'Trạng thái', default='draft', required=True, readonly=True, copy=False, index=True)
    approved_by = fields.Many2one('res.users', 'Người duyệt', readonly=True, copy=False)

    @api.constrains('date_from', 'date_to', 'days')
    def _check_dates(self):
        for rec in self:
            if rec.date_to < rec.date_from:
                raise ValidationError(_('Ngày kết thúc nghỉ phải từ ngày bắt đầu trở đi.'))
            if rec.days <= 0 or rec.days > (rec.date_to - rec.date_from).days + 1:
                raise ValidationError(_('Số ngày nghỉ phải lớn hơn 0 và không vượt số ngày từ %s đến %s.')
                                      % (rec.date_from.strftime('%d/%m/%Y'), rec.date_to.strftime('%d/%m/%Y')))

    def write(self, vals):
        if not self.env.context.get('lfood_hr_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái đơn nghỉ chỉ đổi bằng nút Duyệt, Từ chối.'))
            if self.filtered(lambda r: r.state != 'draft'):
                raise UserError(_('Đơn nghỉ đã xử lý không sửa được.'))
        return super().write(vals)

    def action_approve(self):
        if not (self.env.user.has_group('lfood_base.group_chief_accountant')
                or self.env.user.has_group('lfood_base.group_director')):
            raise UserError(_('Chỉ Kế toán trưởng hoặc Giám đốc được duyệt đơn nghỉ.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if rec.kind == 'annual':
                entitled, taken = rec.employee_id._leave_balance(rec.date_from.year)
                if taken + rec.days > entitled + 1e-6:
                    raise UserError(_('%s còn %s ngày phép năm %s, đơn xin %s ngày.')
                                    % (rec.employee_id.name, '%g' % (entitled - taken), rec.date_from.year,
                                       '%g' % rec.days))
            rec.with_context(lfood_hr_system=True).write({'state': 'approved', 'approved_by': self.env.uid})
        return True

    def action_refuse(self):
        self.filtered(lambda r: r.state == 'draft').with_context(lfood_hr_system=True).write(
            {'state': 'refused', 'approved_by': self.env.uid})
        return True


class LfoodHrAttendance(models.Model):
    _name = 'lfood.hr.attendance'
    _description = 'Chấm công ngày'
    _order = 'date desc, employee_id'

    employee_id = fields.Many2one('lfood.employee', 'Nhân viên', required=True, index=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    date = fields.Date('Ngày', required=True, index=True, default=fields.Date.context_today)
    hours_normal = fields.Float('Giờ làm bình thường', digits=(6, 2), default=8)
    ot_normal = fields.Float('Làm thêm ngày thường', digits=(6, 2))
    ot_weekend = fields.Float('Làm thêm ngày nghỉ tuần', digits=(6, 2))
    ot_holiday = fields.Float('Làm thêm ngày lễ, tết', digits=(6, 2))
    night_hours = fields.Float('Giờ làm đêm trong giờ bình thường', digits=(6, 2))
    ot_night_hours = fields.Float('Giờ làm thêm vào ban đêm', digits=(6, 2),
                                  help='Phần giờ làm thêm rơi vào ban đêm, đã tính trong các cột làm thêm')
    note = fields.Char('Ghi chú')
    ot_total = fields.Float('Tổng giờ làm thêm', digits=(6, 2), compute='_compute_ot_total', store=True)

    _day_uniq = models.Constraint('unique(employee_id, date)', 'Nhân viên đã có dòng chấm công ngày này.')

    @api.depends('ot_normal', 'ot_weekend', 'ot_holiday')
    def _compute_ot_total(self):
        for rec in self:
            rec.ot_total = rec.ot_normal + rec.ot_weekend + rec.ot_holiday

    @api.constrains('hours_normal', 'ot_normal', 'ot_weekend', 'ot_holiday', 'night_hours', 'ot_night_hours', 'date')
    def _check_limits(self):
        """Chặn làm thêm vượt giới hạn theo ngày, tháng, năm (Bộ luật Lao động 2019, Điều 107)."""
        for rec in self:
            values = [rec.hours_normal, rec.ot_normal, rec.ot_weekend, rec.ot_holiday, rec.night_hours, rec.ot_night_hours]
            if any(v < 0 for v in values):
                raise ValidationError(_('Số giờ không được âm.'))
            if rec.ot_night_hours > rec.ot_total + 1e-6:
                raise ValidationError(_('Giờ làm thêm ban đêm không vượt tổng giờ làm thêm.'))
            at = rec.date
            normal_day = param(self.env, 'GIO_LAM_VIEC_NGAY', at)
            same = self.search([('employee_id', '=', rec.employee_id.id)])
            month = sum(same.filtered(lambda a: a.date.year == at.year and a.date.month == at.month).mapped('ot_total'))
            year = sum(same.filtered(lambda a: a.date.year == at.year).mapped('ot_total'))
            # ngày nghỉ tuần, lễ tết không có giờ bình thường: giới hạn theo ngày chỉ xét ngày làm việc thường
            day_ot = rec.ot_normal
            problems = overtime_warnings(day_ot, month, year, normal_day,
                                         param(self.env, 'GIOI_HAN_LAM_THEM_NGAY_PT', at),
                                         param(self.env, 'GIOI_HAN_LAM_THEM_THANG', at),
                                         param(self.env, 'GIOI_HAN_LAM_THEM_NAM', at))
            day_pct = '%g' % param(self.env, 'GIOI_HAN_LAM_THEM_NGAY_PT', at)
            month_cap = '%g' % param(self.env, 'GIOI_HAN_LAM_THEM_THANG', at)
            year_cap = '%g' % param(self.env, 'GIOI_HAN_LAM_THEM_NAM', at)
            messages = {'day': _('quá %s%% giờ làm việc bình thường trong ngày') % day_pct,
                        'month': _('tổng tháng %s giờ, quá %s giờ') % ('%g' % month, month_cap),
                        'year': _('tổng năm %s giờ, quá %s giờ') % ('%g' % year, year_cap)}
            if problems:
                raise ValidationError(_('%s ngày %s làm thêm %s (Bộ luật Lao động 2019, Điều 107).')
                                      % (rec.employee_id.name, at.strftime('%d/%m/%Y'),
                                         ', '.join(messages[p] for p in problems)))


class LfoodPayrollRun(models.Model):
    _inherit = 'lfood.payroll.run'

    def _apply_attendance(self):
        """Lấy ngày công, ngày nghỉ không lương và tiền làm thêm từ chấm công, nghỉ phép vào phiếu lương."""
        ot_comp = self.env.ref('lfood_payroll.comp_ot')
        basic = self.env.ref('lfood_payroll.comp_basic')
        Attendance = self.env['lfood.hr.attendance'].sudo()
        Leave = self.env['lfood.hr.leave'].sudo()
        for rec in self:
            at = rec.date_to
            factors = {'normal': param(self.env, 'LAM_THEM_NGAY_THUONG', at),
                       'weekend': param(self.env, 'LAM_THEM_NGHI_TUAN', at),
                       'holiday': param(self.env, 'LAM_THEM_LE_TET', at)}
            hours_day = param(self.env, 'GIO_LAM_VIEC_NGAY', at)
            for slip in rec.slip_ids:
                emp = slip.employee_id
                days = Attendance.search([('employee_id', '=', emp.id), ('date', '>=', rec.date_from),
                                          ('date', '<=', rec.date_to)])
                if not days:
                    continue
                # ponytail: đơn nghỉ tính trọn vào tháng của ngày bắt đầu nghỉ; đơn kéo dài qua tháng thì tách đơn
                leaves = Leave.search([('employee_id', '=', emp.id), ('state', '=', 'approved'),
                                       ('date_from', '>=', rec.date_from), ('date_from', '<=', rec.date_to)])
                paid_leave = sum(leaves.filtered(lambda l: l.kind in ('annual', 'paid')).mapped('days'))
                unpaid = sum(leaves.filtered(lambda l: l.kind in ('unpaid', 'sick')).mapped('days'))
                worked = sum(days.mapped('hours_normal')) / hours_day if hours_day else 0
                salary = emp.contract_id.salary or sum(
                    emp.component_line_ids.filtered(lambda l: l.component_id == basic).mapped('amount'))
                rate = hourly_rate(salary, rec.standard_days, hours_day)
                pay = overtime_pay(rate, {'normal': sum(days.mapped('ot_normal')),
                                          'weekend': sum(days.mapped('ot_weekend')),
                                          'holiday': sum(days.mapped('ot_holiday'))}, factors,
                                   night_hours=sum(days.mapped('night_hours')),
                                   night_extra=param(self.env, 'LAM_DEM_THEM', at),
                                   ot_night_hours=sum(days.mapped('ot_night_hours')),
                                   ot_night_extra=param(self.env, 'LAM_THEM_DEM_THEM', at))
                slip.write({'worked_days': round(worked + paid_leave, 2), 'unpaid_days': unpaid})
                line = slip.line_ids.filtered(lambda l: l.component_id == ot_comp)
                if pay and line:
                    line.write({'amount': pay})
                elif pay:
                    slip.write({'line_ids': [(0, 0, {'component_id': ot_comp.id, 'amount': pay})]})
        return True

    def action_load_employees(self):
        res = super().action_load_employees()
        self._apply_attendance()
        self.action_compute()
        return res
