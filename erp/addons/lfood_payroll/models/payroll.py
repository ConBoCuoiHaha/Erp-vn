import calendar
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd
from .calc import compute_slip

REGIONS = [('I', 'Vùng I'), ('II', 'Vùng II'), ('III', 'Vùng III'), ('IV', 'Vùng IV')]
COST_ACCOUNTS = [('622', '622 Nhân công trực tiếp'), ('6271', '6271 Nhân viên phân xưởng'),
                 ('6411', '6411 Nhân viên bán hàng'), ('6421', '6421 Nhân viên quản lý')]


class LfoodEmployee(models.Model):
    _name = 'lfood.employee'
    _description = 'Nhân viên'
    _order = 'code'
    _rec_names_search = ['code', 'name']

    code = fields.Char('Mã nhân viên', required=True, index=True)
    name = fields.Char('Họ và tên', required=True)
    partner_id = fields.Many2one('res.partner', 'Đối tượng công nợ', readonly=True, copy=False)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    department = fields.Char('Bộ phận')
    job = fields.Char('Chức danh')
    tax_code = fields.Char('Mã số thuế cá nhân')
    id_number = fields.Char('Số định danh cá nhân', groups='lfood_base.group_chief_accountant')
    social_insurance_code = fields.Char('Mã số BHXH')
    bank_account = fields.Char('Tài khoản ngân hàng')
    date_start = fields.Date('Ngày vào làm')
    date_end = fields.Date('Ngày nghỉ việc')
    contract_type = fields.Selection([('indefinite', 'Không xác định thời hạn'), ('definite', 'Xác định thời hạn'),
                                      ('short', 'Dưới 03 tháng hoặc không có hợp đồng lao động')], 'Loại hợp đồng',
                                     required=True, default='indefinite')
    resident = fields.Boolean('Cá nhân cư trú', default=True)
    region = fields.Selection(REGIONS, 'Vùng lương tối thiểu nơi làm việc', required=True, default='III')
    cost_account = fields.Selection(COST_ACCOUNTS, 'TK chi phí lương', required=True, default='6421')
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP')
    insurance_enrolled = fields.Boolean('Tham gia BHXH, BHYT bắt buộc', default=True,
                                        help='Kế toán, nhân sự xác định theo loại và thời hạn hợp đồng theo Luật Bảo hiểm xã hội')
    unemployment_enrolled = fields.Boolean('Tham gia BHTN', default=True)
    insurance_salary = fields.Float('Tiền lương làm căn cứ đóng bảo hiểm', digits=(16, 0),
                                    help='Lương, phụ cấp lương và các khoản bổ sung khác theo hợp đồng lao động')
    dependents = fields.Integer('Số người phụ thuộc đã đăng ký')
    component_line_ids = fields.One2many('lfood.employee.component', 'employee_id', 'Khoản lương cố định')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique(company_id, code)', 'Mã nhân viên đã tồn tại.')

    def _dependents_in(self, date_from, date_to):
        """Số người phụ thuộc được giảm trừ trong kỳ lương; phân hệ hồ sơ người phụ thuộc ghi đè."""
        self.ensure_one()
        return self.dependents

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s %s' % (rec.code, rec.name) if rec.code else rec.name

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        for emp in employees:
            emp.partner_id = self.env['res.partner'].sudo().create({'name': emp.name, 'ref': emp.code, 'company_id': emp.company_id.id})
        return employees


