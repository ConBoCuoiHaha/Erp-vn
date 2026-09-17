"""Hồ sơ nhân sự: phòng ban, chức danh (DM10); điều chuyển, điều chỉnh lương (NSU13); khen thưởng, kỷ luật (NSU12).

Bộ luật Lao động 2019:
- Điều 29: tạm chuyển làm công việc khác khi khó khăn đột xuất hoặc nhu cầu sản xuất kinh doanh, không quá 60 ngày làm
  việc cộng dồn trong 1 năm (quá thì phải được người lao động đồng ý bằng văn bản), báo trước ít nhất 3 ngày làm việc,
  lương công việc mới ít nhất 85% lương cũ và không thấp hơn lương tối thiểu; lương mới thấp hơn thì giữ lương cũ
  30 ngày làm việc. Thay đổi lâu dài công việc, lương phải thỏa thuận (phụ lục hợp đồng, Điều 22, 33).
- Điều 122-125: xử lý kỷ luật phải có sự tham gia của tổ chức đại diện người lao động, người lao động có mặt; thời hiệu
  6 tháng (12 tháng nếu vi phạm liên quan trực tiếp tài chính, tài sản, bí mật); hình thức khiển trách, kéo dài thời hạn
  nâng lương không quá 6 tháng, cách chức, sa thải (chỉ trong các trường hợp Điều 125). Điều 127: cấm phạt tiền,
  cắt lương thay việc xử lý kỷ luật.
"""
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd

DISMISS_REASONS = [
    ('theft', 'Trộm cắp, tham ô, đánh bạc, cố ý gây thương tích, sử dụng ma túy tại nơi làm việc'),
    ('secret', 'Tiết lộ bí mật kinh doanh, công nghệ, xâm phạm sở hữu trí tuệ; gây thiệt hại đặc biệt nghiêm trọng'),
    ('harass', 'Quấy rối tình dục tại nơi làm việc theo nội quy'),
    ('repeat', 'Tái phạm khi đang bị kéo dài thời hạn nâng lương hoặc cách chức'),
    ('absent', 'Tự ý bỏ việc 05 ngày cộng dồn trong 30 ngày hoặc 20 ngày cộng dồn trong 365 ngày không có lý do chính đáng'),
]


def _param(env, code, at, default):
    return env['lfood.legal.param'].get_value(code, at, default=default)


class LfoodDepartment(models.Model):
    _name = 'lfood.department'
    _description = 'Phòng ban'
    _order = 'code'

    code = fields.Char('Mã', required=True)
    name = fields.Char('Tên phòng ban', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    parent_id = fields.Many2one('lfood.department', 'Thuộc')
    manager_id = fields.Many2one('lfood.employee', 'Trưởng bộ phận')
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục chi phí mặc định')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique(company_id, code)', 'Mã phòng ban đã tồn tại.')


class LfoodJobPosition(models.Model):
    _name = 'lfood.job.position'
    _description = 'Chức danh'
    _order = 'name'

    name = fields.Char('Chức danh', required=True)
    probation_level = fields.Selection([
        ('manager', 'Quản lý doanh nghiệp'), ('college', 'Cao đẳng trở lên'),
        ('intermediate', 'Trung cấp, công nhân kỹ thuật, nhân viên nghiệp vụ'), ('other', 'Công việc khác')],
        string='Tính chất công việc thử việc', default='other')
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint('unique(name)', 'Chức danh đã tồn tại.')


class LfoodEmployee(models.Model):
    _inherit = 'lfood.employee'

    department_id = fields.Many2one('lfood.department', 'Phòng ban', index=True)
    job_id = fields.Many2one('lfood.job.position', 'Chức danh (danh mục)')

    @api.onchange('department_id')
    def _onchange_department(self):
        if self.department_id:
            self.department = self.department_id.name
            self.cost_item_id = self.department_id.cost_item_id or self.cost_item_id

    @api.onchange('job_id')
    def _onchange_job(self):
        if self.job_id:
            self.job = self.job_id.name

    def _basic_salary(self):
        self.ensure_one()
        basic = self.env.ref('lfood_payroll.comp_basic')
        return sum(self.component_line_ids.filtered(lambda l: l.component_id == basic).mapped('amount'))


