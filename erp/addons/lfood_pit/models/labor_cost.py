"""Báo cáo lao động, tiền lương, bảo hiểm theo tháng (BC08).

Lấy từ bảng lương đã ghi sổ: số người có phiếu lương, quỹ lương (tổng thu nhập), bảo hiểm người lao động đóng,
doanh nghiệp đóng (BHXH, BHYT, BHTN, KPCĐ), thuế TNCN khấu trừ, thực lĩnh, tổng chi phí nhân công; cộng thêm thuế đã
khấu trừ trên thu nhập vãng lai. Mỗi tháng một cột, cột cuối là cả năm.
"""
from markupsafe import Markup

from odoo import fields, models, _

from odoo.addons.lfood_voucher.models.tools import vnd

ROWS = [('headcount', 'Số người có lương'), ('gross', 'Quỹ lương (tổng thu nhập)'),
        ('emp_ins', 'Bảo hiểm người lao động đóng'), ('co_ins', 'Doanh nghiệp đóng BH, KPCĐ'),
        ('pit', 'Thuế TNCN khấu trừ (tiền lương)'), ('net', 'Thực lĩnh'), ('cost', 'Chi phí nhân công (lương + DN đóng)'),
        ('freelance', 'Thu nhập vãng lai đã chi'), ('freelance_pit', 'Thuế TNCN khấu trừ (vãng lai)')]


class LfoodLaborCostReport(models.TransientModel):
    _name = 'lfood.labor.cost.report'
    _description = 'Báo cáo lao động, tiền lương, bảo hiểm'

    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company)
    year = fields.Integer('Năm', required=True, default=lambda s: fields.Date.context_today(s).year)
    report_html = fields.Html('Báo cáo', readonly=True, sanitize=False)

    def _data(self):
        """{mã dòng: [12 tháng]}"""
        self.ensure_one()
        data = {k: [0] * 12 for k, _l in ROWS}
        slips = self.env['lfood.payroll.slip'].sudo().search([
            ('company_id', '=', self.company_id.id), ('run_id.year', '=', self.year),
            ('run_id.state', 'in', ('posted', 'paid'))])
        people = [set() for _i in range(12)]
        for s in slips:
            m = s.run_id.month - 1
            people[m].add(s.employee_id.id)
            co = s.co_si + s.co_hi + s.co_ui + s.co_union
            data['gross'][m] += s.gross
            data['emp_ins'][m] += s.emp_si + s.emp_hi + s.emp_ui
            data['co_ins'][m] += co
            data['pit'][m] += s.pit
            data['net'][m] += s.net
            data['cost'][m] += s.gross + co
        data['headcount'] = [len(p) for p in people]
        for f in self.env['lfood.pit.freelance'].sudo().search([
                ('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
                ('date', '>=', '%s-01-01' % self.year), ('date', '<=', '%s-12-31' % self.year)]):
            data['freelance'][f.date.month - 1] += f.gross
            data['freelance_pit'][f.date.month - 1] += f.tax
        return data

    def action_compute(self):
        for rec in self:
            data = rec._data()
            head = Markup('').join(Markup('<th class="text-end">T%s</th>') % m for m in range(1, 13))
            body = Markup('')
            for k, label in ROWS:
                vals = data[k]
                total = max(vals) if k == 'headcount' else sum(vals)
                cells = Markup('').join(Markup('<td class="text-end">%s</td>') % vnd(v) for v in vals + [total])
                body += Markup('<tr><td>%s</td>%s</tr>') % (label, cells)
            rec.report_html = Markup('<table class="table table-sm"><thead><tr><th>%s</th>%s<th class="text-end">%s</th>'
                                     '</tr></thead><tbody>%s</tbody></table><p class="text-muted">%s</p>') % (
                _('Chỉ tiêu'), head, _('Cả năm'), body,
                _('Cột cả năm của số người là số cao nhất trong các tháng. Chỉ tính bảng lương đã ghi sổ.'))
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form',
                'target': 'new'}
