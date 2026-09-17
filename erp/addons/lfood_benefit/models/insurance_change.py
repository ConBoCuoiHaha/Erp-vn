"""Danh sách tăng, giảm, điều chỉnh mức đóng bảo hiểm hằng tháng (LUONG07).

So phiếu lương tháng này với tháng trước: có đóng tháng này mà tháng trước không đóng là tăng; tháng trước đóng mà tháng
này không đóng (nghỉ việc, nghỉ không lương, không có phiếu lương) là giảm; cùng đóng nhưng tiền lương đóng BHXH hoặc
BHTN khác là điều chỉnh. Số liệu dùng để lập mẫu D02-LT (danh sách lao động tham gia BHXH, BHYT, BHTN, BHTNLĐ-BNN) trên
phần mềm kê khai bảo hiểm; app không vẽ lại mẫu vì mẫu do BHXH Việt Nam ban hành và thay đổi theo quyết định của cơ quan
này (năm 2026 là Quyết định 366/QĐ-BHXH theo các nguồn tổng hợp, kế toán kiểm tra phiên bản trên phần mềm kê khai).
"""
import base64
import calendar
import csv
import io
from datetime import date, timedelta

from odoo import fields, models, _
from odoo.exceptions import UserError

KINDS = [('increase', 'Tăng'), ('decrease', 'Giảm'), ('adjust', 'Điều chỉnh mức đóng')]


class LfoodInsuranceChange(models.Model):
    _name = 'lfood.insurance.change'
    _description = 'Tăng, giảm lao động đóng bảo hiểm'
    _order = 'year desc, month desc'

    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    year = fields.Integer('Năm', required=True, default=lambda s: fields.Date.context_today(s).year)
    month = fields.Integer('Tháng', required=True, default=lambda s: fields.Date.context_today(s).month)
    line_ids = fields.One2many('lfood.insurance.change.line', 'change_id', 'Danh sách')
    export_file = fields.Binary('Tệp CSV', readonly=True, attachment=False)
    export_name = fields.Char()
    summary = fields.Char('Tóm tắt', readonly=True)

    _uniq = models.Constraint('unique(company_id, year, month)', 'Đã có danh sách tháng này.')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('Tăng, giảm bảo hiểm tháng %02d/%s') % (rec.month, rec.year)

    def _slips(self, y, m):
        return {s.employee_id: s for s in self.env['lfood.payroll.slip'].search([
            ('company_id', '=', self.company_id.id), ('run_id.year', '=', y), ('run_id.month', '=', m)])}

    def action_compute(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được lập danh sách.'))
        for rec in self:
            cur = rec._slips(rec.year, rec.month)
            if not cur:
                raise UserError(_('Chưa có bảng lương tháng %02d/%s.') % (rec.month, rec.year))
            prev_day = date(rec.year, rec.month, 1) - timedelta(days=1)
            prev = rec._slips(prev_day.year, prev_day.month)
            vals = []
            for emp in (set(cur) | set(prev)):
                c, p = cur.get(emp), prev.get(emp)
                c_si, p_si = (c.si_base if c else 0), (p.si_base if p else 0)
                c_ui, p_ui = (c.ui_base if c else 0), (p.ui_base if p else 0)
                note = ''
                if c_si and not p_si:
                    kind = 'increase'
                    if not emp.social_insurance_code:
                        note = _('Chưa có mã số BHXH: đăng ký tham gia lần đầu')
                elif p_si and not c_si:
                    kind = 'decrease'
                    if emp.date_end and emp.date_end <= date(rec.year, rec.month, calendar.monthrange(rec.year, rec.month)[1]):
                        note = _('Nghỉ việc từ %s') % emp.date_end.strftime('%d/%m/%Y')
                    elif c and c.skip_insurance:
                        note = _('Không đóng tháng này: %s') % (c.note or _('nghỉ không lương'))
                    else:
                        note = _('Không còn phiếu lương đóng bảo hiểm')
                elif c_si and (c_si != p_si or c_ui != p_ui):
                    kind = 'adjust'
                    note = _('Từ %s thành %s') % ('{:,.0f}'.format(p_si).replace(',', '.'),
                                                    '{:,.0f}'.format(c_si).replace(',', '.'))
                else:
                    continue
                vals.append({'employee_id': emp.id, 'kind': kind, 'old_si': p_si, 'new_si': c_si,
                             'old_ui': p_ui, 'new_ui': c_ui, 'note': note})
            rec.line_ids.unlink()
            rec.write({'line_ids': [(0, 0, v) for v in sorted(vals, key=lambda v: (v['kind'], v['employee_id']))]})
            counts = {k: len(rec.line_ids.filtered(lambda l, k=k: l.kind == k)) for k, _l in KINDS}
            rec.summary = ', '.join('%s: %s' % (label, counts[k]) for k, label in KINDS if counts[k]) or _('Không có thay đổi')
            rec._export()
        return True

    def _export(self):
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=';')
        w.writerow(['Loại', 'Mã nhân viên', 'Họ và tên', 'Mã số BHXH', 'Mã số thuế', 'Chức danh', 'Từ tháng',
                    'Tiền lương đóng BHXH cũ', 'Tiền lương đóng BHXH mới', 'Tiền lương đóng BHTN cũ',
                    'Tiền lương đóng BHTN mới', 'Ghi chú'])
        labels = dict(KINDS)
        for l in self.line_ids:
            e = l.employee_id
            w.writerow([labels[l.kind], e.code, e.name, e.social_insurance_code or '', e.tax_code or '', e.job or '',
                        '%02d/%s' % (self.month, self.year), int(l.old_si), int(l.new_si), int(l.old_ui), int(l.new_ui),
                        l.note or ''])
        self.write({'export_file': base64.b64encode(buf.getvalue().encode('utf-8-sig')),
                    'export_name': 'tang-giam-bao-hiem-%s-%02d.csv' % (self.year, self.month)})


class LfoodInsuranceChangeLine(models.Model):
    _name = 'lfood.insurance.change.line'
    _description = 'Dòng tăng, giảm bảo hiểm'

    change_id = fields.Many2one('lfood.insurance.change', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='change_id.company_id', store=True)
    employee_id = fields.Many2one('lfood.employee', 'Người lao động', required=True)
    social_insurance_code = fields.Char(related='employee_id.social_insurance_code')
    kind = fields.Selection(KINDS, 'Loại', required=True)
    old_si = fields.Float('Lương đóng BHXH cũ', digits=(16, 0))
    new_si = fields.Float('Lương đóng BHXH mới', digits=(16, 0))
    old_ui = fields.Float('Lương đóng BHTN cũ', digits=(16, 0))
    new_ui = fields.Float('Lương đóng BHTN mới', digits=(16, 0))
    note = fields.Char('Ghi chú')