class LfoodHrTransfer(models.Model):
    _name = 'lfood.hr.transfer'
    _description = 'Điều chuyển, điều chỉnh lương'
    _order = 'date_from desc, id desc'

    name = fields.Char('Số', default='/', readonly=True, copy=False, index=True)
    employee_id = fields.Many2one('lfood.employee', 'Nhân viên', required=True, index=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    kind = fields.Selection([('temporary', 'Tạm chuyển làm công việc khác (Điều 29)'),
                             ('permanent', 'Điều chuyển, bổ nhiệm, điều chỉnh lương theo thỏa thuận')], 'Loại',
                            required=True, default='temporary')
    reason = fields.Char('Lý do', required=True)
    notice_date = fields.Date('Ngày thông báo')
    date_from = fields.Date('Từ ngày', required=True)
    date_to = fields.Date('Đến ngày')
    work_days = fields.Integer('Số ngày làm việc', compute='_compute_work_days', store=True)
    old_department_id = fields.Many2one('lfood.department', 'Phòng ban cũ', readonly=True)
    old_job = fields.Char('Công việc cũ', readonly=True)
    old_salary = fields.Float('Lương cũ', digits=(16, 0), readonly=True)
    new_department_id = fields.Many2one('lfood.department', 'Phòng ban mới')
    new_job_id = fields.Many2one('lfood.job.position', 'Chức danh mới')
    new_job = fields.Char('Công việc mới', required=True)
    new_salary = fields.Float('Lương công việc mới', digits=(16, 0), required=True)
    consent = fields.Boolean('Người lao động đồng ý bằng văn bản')
    consent_file = fields.Binary('Văn bản đồng ý, phụ lục hợp đồng', attachment=True)
    consent_name = fields.Char()
    keep_old_until = fields.Date('Giữ lương cũ đến', compute='_compute_work_days', store=True)
    state = fields.Selection([('draft', 'Nháp'), ('done', 'Đã thực hiện'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)

    @api.depends('date_from', 'date_to', 'new_salary', 'old_salary', 'kind')
    def _compute_work_days(self):
        Hol = self.env['lfood.holiday']
        for rec in self:
            rec.work_days = Hol.working_days_between(rec.date_from - relativedelta(days=1),
                                                     rec.date_to + relativedelta(days=1)) \
                if rec.date_from and rec.date_to else 0
            rec.keep_old_until = Hol.add_working_days(rec.date_from - relativedelta(days=1), 30) \
                if rec.kind == 'temporary' and rec.date_from and rec.new_salary < rec.old_salary else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('lfood.hr.transfer') or '/'
            emp = self.env['lfood.employee'].browse(vals.get('employee_id'))
            vals.setdefault('old_department_id', emp.department_id.id)
            vals.setdefault('old_job', emp.job)
            vals.setdefault('old_salary', emp._basic_salary())
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_hr_system') and self.filtered(lambda r: r.state != 'draft'):
            raise UserError(_('Quyết định đã thực hiện không sửa được.'))
        return super().write(vals)

    def _check_rules(self):
        self.ensure_one()
        at = self.date_from
        region_min = _param(self.env, 'LUONG_TOI_THIEU_VUNG_%s' % self.employee_id.region, at, 0)
        if region_min and self.new_salary < region_min:
            raise ValidationError(_('Lương mới %s thấp hơn lương tối thiểu vùng %s.') % (vnd(self.new_salary), vnd(region_min)))
        if self.kind == 'permanent':
            if not (self.consent and self.consent_file):
                raise ValidationError(_('Điều chuyển, điều chỉnh lương lâu dài phải có thỏa thuận (phụ lục hợp đồng) '
                                        'với người lao động, đính kèm văn bản.'))
            return
        if not self.date_to:
            raise ValidationError(_('Tạm chuyển công việc phải có ngày kết thúc.'))
        notice = int(_param(self.env, 'DIEU_CHUYEN_BAO_TRUOC', at, 3))
        if not self.notice_date or self.env['lfood.holiday'].working_days_between(
                self.notice_date - relativedelta(days=1), self.date_from) < notice:
            raise ValidationError(_('Phải báo trước ít nhất %s ngày làm việc (Điều 29).') % notice)
        ratio = _param(self.env, 'DIEU_CHUYEN_TY_LE_LUONG', at, 85)
        if self.new_salary < self.old_salary * ratio / 100 - 0.5:
            raise ValidationError(_('Lương công việc mới phải ít nhất %s%% lương cũ (%s).') % (
                '%g' % ratio, vnd(self.old_salary * ratio / 100)))
        limit = int(_param(self.env, 'DIEU_CHUYEN_TOI_DA_NGAY', at, 60))
        used = sum(self.search([('employee_id', '=', self.employee_id.id), ('kind', '=', 'temporary'),
                                ('state', '=', 'done'), ('id', '!=', self.id),
                                ('date_from', '>=', at.replace(month=1, day=1)),
                                ('date_from', '<=', at.replace(month=12, day=31))]).mapped('work_days'))
        if used + self.work_days > limit and not (self.consent and self.consent_file):
            raise ValidationError(_('Tổng thời gian tạm chuyển trong năm %s ngày làm việc vượt %s ngày: '
                                    'cần văn bản đồng ý của người lao động.') % (used + self.work_days, limit))

    def action_done(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            rec._check_rules()
            emp = rec.employee_id
            vals = {'job': rec.new_job}
            if rec.new_department_id:
                vals.update({'department_id': rec.new_department_id.id, 'department': rec.new_department_id.name})
            if rec.new_job_id:
                vals['job_id'] = rec.new_job_id.id
            emp.write(vals)
            basic = self.env.ref('lfood_payroll.comp_basic')
            line = emp.component_line_ids.filtered(lambda l: l.component_id == basic)
            # tạm chuyển có lương mới thấp hơn: giữ lương cũ 30 ngày làm việc, kế toán đổi lương sau hạn giữ lương
            if rec.kind == 'permanent' or rec.new_salary >= rec.old_salary:
                if line:
                    line.write({'amount': rec.new_salary})
            rec.with_context(lfood_hr_system=True).write({'state': 'done'})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('%s: %s từ %s, công việc %s, lương %s -> %s') % (
                    rec.name, emp.name, rec.date_from.strftime('%d/%m/%Y'), rec.new_job, vnd(rec.old_salary),
                    vnd(rec.new_salary)))
        return True

    def action_cancel(self):
        self.filtered(lambda r: r.state == 'draft').with_context(lfood_hr_system=True).write({'state': 'cancel'})
        return True


class LfoodHrDiscipline(models.Model):
    _name = 'lfood.hr.discipline'
    _description = 'Xử lý kỷ luật lao động'
    _order = 'violation_date desc, id desc'

    name = fields.Char('Số', default='/', readonly=True, copy=False, index=True)
    employee_id = fields.Many2one('lfood.employee', 'Người lao động', required=True, index=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    violation_date = fields.Date('Ngày xảy ra vi phạm', required=True)
    violation = fields.Text('Hành vi vi phạm (theo nội quy)', required=True)
    finance_related = fields.Boolean('Liên quan trực tiếp tài chính, tài sản, bí mật công nghệ, kinh doanh')
    deadline = fields.Date('Hết thời hiệu', compute='_compute_deadline', store=True)
    meeting_date = fields.Date('Ngày họp xử lý')
    union_attended = fields.Boolean('Có tổ chức đại diện người lao động tham gia')
    employee_attended = fields.Boolean('Người lao động có mặt hoặc có người bào chữa')
    minutes = fields.Binary('Biên bản họp', attachment=True)
    minutes_name = fields.Char()
    form = fields.Selection([('reprimand', 'Khiển trách'), ('delay', 'Kéo dài thời hạn nâng lương'),
                             ('demote', 'Cách chức'), ('dismiss', 'Sa thải')], 'Hình thức', required=True,
                            default='reprimand')
    delay_months = fields.Integer('Số tháng kéo dài nâng lương')
    dismiss_reason = fields.Selection(DISMISS_REASONS, 'Trường hợp sa thải (Điều 125)')
    decision_ref = fields.Char('Số quyết định')
    decision_date = fields.Date('Ngày ra quyết định')
    state = fields.Selection([('draft', 'Nháp'), ('decided', 'Đã ra quyết định'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)

    @api.depends('violation_date', 'finance_related')
    def _compute_deadline(self):
        for rec in self:
            if not rec.violation_date:
                rec.deadline = False
                continue
            code = 'KY_LUAT_THOI_HIEU_TAI_CHINH_THANG' if rec.finance_related else 'KY_LUAT_THOI_HIEU_THANG'
            months = int(_param(self.env, code, rec.violation_date, 12 if rec.finance_related else 6))
            rec.deadline = rec.violation_date + relativedelta(months=months)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('lfood.hr.discipline') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_hr_system') and self.filtered(lambda r: r.state != 'draft'):
            raise UserError(_('Quyết định kỷ luật đã ban hành không sửa được.'))
        return super().write(vals)

    def action_decide(self):
        if not self.env.user.has_group('lfood_base.group_director'):
            raise UserError(_('Chỉ Giám đốc (người có thẩm quyền) ra quyết định kỷ luật.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not (rec.meeting_date and rec.minutes and rec.decision_ref and rec.decision_date):
                raise ValidationError(_('Cần ngày họp, biên bản họp, số và ngày quyết định.'))
            if not rec.union_attended:
                raise ValidationError(_('Cuộc họp xử lý kỷ luật phải có sự tham gia của tổ chức đại diện người lao động '
                                        '(Điều 122).'))
            if not rec.employee_attended:
                raise ValidationError(_('Người lao động phải có mặt hoặc có người bào chữa (Điều 122).'))
            if rec.decision_date > rec.deadline:
                raise ValidationError(_('Đã hết thời hiệu xử lý kỷ luật ngày %s (Điều 123).') % rec.deadline.strftime('%d/%m/%Y'))
            if rec.form == 'delay' and not 0 < rec.delay_months <= 6:
                raise ValidationError(_('Kéo dài thời hạn nâng lương không quá 6 tháng (Điều 124).'))
            if rec.form == 'dismiss' and not rec.dismiss_reason:
                raise ValidationError(_('Sa thải chỉ áp dụng trong các trường hợp của Điều 125: chọn trường hợp.'))
            rec.with_context(lfood_hr_system=True).write({'state': 'decided'})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Quyết định kỷ luật %s: %s, hình thức %s') % (
                    rec.decision_ref, rec.employee_id.name, dict(self._fields['form'].selection)[rec.form]))
        return True

    def action_cancel(self):
        self.filtered(lambda r: r.state == 'draft').with_context(lfood_hr_system=True).write({'state': 'cancel'})
        return True


class LfoodHrReward(models.Model):
    _name = 'lfood.hr.reward'
    _description = 'Khen thưởng'
    _order = 'date desc, id desc'

    employee_id = fields.Many2one('lfood.employee', 'Người lao động', required=True, index=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    date = fields.Date('Ngày', required=True, default=fields.Date.context_today)
    reason = fields.Char('Thành tích', required=True)
    decision_ref = fields.Char('Số quyết định')
    amount = fields.Float('Tiền thưởng', digits=(16, 0),
                          help='Đưa vào bảng lương kỳ trả bằng khoản thưởng để tính thuế TNCN, bảo hiểm')