class LfoodPayrollComponent(models.Model):
    _name = 'lfood.payroll.component'
    _description = 'Khoản lương'
    _order = 'sequence, code'

    sequence = fields.Integer(default=10)
    code = fields.Char('Mã', required=True)
    name = fields.Char('Tên khoản', required=True)
    kind = fields.Selection([('earning', 'Thu nhập'), ('deduction', 'Khấu trừ')], 'Loại', required=True, default='earning')
    taxable = fields.Boolean('Tính thu nhập chịu thuế TNCN', default=True,
                             help='Bỏ chọn cho khoản được miễn hoặc không tính vào thu nhập chịu thuế theo quy định; kế toán trưởng chịu trách nhiệm xác định')
    prorate = fields.Boolean('Tính theo ngày công', default=False)
    pit_exempt_code = fields.Char('Mã tham số miễn thuế TNCN',
                                  help='Mã tham số pháp lý; kỳ lương nào tham số này có giá trị 1 thì khoản không tính '
                                       'vào thu nhập chịu thuế, giá trị 0 hoặc chưa có hiệu lực thì theo ô Tính thu nhập chịu thuế')
    deduction_account = fields.Char('TK ghi Có khi khấu trừ', default='141', help='Ví dụ 141 trừ tạm ứng, 1388 trừ khoản phải thu khác')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique(code)', 'Mã khoản lương đã tồn tại.')

    def _is_taxable(self, at):
        """Khoản có tính vào thu nhập chịu thuế TNCN tại kỳ lương này không."""
        self.ensure_one()
        if self.pit_exempt_code and self.env['lfood.legal.param'].get_value(self.pit_exempt_code, at, default=0) == 1:
            return False
        return self.taxable


class LfoodEmployeeComponent(models.Model):
    _name = 'lfood.employee.component'
    _description = 'Khoản lương cố định của nhân viên'

    employee_id = fields.Many2one('lfood.employee', required=True, ondelete='cascade', index=True)
    component_id = fields.Many2one('lfood.payroll.component', 'Khoản', required=True)
    amount = fields.Float('Số tiền tháng', digits=(16, 0))


