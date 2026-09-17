"""Quyết toán thuế TNCN năm thay người lao động (THUE09) và dữ liệu chứng từ khấu trừ (THUE08).

Nghị định 253/2026/NĐ-CP Điều 51: tổ chức trả thu nhập quyết toán thuế theo năm; người lao động được ủy quyền cho tổ chức
quyết toán thay nếu chỉ có một nguồn tiền lương, tiền công ký hợp đồng từ 03 tháng trở lên tại tổ chức và đang làm việc
tại đó lúc quyết toán (kể cả không đủ 12 tháng), hoặc có thêm thu nhập nơi khác bình quân tháng không quá 15 triệu đồng
đã được khấu trừ 10%; người đề nghị giảm thuế hoặc có khoản giảm trừ từ thiện, y tế, giáo dục (Điều 40, 49) phải tự
quyết toán.
Cách tính theo năm: thu nhập chịu thuế cả năm trừ bảo hiểm bắt buộc người lao động đóng, giảm trừ bản thân 12 tháng,
giảm trừ người phụ thuộc theo số tháng; thuế theo biểu lũy tiến năm (ngưỡng bậc tháng x 12); các mức lấy tại ngày 31/12.
So với thuế đã khấu trừ hằng tháng ra số phải nộp thêm hoặc nộp thừa. Hạn nộp hồ sơ quyết toán năm theo pháp luật quản lý
thuế (app gợi ý ngày cuối tháng thứ 3 sau năm tính thuế; kế toán kiểm tra lại với Luật Quản lý thuế hiện hành).
Tờ khai 05/QTT-TNCN và chứng từ khấu trừ điện tử lập trên phần mềm của cơ quan thuế, nhà cung cấp hóa đơn: app cung
cấp số liệu từng người.
"""
import calendar
from datetime import date

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_payroll.models.calc import pit_progressive
from odoo.addons.lfood_voucher.models.tools import vnd


