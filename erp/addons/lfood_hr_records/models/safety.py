"""Tai nạn lao động (NSU10) và huấn luyện an toàn, vệ sinh lao động (NSU11).

Luật An toàn, vệ sinh lao động 2015:
- Điều 34: tai nạn làm chết người hoặc bị thương nặng phải khai báo ngay với cơ quan có thẩm quyền.
- Điều 38: người sử dụng lao động trả chi phí y tế, trả đủ tiền lương theo hợp đồng trong thời gian điều trị; bồi
  thường ít nhất 1,5 tháng tiền lương khi suy giảm khả năng lao động từ 5% đến 10%, cộng 0,4 tháng cho mỗi 1% từ 11%
  đến 80%; ít nhất 30 tháng tiền lương khi suy giảm từ 81% trở lên hoặc chết; lỗi hoàn toàn do người lao động thì trợ
  cấp ít nhất 40% các mức trên. Các hệ số là tham số pháp lý.
Nghị định 39/2016/NĐ-CP, Điều 24: báo cáo tổng hợp tình hình tai nạn lao động định kỳ 6 tháng (trước ngày 05/7) và
hằng năm (trước ngày 10/01 năm sau).
Huấn luyện an toàn: ghi nhận lớp, nhóm đối tượng, hạn chứng nhận; nhắc khi sắp hết hạn. Khám sức khỏe định kỳ ở phân hệ
Chất lượng (hồ sơ người lao động); cấp phát bảo hộ lao động làm bằng phiếu xuất kho nội bộ.
"""
from datetime import date, timedelta

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd

SEVERITY = [('light', 'Nhẹ'), ('serious', 'Nặng'), ('fatal', 'Chết người')]


def compensation_months(impairment, fatal, worker_fault, base=1.5, step=0.4, top=30, fault_pct=40):
    """Số tháng tiền lương bồi thường (hoặc trợ cấp khi lỗi do người lao động)."""
    if fatal or impairment >= 81:
        months = top
    elif impairment >= 11:
        months = base + (impairment - 10) * step
    elif impairment >= 5:
        months = base
    else:
        months = 0
    return round(months * (fault_pct / 100 if worker_fault else 1), 2)


