"""Báo cáo tình hình thay đổi về lao động (NSU15).

Nghị định 145/2020/NĐ-CP, Điều 4: định kỳ 6 tháng (trước ngày 05/6) và hằng năm (trước ngày 05/12) người sử dụng lao
động báo cáo tình hình thay đổi lao động đến Sở Nội vụ qua Cổng Dịch vụ công quốc gia theo Mẫu số 01/PLI và thông báo
cơ quan bảo hiểm xã hội. App lập bảng số liệu có sẵn (người lao động, vị trí, lương, hợp đồng, bảo hiểm, tăng giảm trong
kỳ) để kế toán, nhân sự đối chiếu và khai trên cổng; các cột app chưa có dữ liệu (hệ số, nặng nhọc độc hại) để trống.
"""
from datetime import date, timedelta

from markupsafe import escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd


class LfoodEmployee(models.Model):
    _inherit = 'lfood.employee'

    birth_date = fields.Date('Ngày sinh', groups='lfood_base.group_accountant')
    gender = fields.Selection([('male', 'Nam'), ('female', 'Nữ')], 'Giới tính')


class LfoodLaborReport(models.Model):
    _name = 'lfood.labor.report'
    _description = 'Báo cáo tình hình thay đổi về lao động'
    _order = 'year desc, period desc'

    name = fields.Char('Tên', compute='_compute_period', store=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    year = fields.Integer('Năm', required=True, default=lambda s: fields.Date.context_today(s).year)
    period = fields.Selection([('h1', '6 tháng đầu năm'), ('year', 'Cả năm')], 'Kỳ', required=True, default='h1')
    date_from = fields.Date('Từ ngày', compute='_compute_period', store=True)
    date_to = fields.Date('Đến ngày', compute='_compute_period', store=True)
    due_date = fields.Date('Hạn nộp', compute='_compute_period', store=True)
    submitted_on = fields.Date('Ngày nộp trên Cổng Dịch vụ công')
    receipt_ref = fields.Char('Mã hồ sơ đã nộp')
    count_start = fields.Integer('Lao động đầu kỳ', readonly=True)
    count_in = fields.Integer('Tăng trong kỳ', readonly=True)
    count_out = fields.Integer('Giảm trong kỳ', readonly=True)
    count_end = fields.Integer('Lao động cuối kỳ', readonly=True)
    html = fields.Html('Bảng số liệu', readonly=True, sanitize=False)

    _period_uniq = models.Constraint('unique(company_id, year, period)', 'Kỳ báo cáo này đã có.')

    @api.depends('year', 'period')
    def _compute_period(self):
        for rec in self:
            if not rec.year:
                rec.name = rec.date_from = rec.date_to = rec.due_date = False
                continue
            day = int(self.env['lfood.legal.param'].get_value('BAO_CAO_LAO_DONG_HAN_6_THANG', date(rec.year, 1, 1),
                                                               default=5))
            rec.date_from = date(rec.year, 1, 1)
            if rec.period == 'h1':
                rec.date_to, rec.due_date = date(rec.year, 6, 30), date(rec.year, 6, day)
                rec.name = _('Báo cáo lao động 6 tháng đầu năm %s') % rec.year
            else:
                rec.date_to, rec.due_date = date(rec.year, 12, 31), date(rec.year, 12, day)
                rec.name = _('Báo cáo lao động năm %s') % rec.year

    def action_compute(self):
        for rec in self:
            emps = self.env['lfood.employee'].sudo().with_context(active_test=False).search(
                [('company_id', '=', rec.company_id.id), ('date_start', '!=', False)])
            start = emps.filtered(lambda e: e.date_start < rec.date_from and (not e.date_end or e.date_end >= rec.date_from))
            joined = emps.filtered(lambda e: rec.date_from <= e.date_start <= rec.date_to)
            left = emps.filtered(lambda e: e.date_end and rec.date_from <= e.date_end <= rec.date_to)
            # nghỉ việc trong kỳ (kể cả ngày cuối kỳ) tính vào giảm, không tính vào cuối kỳ
            end = emps.filtered(lambda e: e.date_start <= rec.date_to and (not e.date_end or e.date_end > rec.date_to))
            basic = self.env.ref('lfood_payroll.comp_basic')
            rows = []
            for i, e in enumerate((end | left).sorted('code'), 1):
                contract = e.contract_ids.filtered(lambda c: c.state in ('running', 'closed')).sorted('date_start')[-1:]
                change = _('Tăng') if e in joined else (_('Giảm') if e in left else '')
                allowances = sum(e.component_line_ids.filtered(lambda l: l.component_id != basic).mapped('amount'))
                rows.append('<tr>' + ''.join('<td>%s</td>' % escape(str(v)) for v in (
                    i, e.name, e.social_insurance_code or '', e.birth_date and e.birth_date.strftime('%d/%m/%Y') or '',
                    dict(e._fields['gender'].selection).get(e.gender, ''), e.job or '', vnd(e._basic_salary()),
                    vnd(allowances), dict(contract._fields['kind'].selection).get(contract.kind, '') if contract else '',
                    contract.date_start.strftime('%d/%m/%Y') if contract else '',
                    contract.date_end.strftime('%d/%m/%Y') if contract and contract.date_end else '',
                    vnd(e.insurance_salary), change,
                    e.date_end.strftime('%d/%m/%Y') if e in left else '')) + '</tr>')
            head = ''.join('<th>%s</th>' % h for h in (
                'STT', 'Họ tên', 'Mã số BHXH', 'Ngày sinh', 'Giới tính', 'Vị trí, chức danh', 'Lương', 'Phụ cấp, bổ sung',
                'Loại hợp đồng', 'Hiệu lực từ', 'Đến', 'Lương đóng BHXH', 'Tăng/giảm', 'Ngày nghỉ việc'))
            rec.write({
                'count_start': len(start), 'count_in': len(joined), 'count_out': len(left), 'count_end': len(end),
                'html': '<table class="table table-sm"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
                        '<p class="text-muted">Nghị định 145/2020/NĐ-CP, Điều 4, Mẫu số 01/PLI. Hệ số lương, phụ cấp chức vụ, '
                        'thâm niên, nghề nặng nhọc độc hại khai bổ sung trên Cổng Dịch vụ công.</p>' % (head, ''.join(rows))})
        return True

    def action_submitted(self):
        for rec in self:
            if not rec.html:
                raise UserError(_('Lập bảng số liệu trước.'))
            rec.write({'submitted_on': rec.submitted_on or fields.Date.context_today(self)})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Đã nộp %s, mã hồ sơ %s') % (rec.name, rec.receipt_ref or ''))
        return True


class LfoodReminder(models.Model):
    _inherit = 'lfood.reminder'

    def _collect_extra(self, company, today, horizon):
        out = super()._collect_extra(company, today, horizon)
        for year in (today.year,):
            for period, month in (('h1', 6), ('year', 12)):
                due = date(year, month, 5)
                if not (today - timedelta(days=60) <= due <= horizon):
                    continue
                done = self.env['lfood.labor.report'].sudo().search_count([
                    ('company_id', '=', company.id), ('year', '=', year), ('period', '=', period),
                    ('submitted_on', '!=', False)])
                if not done:
                    out.append({'key': 'laborrep-%s-%s-%s' % (company.id, year, period), 'category': 'hr',
                                'title': _('Nộp báo cáo tình hình thay đổi lao động %s năm %s') % (
                                    _('6 tháng') if period == 'h1' else _('cả năm'), year),
                                'due_date': due, 'res_model': 'lfood.labor.report', 'res_id': 0})
        return out