class LfoodPayrollRun(models.Model):
    _name = 'lfood.payroll.run'
    _description = 'Bảng lương tháng'
    _order = 'date_to desc, id desc'

    name = fields.Char('Bảng lương', compute='_compute_period', store=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    year = fields.Integer('Năm', required=True, default=lambda s: fields.Date.context_today(s).year)
    month = fields.Integer('Tháng', required=True, default=lambda s: fields.Date.context_today(s).month)
    date_from = fields.Date('Từ ngày', compute='_compute_period', store=True)
    date_to = fields.Date('Đến ngày', compute='_compute_period', store=True)
    standard_days = fields.Float('Ngày công chuẩn', default=26, required=True)
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ'), ('paid', 'Đã chi lương')], 'Trạng thái',
                             default='draft', readonly=True, copy=False, index=True)
    slip_ids = fields.One2many('lfood.payroll.slip', 'run_id', 'Phiếu lương')
    total_gross = fields.Float('Tổng thu nhập', digits=(16, 0), compute='_compute_totals')
    total_net = fields.Float('Tổng thực lĩnh', digits=(16, 0), compute='_compute_totals')
    total_pit = fields.Float('Thuế TNCN khấu trừ', digits=(16, 0), compute='_compute_totals')
    total_employer = fields.Float('Doanh nghiệp đóng BH, KPCĐ', digits=(16, 0), compute='_compute_totals')
    pay_date = fields.Date('Ngày chi lương', copy=False)
    pay_method = fields.Selection([('bank', 'Chuyển khoản'), ('cash', 'Tiền mặt')], 'Hình thức chi', default='bank')

    _period_uniq = models.Constraint('unique(company_id, year, month)', 'Đã có bảng lương tháng này.')

    @api.depends('year', 'month')
    def _compute_period(self):
        for rec in self:
            m = min(max(rec.month or 1, 1), 12)
            rec.date_from = date(rec.year, m, 1)
            rec.date_to = date(rec.year, m, calendar.monthrange(rec.year, m)[1])
            rec.name = _('Bảng lương tháng %02d/%s') % (m, rec.year)

    @api.depends('slip_ids.gross', 'slip_ids.net', 'slip_ids.pit', 'slip_ids.co_si', 'slip_ids.co_hi', 'slip_ids.co_ui', 'slip_ids.co_union')
    def _compute_totals(self):
        for rec in self:
            rec.total_gross = sum(rec.slip_ids.mapped('gross'))
            rec.total_net = sum(rec.slip_ids.mapped('net'))
            rec.total_pit = sum(rec.slip_ids.mapped('pit'))
            rec.total_employer = sum(rec.slip_ids.mapped(lambda s: s.co_si + s.co_hi + s.co_ui + s.co_union))

    def write(self, vals):
        if not self.env.context.get('lfood_payroll_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái bảng lương chỉ đổi bằng nút Ghi sổ, Chi lương, Hủy.'))
            if self.filtered(lambda r: r.state != 'draft') and set(vals) - {'pay_date', 'pay_method'}:
                raise UserError(_('Bảng lương đã ghi sổ không sửa được. Hủy ghi sổ rồi sửa.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda r: r.state != 'draft'):
            raise UserError(_('Bảng lương đã ghi sổ không xóa được.'))
        return super().unlink()

    # ------------------------------------------------------------ tham số theo ngày
    def _params(self):
        P, d = self.env['lfood.legal.param'], self.date_to
        g = lambda code: P.get_value(code, d)
        return {
            'reference_wage': g('LUONG_CO_SO'),
            'min_wage': {'I': g('LUONG_TOI_THIEU_VUNG_I'), 'II': g('LUONG_TOI_THIEU_VUNG_II'),
                         'III': g('LUONG_TOI_THIEU_VUNG_III'), 'IV': g('LUONG_TOI_THIEU_VUNG_IV')},
            'cap_multiplier_si': g('HE_SO_TRAN_BHXH'), 'cap_multiplier_ui': g('HE_SO_TRAN_BHTN'),
            'rates': {'emp_si': g('BHXH_NLD'), 'emp_hi': g('BHYT_NLD'), 'emp_ui': g('BHTN_NLD'),
                      'co_sickness': g('BHXH_DN_OM_DAU_THAI_SAN'), 'co_retirement': g('BHXH_DN_HUU_TRI_TU_TUAT'),
                      'co_accident': g('BHXH_DN_TNLD_BNN'), 'co_hi': g('BHYT_DN'), 'co_ui': g('BHTN_DN'), 'union': g('TY_LE_KPCD')},
            'self_deduction': g('TNCN_GIAM_TRU_BAN_THAN'), 'dependent_deduction': g('TNCN_GIAM_TRU_NPT'),
            'brackets': [(g('TNCN_BAC_1_DEN'), g('TNCN_THUE_SUAT_1')), (g('TNCN_BAC_2_DEN'), g('TNCN_THUE_SUAT_2')),
                         (g('TNCN_BAC_3_DEN'), g('TNCN_THUE_SUAT_3')), (g('TNCN_BAC_4_DEN'), g('TNCN_THUE_SUAT_4')),
                         (None, g('TNCN_THUE_SUAT_5'))],
        }

    # ------------------------------------------------------------ nghiệp vụ
    def action_load_employees(self):
        self._require('lfood_base.group_accountant')
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ lấy nhân viên cho bảng lương Nháp.'))
            existing = rec.slip_ids.employee_id
            emps = self.env['lfood.employee'].search([('company_id', '=', rec.company_id.id), ('active', '=', True),
                                                      ('id', 'not in', existing.ids),
                                                      '|', ('date_start', '=', False), ('date_start', '<=', rec.date_to),
                                                      '|', ('date_end', '=', False), ('date_end', '>=', rec.date_from)])
            for emp in emps:
                self.env['lfood.payroll.slip'].create({
                    'run_id': rec.id, 'employee_id': emp.id, 'worked_days': rec.standard_days,
                    'line_ids': [(0, 0, {'component_id': c.component_id.id, 'amount': c.amount}) for c in emp.component_line_ids],
                })
            rec._load_extras()
            rec.action_compute()
        return True

    def _load_extras(self):
        """Phân hệ khác thêm dòng vào phiếu lương (tạm ứng lương, thưởng)."""
        return True

    def action_load_extras(self):
        self._require('lfood_base.group_accountant')
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ lấy dữ liệu cho bảng lương Nháp.'))
            rec._load_extras()
            rec.action_compute()
        return True

    def action_compute(self):
        self._require('lfood_base.group_accountant')
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Bảng lương đã ghi sổ không tính lại được.'))
            params = rec._params()
            for slip in rec.slip_ids:
                slip._compute_values(params)
        return True

    def _cost_extra(self, emp):
        """Giá trị bổ sung cho dòng chi phí lương, ví dụ đối tượng tính giá thành; phân hệ giá thành ghi đè."""
        return None

    def action_post(self):
        self._require('lfood_base.group_chief_accountant', _('Chỉ Kế toán trưởng được ghi sổ bảng lương.'))
        Move = self.env['lfood.move']
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.slip_ids:
                raise UserError(_('Bảng lương chưa có nhân viên.'))
            rec.action_compute()
            label = rec.name
            lines = []
            for s in rec.slip_ids:
                emp, partner = s.employee_id, s.employee_id.partner_id
                ci = emp.cost_item_id
                extra = rec._cost_extra(emp)
                lines += [(emp.cost_account, s.gross, 0, None, _('%s: %s') % (label, emp.name), ci, extra),
                          ('334', 0, s.gross, partner, _('Phải trả lương %s') % emp.name, None)]
                for acc, amount, what in (('3383', s.emp_si, 'BHXH'), ('3384', s.emp_hi, 'BHYT'), ('3386', s.emp_ui, 'BHTN')):
                    lines += [('334', amount, 0, partner, _('Trừ %s người lao động %s') % (what, emp.name), None),
                              (acc, 0, amount, None, _('%s người lao động %s') % (what, emp.name), None)]
                for acc, amount, what in (('3383', s.co_si, 'BHXH'), ('3384', s.co_hi, 'BHYT'), ('3386', s.co_ui, 'BHTN'),
                                          ('3382', s.co_union, 'KPCĐ')):
                    lines += [(emp.cost_account, amount, 0, None, _('%s doanh nghiệp đóng %s') % (what, emp.name), ci, extra),
                              (acc, 0, amount, None, _('%s doanh nghiệp đóng %s') % (what, emp.name), None)]
                lines += [('334', s.pit, 0, partner, _('Khấu trừ thuế TNCN %s') % emp.name, None),
                          ('3335', 0, s.pit, None, _('Thuế TNCN %s') % emp.name, None)]
                # khoản trừ ghi Nợ 334 lúc phát sinh (tạm ứng lương) thì không ghi lại
                for l in s.line_ids.filtered(lambda x: x.component_id.kind == 'deduction' and x.amount
                                             and x.component_id.deduction_account != '334'):
                    acc = l.component_id.deduction_account
                    track = self.env['lfood.account'].by_code(acc).track_partner
                    lines += [('334', l.amount, 0, partner, _('%s %s') % (l.component_id.name, emp.name), None),
                              (acc, 0, l.amount, partner if track else None, _('%s %s') % (l.component_id.name, emp.name), None)]
            Move._create_from_source(rec, 'general', rec.date_to, lines, memo=label, key='payroll', ref=rec.name)
            rec.with_context(lfood_payroll_system=True).write({'state': 'posted'})
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                                                      summary=_('Ghi sổ %s: %s nhân viên, thu nhập %s, thuế TNCN %s, thực lĩnh %s, doanh nghiệp đóng %s')
                                                      % (rec.name, len(rec.slip_ids), vnd(rec.total_gross), vnd(rec.total_pit),
                                                         vnd(rec.total_net), vnd(rec.total_employer)))
        return True

    def action_pay(self):
        self._require('lfood_base.group_accountant')
        Move = self.env['lfood.move']
        for rec in self.filtered(lambda r: r.state == 'posted'):
            pay_date = rec.pay_date or fields.Date.context_today(self)
            cash_acc = '111' if rec.pay_method == 'cash' else '112'
            lines = []
            for s in rec.slip_ids.filtered(lambda x: x.net > 0):
                lines += [('334', s.net, 0, s.employee_id.partner_id, _('Chi lương %s') % s.employee_id.name, None),
                          (cash_acc, 0, s.net, None, _('Chi lương %s') % s.employee_id.name, None)]
            Move._create_from_source(rec, 'bank' if rec.pay_method == 'bank' else 'cash', pay_date, lines,
                                     memo=_('Chi %s') % rec.name, key='pay', ref=rec.name)
            rec.with_context(lfood_payroll_system=True).write({'state': 'paid', 'pay_date': pay_date})
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                                                      summary=_('Chi %s: %s') % (rec.name, vnd(rec.total_net)))
        return True

    def action_reset(self):
        self._require('lfood_base.group_chief_accountant', _('Chỉ Kế toán trưởng được hủy ghi sổ bảng lương.'))
        for rec in self.filtered(lambda r: r.state != 'draft'):
            for move in self.env['lfood.move']._active_for(rec):
                move._reverse(memo=_('Hủy %s') % rec.name)
            rec.with_context(lfood_payroll_system=True).write({'state': 'draft'})
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=rec.name,
                                                      company_id=rec.company_id.id, summary=_('Hủy ghi sổ %s') % rec.name)
        return True

    def _require(self, group, message=None):
        if not self.env.user.has_group(group):
            raise UserError(message or _('Không đủ quyền.'))


