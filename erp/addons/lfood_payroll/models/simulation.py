"""Tính thử bảng lương với mức tham số chưa duyệt (CH03).

Chọn một bảng lương và các mức tham số đang Chờ duyệt; app tính lại từng phiếu với mức mới, so với mức đang áp dụng,
không ghi gì vào bảng lương. Dùng trước khi duyệt lương tối thiểu vùng, lương cơ sở, giảm trừ gia cảnh, tỷ lệ bảo hiểm mới.
"""
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import num, vnd

KEYS = [('gross', 'Tổng thu nhập'), ('pit', 'Thuế TNCN'), ('net', 'Thực lĩnh'), ('employer', 'DN đóng BH, KPCĐ')]


class LfoodPayrollSimulation(models.TransientModel):
    _name = 'lfood.payroll.simulation'
    _description = 'Tính thử bảng lương với tham số mới'

    run_id = fields.Many2one('lfood.payroll.run', 'Bảng lương', required=True)
    value_ids = fields.Many2many('lfood.legal.param.value', string='Mức tham số chờ duyệt',
                                domain="[('state', '=', 'draft')]")
    result_html = fields.Html('So sánh', readonly=True, sanitize=False)
    diff_net = fields.Float('Chênh thực lĩnh', digits=(16, 0), readonly=True)
    diff_pit = fields.Float('Chênh thuế TNCN', digits=(16, 0), readonly=True)
    diff_employer = fields.Float('Chênh chi phí bảo hiểm DN', digits=(16, 0), readonly=True)

    @staticmethod
    def _pick(r):
        return {'gross': r['gross'], 'pit': r['pit'], 'net': r['net'],
                'employer': r['co_si'] + r['co_hi'] + r['co_ui'] + r['co_union']}

    def action_simulate(self):
        self.ensure_one()
        if not self.value_ids:
            raise UserError(_('Chọn ít nhất một mức tham số chờ duyệt.'))
        codes = self.value_ids.mapped('param_id.code')
        if len(codes) != len(set(codes)):
            raise UserError(_('Mỗi tham số chỉ chọn một mức.'))
        sim = {v.param_id.code: v.value for v in self.value_ids}
        run = self.run_id
        old_params = run._params()
        new_run = run.with_context(lfood_param_sim=sim)
        new_params = new_run._params()
        rows, tot_old, tot_new = [], dict.fromkeys(dict(KEYS), 0), dict.fromkeys(dict(KEYS), 0)
        for slip in run.slip_ids:
            old = self._pick(slip._slip_result(old_params)[0])
            new = self._pick(slip.with_context(lfood_param_sim=sim)._slip_result(new_params)[0])
            for k in old:
                tot_old[k] += old[k]
                tot_new[k] += new[k]
            rows.append((slip.employee_id.display_name, old, new))
        rows.append((_('Cộng'), tot_old, tot_new))
        head = Markup('').join(Markup('<th class="text-end">%s cũ</th><th class="text-end">%s mới</th>') % (l, l) for k, l in KEYS)
        body = Markup('').join(
            Markup('<tr><td>%s</td>%s</tr>') % (name, Markup('').join(
                Markup('<td class="text-end">%s</td><td class="text-end">%s</td>') % (vnd(o[k]), vnd(n[k])) for k, l in KEYS))
            for name, o, n in rows)
        params = Markup('').join(Markup('<li>%s: %s → %s (%s)</li>') % (
            v.param_id.code, num(v.param_id.get_value(v.param_id.code, run.date_to, default=0)), num(v.value),
            v.legal_ref or _('chưa ghi căn cứ')) for v in self.value_ids)
        self.write({
            'result_html': Markup('<ul>%s</ul><table class="table table-sm"><thead><tr><th>%s</th>%s</tr></thead>'
                                  '<tbody>%s</tbody></table>') % (params, _('Nhân viên'), head, body),
            'diff_net': tot_new['net'] - tot_old['net'], 'diff_pit': tot_new['pit'] - tot_old['pit'],
            'diff_employer': tot_new['employer'] - tot_old['employer']})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form',
                'target': 'new'}