class LfoodHrAccident(models.Model):
    _name = 'lfood.hr.accident'
    _description = 'Tai nạn lao động'
    _order = 'date desc, id desc'

    employee_id = fields.Many2one('lfood.employee', 'Người bị nạn', required=True, index=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    date = fields.Date('Ngày xảy ra', required=True)
    place = fields.Char('Nơi xảy ra', required=True)
    description = fields.Text('Diễn biến, nguyên nhân', required=True)
    severity = fields.Selection(SEVERITY, 'Mức độ', required=True, default='light')
    occupational_disease = fields.Boolean('Bệnh nghề nghiệp')
    reported_on = fields.Date('Ngày khai báo cơ quan có thẩm quyền')
    investigation_file = fields.Binary('Biên bản điều tra', attachment=True)
    investigation_name = fields.Char()
    days_off = fields.Float('Số ngày nghỉ điều trị')
    medical_cost = fields.Float('Chi phí y tế doanh nghiệp trả', digits=(16, 0))
    impairment = fields.Float('Tỷ lệ suy giảm khả năng lao động (%)')
    worker_fault = fields.Boolean('Lỗi hoàn toàn do người lao động')
    monthly_salary = fields.Float('Tiền lương tháng theo hợp đồng', digits=(16, 0))
    salary_during_treatment = fields.Float('Tiền lương trả trong thời gian điều trị', digits=(16, 0),
                                           compute='_compute_amounts', store=True)
    compensation_months = fields.Float('Số tháng lương bồi thường, trợ cấp', compute='_compute_amounts', store=True)
    compensation = fields.Float('Tiền bồi thường, trợ cấp', digits=(16, 0), compute='_compute_amounts', store=True)
    state = fields.Selection([('draft', 'Đang xử lý'), ('closed', 'Đã giải quyết xong')], 'Trạng thái', default='draft',
                             required=True, readonly=True)

    @api.onchange('employee_id')
    def _onchange_employee(self):
        emp = self.employee_id
        if emp:
            self.monthly_salary = (emp.contract_id.salary if 'contract_id' in emp._fields and emp.contract_id else 0) \
                or emp.insurance_salary

    @api.depends('days_off', 'impairment', 'worker_fault', 'severity', 'monthly_salary', 'date')
    def _compute_amounts(self):
        P = self.env['lfood.legal.param']
        for rec in self:
            d = rec.date or fields.Date.context_today(rec)
            g = lambda code, default: P.get_value(code, d, default=default)
            months = compensation_months(rec.impairment, rec.severity == 'fatal', rec.worker_fault,
                                         g('TNLD_BT_THANG_CO_BAN', 1.5), g('TNLD_BT_THANG_MOI_PT', 0.4),
                                         g('TNLD_BT_THANG_TOI_DA', 30), g('TNLD_TRO_CAP_LOI_NLD_PT', 40))
            standard = g('NGAY_CONG_CHUAN', 26)
            rec.salary_during_treatment = round(rec.monthly_salary / standard * rec.days_off) if standard else 0
            rec.compensation_months = months
            rec.compensation = round(rec.monthly_salary * months)

    def action_close(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if rec.severity in ('serious', 'fatal') and not rec.reported_on:
                raise UserError(_('Tai nạn nặng hoặc chết người phải ghi ngày khai báo cơ quan có thẩm quyền '
                                  '(Luật An toàn, vệ sinh lao động 2015, Điều 34).'))
            if rec.impairment and not rec.investigation_file:
                raise UserError(_('Đính kèm biên bản điều tra, kết luận giám định.'))
            rec.state = 'closed'
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.employee_id.name, company_id=rec.company_id.id,
                summary=_('Giải quyết tai nạn lao động %s ngày %s: bồi thường, trợ cấp %s, lương điều trị %s, chi phí y tế %s')
                % (rec.employee_id.name, rec.date.strftime('%d/%m/%Y'), vnd(rec.compensation),
                   vnd(rec.salary_during_treatment), vnd(rec.medical_cost)))
        return True


class LfoodHrAccidentReport(models.Model):
    _name = 'lfood.hr.accident.report'
    _description = 'Báo cáo tình hình tai nạn lao động'
    _order = 'year desc, period desc'

    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    year = fields.Integer('Năm', required=True, default=lambda s: fields.Date.context_today(s).year)
    period = fields.Selection([('h1', '6 tháng đầu năm'), ('year', 'Cả năm')], 'Kỳ', required=True, default='h1')
    due_date = fields.Date('Hạn nộp', compute='_compute_due', store=True)
    content_html = fields.Html('Số liệu', readonly=True, sanitize=False)
    submitted_on = fields.Date('Ngày nộp')

    _uniq = models.Constraint('unique(company_id, year, period)', 'Đã có báo cáo kỳ này.')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('Báo cáo tai nạn lao động %s năm %s') % (
                dict(self._fields['period'].selection).get(rec.period, ''), rec.year)

    @api.depends('year', 'period')
    def _compute_due(self):
        for rec in self:
            rec.due_date = date(rec.year, 7, 5) if rec.period == 'h1' else date(rec.year + 1, 1, 10)

    def action_compute(self):
        for rec in self:
            end = date(rec.year, 6, 30) if rec.period == 'h1' else date(rec.year, 12, 31)
            acc = self.env['lfood.hr.accident'].search([
                ('company_id', '=', rec.company_id.id), ('date', '>=', date(rec.year, 1, 1)), ('date', '<=', end)])
            rows = [(_('Số vụ tai nạn lao động'), len(acc)),
                    (_('Số vụ có người chết'), len(acc.filtered(lambda a: a.severity == 'fatal'))),
                    (_('Số người bị nạn'), len(acc.employee_id)),
                    (_('Số người bị thương nặng'), len(acc.filtered(lambda a: a.severity == 'serious').employee_id)),
                    (_('Số người chết'), len(acc.filtered(lambda a: a.severity == 'fatal').employee_id)),
                    (_('Số người mắc bệnh nghề nghiệp'), len(acc.filtered('occupational_disease').employee_id)),
                    (_('Tổng số ngày nghỉ vì tai nạn'), '%g' % sum(acc.mapped('days_off'))),
                    (_('Chi phí y tế (đồng)'), vnd(sum(acc.mapped('medical_cost')))),
                    (_('Tiền lương trong thời gian điều trị (đồng)'), vnd(sum(acc.mapped('salary_during_treatment')))),
                    (_('Bồi thường, trợ cấp (đồng)'), vnd(sum(acc.mapped('compensation'))))]
            rec.content_html = Markup('<table class="table table-sm">%s</table>') % Markup('').join(
                Markup('<tr><td>%s</td><td class="text-end">%s</td></tr>') % r for r in rows)
        return True


class LfoodHrSafetyTraining(models.Model):
    _name = 'lfood.hr.safety.training'
    _description = 'Huấn luyện an toàn, vệ sinh lao động'
    _order = 'date desc'

    employee_id = fields.Many2one('lfood.employee', 'Người được huấn luyện', required=True, index=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    group = fields.Selection([(str(i), 'Nhóm %s' % i) for i in range(1, 7)], 'Nhóm đối tượng', required=True, default='4')
    course = fields.Char('Nội dung, lớp huấn luyện', required=True)
    provider = fields.Char('Đơn vị huấn luyện')
    date = fields.Date('Ngày huấn luyện', required=True)
    valid_until = fields.Date('Hạn chứng nhận, thẻ', help='Để trống nếu không có hạn')
    certificate = fields.Binary('Chứng nhận, sổ theo dõi', attachment=True)
    certificate_name = fields.Char()


class LfoodReminder(models.Model):
    _inherit = 'lfood.reminder'

    def _collect_extra(self, company, today, horizon):
        out = super()._collect_extra(company, today, horizon)
        Report = self.env['lfood.hr.accident.report'].sudo()
        for year, period, due in ((today.year, 'h1', date(today.year, 7, 5)), (today.year - 1, 'year', date(today.year, 1, 10))):
            if not (today - timedelta(days=60) <= due <= horizon):
                continue
            if not Report.search_count([('company_id', '=', company.id), ('year', '=', year), ('period', '=', period),
                                        ('submitted_on', '!=', False)]):
                out.append({'key': 'accrep-%s-%s-%s' % (company.id, year, period), 'category': 'hr',
                            'title': _('Nộp báo cáo tình hình tai nạn lao động %s năm %s') % (
                                _('6 tháng') if period == 'h1' else _('cả năm'), year),
                            'due_date': due, 'res_model': 'lfood.hr.accident.report', 'res_id': 0})
        trainings = self.env['lfood.hr.safety.training'].sudo().search([
            ('company_id', '=', company.id), ('valid_until', '!=', False), ('valid_until', '<=', horizon)])
        latest = {}
        for t in trainings.sorted('valid_until'):
            latest[(t.employee_id, t.group)] = t
        for (emp, group), t in latest.items():
            newer = self.env['lfood.hr.safety.training'].sudo().search_count([
                ('employee_id', '=', emp.id), ('group', '=', group), ('valid_until', '>', horizon)])
            if not newer and emp.active:
                out.append({'key': 'safety-%s-%s' % (t.id, t.valid_until), 'category': 'hr',
                            'title': _('Chứng nhận huấn luyện an toàn nhóm %s của %s hết hạn') % (group, emp.name),
                            'due_date': t.valid_until, 'res_model': t._name, 'res_id': t.id})
        return out