class LfoodPayrollSlip(models.Model):
    _name = 'lfood.payroll.slip'
    _description = 'Phiếu lương'
    _order = 'run_id, employee_id'

    run_id = fields.Many2one('lfood.payroll.run', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='run_id.company_id', store=True)
    state = fields.Selection(related='run_id.state')
    employee_id = fields.Many2one('lfood.employee', 'Nhân viên', required=True, index=True)
    worked_days = fields.Float('Ngày công thực tế', digits=(6, 2))
    unpaid_days = fields.Float('Ngày không hưởng lương', digits=(6, 2))
    skip_insurance = fields.Boolean('Không đóng BH tháng này', help='Ví dụ nghỉ không lương cả tháng; ghi rõ lý do vào ghi chú')
    note = fields.Char('Ghi chú')
    line_ids = fields.One2many('lfood.payroll.slip.line', 'slip_id', 'Các khoản')
    gross = fields.Float('Tổng thu nhập', digits=(16, 0), readonly=True)
    taxable_income = fields.Float('Thu nhập chịu thuế', digits=(16, 0), readonly=True)
    si_base = fields.Float('Lương đóng BHXH, BHYT', digits=(16, 0), readonly=True)
    ui_base = fields.Float('Lương đóng BHTN', digits=(16, 0), readonly=True)
    emp_si = fields.Float('BHXH NLĐ', digits=(16, 0), readonly=True)
    emp_hi = fields.Float('BHYT NLĐ', digits=(16, 0), readonly=True)
    emp_ui = fields.Float('BHTN NLĐ', digits=(16, 0), readonly=True)
    co_si = fields.Float('BHXH DN', digits=(16, 0), readonly=True)
    co_hi = fields.Float('BHYT DN', digits=(16, 0), readonly=True)
    co_ui = fields.Float('BHTN DN', digits=(16, 0), readonly=True)
    co_union = fields.Float('KPCĐ DN', digits=(16, 0), readonly=True)
    family_deduction = fields.Float('Giảm trừ gia cảnh', digits=(16, 0), readonly=True)
    assessable = fields.Float('Thu nhập tính thuế', digits=(16, 0), readonly=True)
    pit = fields.Float('Thuế TNCN', digits=(16, 0), readonly=True)
    other_deductions = fields.Float('Khấu trừ khác', digits=(16, 0), readonly=True)
    net = fields.Float('Thực lĩnh', digits=(16, 0), readonly=True)
    warning = fields.Char('Cảnh báo', readonly=True)

    _employee_uniq = models.Constraint('unique(run_id, employee_id)', 'Nhân viên đã có phiếu lương trong bảng lương này.')

    def _compute_values(self, params):
        for s in self:
            ratio = (s.worked_days / s.run_id.standard_days) if s.run_id.standard_days else 1
            for l in s.line_ids:
                l.paid_amount = round(l.amount * ratio) if l.component_id.prorate else round(l.amount)
            r, warn = s._slip_result(params)
            s.write({k: r[k] for k in ('gross', 'si_base', 'ui_base', 'emp_si', 'emp_hi', 'emp_ui', 'co_si', 'co_hi', 'co_ui', 'co_union',
                                        'family_deduction', 'assessable', 'pit', 'other_deductions', 'net')}
                    | {'taxable_income': r['taxable_income'], 'warning': '; '.join(warn)})

    def _slip_result(self, params):
        """Tính một phiếu lương, không ghi (dùng cho tính lương và tính thử tham số)."""
        self.ensure_one()
        s = self
        emp, run = s.employee_id, s.run_id
        ratio = (s.worked_days / run.standard_days) if run.standard_days else 1
        earnings = s.line_ids.filtered(lambda l: l.component_id.kind == 'earning')
        paid = {l: round(l.amount * ratio) if l.component_id.prorate else round(l.amount) for l in s.line_ids}
        gross = sum(paid[l] for l in earnings)
        taxable = sum(paid[l] for l in earnings if l.component_id._is_taxable(run.date_to))
        deductions = sum(paid[l] for l in s.line_ids if l.component_id.kind == 'deduction')
        r = compute_slip({
            'insurance_salary': emp.insurance_salary, 'insurance_enrolled': emp.insurance_enrolled,
            'unemployment_enrolled': emp.unemployment_enrolled, 'skip_insurance': s.skip_insurance, 'unpaid_days': s.unpaid_days,
            'min_wage': params['min_wage'][emp.region], 'cap_multiplier_si': params['cap_multiplier_si'],
            'cap_multiplier_ui': params['cap_multiplier_ui'], 'reference_wage': params['reference_wage'], 'rates': params['rates'],
            'gross': gross, 'taxable_gross': taxable, 'self_deduction': params['self_deduction'],
            'dependent_deduction': params['dependent_deduction'], 'dependents': emp._dependents_in(run.date_from, run.date_to),
            'brackets': params['brackets'],
            'resident': emp.resident and emp.contract_type != 'short', 'other_deductions': deductions,
        })
        warn = []
        if emp.contract_type == 'short':
            warn.append(_('Hợp đồng dưới 03 tháng hoặc không có hợp đồng: app không tính thuế TNCN theo biểu lũy tiến, kế toán tự xác định mức khấu trừ'))
        if not emp.resident:
            warn.append(_('Cá nhân không cư trú: app không tính thuế, kế toán tự xác định'))
        if emp.insurance_enrolled and emp.insurance_salary < params['min_wage'][emp.region]:
            warn.append(_('Lương đóng bảo hiểm thấp hơn lương tối thiểu vùng, app đã đóng trên mức lương tối thiểu vùng'))
        if r['net'] < 0:
            warn.append(_('Thực lĩnh âm'))
        return r, warn

    def write(self, vals):
        if self.filtered(lambda s: s.run_id.state != 'draft') and not self.env.context.get('lfood_payroll_system'):
            raise UserError(_('Bảng lương đã ghi sổ không sửa được phiếu lương.'))
        return super().write(vals)


class LfoodPayrollSlipLine(models.Model):
    _name = 'lfood.payroll.slip.line'
    _description = 'Khoản trên phiếu lương'

    slip_id = fields.Many2one('lfood.payroll.slip', required=True, ondelete='cascade', index=True)
    component_id = fields.Many2one('lfood.payroll.component', 'Khoản', required=True)
    kind = fields.Selection(related='component_id.kind')
    amount = fields.Float('Số tiền theo hợp đồng / nhập', digits=(16, 0))
    paid_amount = fields.Float('Số tính lương', digits=(16, 0), readonly=True)