class LfoodPitSettlement(models.Model):
    _name = 'lfood.pit.settlement'
    _description = 'Quyết toán thuế TNCN năm'
    _order = 'year desc'

    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    year = fields.Integer('Năm tính thuế', required=True, default=lambda s: fields.Date.context_today(s).year - 1)
    due_date = fields.Date('Hạn nộp gợi ý', compute='_compute_due', store=True)
    line_ids = fields.One2many('lfood.pit.settlement.line', 'settlement_id', 'Người lao động')
    freelance_html = fields.Html('Thu nhập vãng lai đã chi trả', readonly=True, sanitize=False)
    total_withheld = fields.Float('Thuế đã khấu trừ (tiền lương)', digits=(16, 0), compute='_compute_totals')
    total_payable = fields.Float('Phải nộp thêm', digits=(16, 0), compute='_compute_totals')
    total_refund = fields.Float('Nộp thừa', digits=(16, 0), compute='_compute_totals')
    state = fields.Selection([('draft', 'Nháp'), ('done', 'Đã chốt')], 'Trạng thái', default='draft', required=True,
                             readonly=True, copy=False)

    _uniq = models.Constraint('unique(company_id, year)', 'Đã có quyết toán năm này.')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('Quyết toán thuế TNCN năm %s') % rec.year

    @api.depends('year')
    def _compute_due(self):
        for rec in self:
            rec.due_date = date(rec.year + 1, 3, 31) if rec.year else False

    @api.depends('line_ids.withheld', 'line_ids.difference', 'line_ids.authorized')
    def _compute_totals(self):
        for rec in self:
            auth = rec.line_ids.filtered('authorized')
            rec.total_withheld = sum(rec.line_ids.mapped('withheld'))
            rec.total_payable = sum(d for d in auth.mapped('difference') if d > 0)
            rec.total_refund = -sum(d for d in auth.mapped('difference') if d < 0)

    def action_compute(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được lập quyết toán.'))
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Quyết toán đã chốt.'))
            y0, y1 = date(rec.year, 1, 1), date(rec.year, 12, 31)
            P = self.env['lfood.legal.param']
            g = lambda code: P.get_value(code, y1)
            brackets = [(g('TNCN_BAC_%s_DEN' % i) * 12, g('TNCN_THUE_SUAT_%s' % i)) for i in range(1, 5)]
            brackets.append((None, g('TNCN_THUE_SUAT_5')))
            self_ded, dep_ded = g('TNCN_GIAM_TRU_BAN_THAN'), g('TNCN_GIAM_TRU_NPT')
            other_cap = P.get_value('TNCN_QT_THU_NHAP_KHAC_BQ_THANG', y1, default=15000000)
            slips = self.env['lfood.payroll.slip'].search([
                ('company_id', '=', rec.company_id.id), ('run_id.state', 'in', ('posted', 'paid')),
                ('run_id.date_from', '>=', y0), ('run_id.date_to', '<=', y1)])
            old = {l.employee_id: l for l in rec.line_ids}
            vals = []
            for emp in slips.employee_id:
                mine = slips.filtered(lambda s: s.employee_id == emp)
                runs = mine.run_id
                dep_months = sum(emp._dependents_in(r.date_from, r.date_to) for r in runs)
                taxable = sum(mine.mapped('taxable_income'))
                insurance = sum(mine.mapped(lambda s: s.emp_si + s.emp_hi + s.emp_ui))
                family = self_ded * 12 + dep_ded * dep_months
                assessable = max(0, taxable - insurance - family)
                eligible = (emp.resident and emp.contract_type != 'short'
                            and (not emp.date_end or emp.date_end > y1))
                prev = old.get(emp)
                other = prev.other_income if prev else 0
                reason = ''
                if not emp.resident:
                    reason = _('Cá nhân không cư trú')
                elif emp.contract_type == 'short':
                    reason = _('Hợp đồng dưới 03 tháng')
                elif emp.date_end and emp.date_end <= y1:
                    reason = _('Đã nghỉ việc trước thời điểm quyết toán')
                elif other and other / 12 > other_cap:
                    eligible, reason = False, _('Thu nhập nơi khác bình quân tháng trên %s') % vnd(other_cap)
                tax = pit_progressive(assessable, brackets) if emp.resident else sum(mine.mapped('pit'))
                withheld = sum(mine.mapped('pit'))
                vals.append({
                    'employee_id': emp.id, 'months': len(runs), 'taxable': taxable, 'insurance': insurance,
                    'dependent_months': dep_months, 'family_deduction': family, 'assessable': assessable,
                    'tax': tax, 'withheld': withheld, 'difference': tax - withheld, 'eligible': eligible,
                    'ineligible_reason': reason, 'other_income': other,
                    'authorized': bool(prev and prev.authorized and eligible),
                    'self_settle_reason': prev.self_settle_reason if prev else False})
            rec.line_ids.unlink()
            rec.write({'line_ids': [(0, 0, v) for v in vals], 'freelance_html': rec._freelance_table(y0, y1)})
        return True

    def _freelance_table(self, y0, y1):
        pays = self.env['lfood.pit.freelance'].search([
            ('company_id', '=', self.company_id.id), ('state', '=', 'posted'), ('date', '>=', y0), ('date', '<=', y1)])
        by = {}
        for p in pays:
            k = (p.tax_code, p.partner_id.name)
            g, t, c = by.get(k, (0, 0, False))
            by[k] = (g + p.gross, t + p.tax, c or p.commitment)
        rows = Markup('').join(
            Markup('<tr><td>%s</td><td>%s</td><td class="text-end">%s</td><td class="text-end">%s</td><td>%s</td></tr>') % (
                name, code, vnd(g), vnd(t), _('Có cam kết') if c else '') for (code, name), (g, t, c) in sorted(by.items()))
        return Markup('<table class="table table-sm"><thead><tr><th>%s</th><th>%s</th><th class="text-end">%s</th>'
                      '<th class="text-end">%s</th><th></th></tr></thead><tbody>%s</tbody></table>') % (
            _('Cá nhân'), _('Mã số thuế'), _('Thu nhập'), _('Thuế đã khấu trừ'), rows)

    def action_done(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.line_ids:
                raise UserError(_('Chưa có số liệu quyết toán.'))
            rec.state = 'done'
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.display_name, company_id=rec.company_id.id,
                summary=_('Chốt quyết toán thuế TNCN %s: %s người ủy quyền, phải nộp thêm %s, nộp thừa %s') % (
                    rec.year, len(rec.line_ids.filtered('authorized')), vnd(rec.total_payable), vnd(rec.total_refund)))
        return True

    def action_reset(self):
        self.write({'state': 'draft'})
        return True


class LfoodPitSettlementLine(models.Model):
    _name = 'lfood.pit.settlement.line'
    _description = 'Quyết toán thuế TNCN từng người'
    _order = 'employee_id'

    settlement_id = fields.Many2one('lfood.pit.settlement', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='settlement_id.company_id', store=True)
    employee_id = fields.Many2one('lfood.employee', 'Người lao động', required=True)
    tax_code = fields.Char(related='employee_id.tax_code', string='Mã số thuế')
    months = fields.Integer('Số tháng có lương')
    taxable = fields.Float('Thu nhập chịu thuế', digits=(16, 0))
    insurance = fields.Float('Bảo hiểm bắt buộc', digits=(16, 0))
    dependent_months = fields.Integer('Tháng giảm trừ người phụ thuộc')
    family_deduction = fields.Float('Giảm trừ gia cảnh', digits=(16, 0))
    assessable = fields.Float('Thu nhập tính thuế', digits=(16, 0))
    tax = fields.Float('Thuế phải nộp cả năm', digits=(16, 0))
    withheld = fields.Float('Đã khấu trừ', digits=(16, 0))
    difference = fields.Float('Chênh lệch (+ nộp thêm, - nộp thừa)', digits=(16, 0))
    eligible = fields.Boolean('Đủ điều kiện ủy quyền', readonly=True)
    ineligible_reason = fields.Char('Lý do không đủ điều kiện', readonly=True)
    other_income = fields.Float('Thu nhập nơi khác trong năm (đã khấu trừ 10%)', digits=(16, 0))
    self_settle_reason = fields.Char('Tự quyết toán vì', help='Ví dụ đề nghị giảm thuế, có khoản giảm trừ từ thiện, y tế, giáo dục')
    authorized = fields.Boolean('Ủy quyền quyết toán')
    authorization_file = fields.Binary('Giấy ủy quyền', attachment=True)
    authorization_name = fields.Char()

    @api.constrains('authorized', 'eligible', 'self_settle_reason')
    def _check_authorized(self):
        for rec in self.filtered('authorized'):
            if not rec.eligible:
                raise ValidationError(_('%s không đủ điều kiện ủy quyền: %s') % (rec.employee_id.name, rec.ineligible_reason))
            if rec.self_settle_reason:
                raise ValidationError(_('%s phải tự quyết toán: %s') % (rec.employee_id.name, rec.self_settle_reason))
