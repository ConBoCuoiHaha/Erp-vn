"""Thuế thu nhập doanh nghiệp: tạm nộp theo quý và quyết toán năm.

App tính số liệu và ghi sổ; tờ khai chính thức vẫn nộp qua phần mềm của cơ quan thuế theo mẫu
03/TNDN hiện hành (mẫu áp dụng từ 01/7/2026 ban hành kèm Thông tư 89/2026/TT-BTC), vì cơ quan thuế
không công bố đặc tả tệp nộp. Màn hình Bảng tính thuế TNDN in ra để đối chiếu khi nhập tờ khai.
"""
from datetime import date

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd
from .calc import rate_for, offset_losses, shortfall

# 82111 chi phí thuế TNDN hiện hành theo Luật thuế TNDN (8211 là tài khoản cấp trên, không hạch toán thẳng)
EXPENSE_ACCOUNT = '82111'

PARAMS = {
    'small_limit': 'TNDN_DOANH_THU_MUC_15',
    'medium_limit': 'TNDN_DOANH_THU_MUC_17',
    'rate_small': 'TNDN_THUE_SUAT_15',
    'rate_medium': 'TNDN_THUE_SUAT_17',
    'rate_standard': 'TNDN_THUE_SUAT_PHO_THONG',
    'min_ratio': 'TNDN_TY_LE_TAM_NOP',
    'loss_years': 'TNDN_SO_NAM_CHUYEN_LO',
}


class CitMixin(models.AbstractModel):
    _name = 'lfood.cit.mixin'
    _description = 'Dùng chung cho tạm nộp và quyết toán thuế TNDN'

    def _param(self, key, at=None):
        return self.env['lfood.legal.param'].get_value(PARAMS[key], at or fields.Date.context_today(self))

    def _profit(self, date_from, date_to):
        """Tổng lợi nhuận kế toán trước thuế theo B02-DN (chỉ tiêu 50) của kỳ."""
        report = self.env['lfood.ledger.report'].with_company(self.company_id).sudo().new({
            'report': 'b02', 'company_id': self.company_id.id, 'date_from': date_from, 'date_to': date_to})
        return report._b02_values(date_from, date_to)['50']

    def _revenue(self, date_from, date_to):
        """Tổng doanh thu của kỳ: doanh thu thuần, doanh thu tài chính và thu nhập khác."""
        report = self.env['lfood.ledger.report'].with_company(self.company_id).sudo().new({
            'report': 'b02', 'company_id': self.company_id.id, 'date_from': date_from, 'date_to': date_to})
        v = report._b02_values(date_from, date_to)
        return (v['10'] or 0) + (v['22'] or 0) + (v['31'] or 0)

    def _post_tax(self, amount, at, label):
        """Nợ 82111 / Có 3334 phần thuế tăng thêm; số âm thì ghi ngược lại."""
        self.ensure_one()
        if not round(amount):
            return False
        if amount > 0:
            lines = [(EXPENSE_ACCOUNT, amount, 0, None, label, None), ('3334', 0, amount, None, label, None)]
        else:
            lines = [('3334', -amount, 0, None, label, None), (EXPENSE_ACCOUNT, 0, -amount, None, label, None)]
        return self.env['lfood.move']._create_from_source(self, 'general', at, lines, memo=label, ref=self.name)


class LfoodCitProvisional(models.Model):
    _name = 'lfood.cit.provisional'
    _inherit = ['lfood.cit.mixin']
    _description = 'Tạm nộp thuế TNDN quý'
    _order = 'year desc, quarter desc'

    name = fields.Char('Số chứng từ', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    year = fields.Integer('Năm', required=True, default=lambda s: fields.Date.context_today(s).year, index=True)
    quarter = fields.Selection([('1', 'Quý I'), ('2', 'Quý II'), ('3', 'Quý III'), ('4', 'Quý IV')], 'Quý',
                               required=True, default='1', index=True)
    date_from = fields.Date('Từ ngày', compute='_compute_period', store=True)
    date_to = fields.Date('Đến ngày', compute='_compute_period', store=True)
    date_due = fields.Date('Hạn nộp thuế', compute='_compute_period', store=True,
                           help='Chậm nhất ngày 30 của tháng đầu quý sau')
    profit = fields.Float('Lợi nhuận kế toán trước thuế trong quý', digits=(16, 0),
                          compute='_compute_base', store=True, readonly=False)
    adjust = fields.Float('Điều chỉnh tăng, giảm ước tính', digits=(16, 0),
                          help='Số dương là điều chỉnh tăng thu nhập tính thuế, số âm là giảm')
    rate = fields.Float('Thuế suất (%)', digits=(16, 2), compute='_compute_base', store=True, readonly=False)
    tax = fields.Float('Thuế tạm nộp', digits=(16, 0), compute='_compute_tax', store=True, readonly=False)
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)
    memo = fields.Char('Diễn giải')

    _period_uniq = models.Constraint('unique(company_id, year, quarter)', 'Quý này đã có chứng từ tạm nộp.')

    @api.depends('year', 'quarter')
    def _compute_period(self):
        for rec in self:
            q = int(rec.quarter or 1)
            rec.date_from = date(rec.year, 3 * q - 2, 1)
            rec.date_to = fields.Date.add(date(rec.year, 3 * q, 1), months=1, days=-1)
            rec.date_due = fields.Date.add(rec.date_to, days=1).replace(day=30)

    @api.depends('date_from', 'date_to', 'company_id')
    def _compute_base(self):
        for rec in self:
            if not (rec.date_from and rec.date_to and rec.company_id):
                continue
            rec.profit = rec._profit(rec.date_from, rec.date_to)
            prior = rec._revenue(date(rec.year - 1, 1, 1), date(rec.year - 1, 12, 31))
            rec.rate = rate_for(prior, rec._param('small_limit', rec.date_to), rec._param('medium_limit', rec.date_to),
                                rec._param('rate_small', rec.date_to), rec._param('rate_medium', rec.date_to),
                                rec._param('rate_standard', rec.date_to))

    @api.depends('profit', 'adjust', 'rate')
    def _compute_tax(self):
        for rec in self:
            rec.tax = round(max(0, rec.profit + rec.adjust) * rec.rate / 100)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.cit.provisional') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_cit_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái chỉ đổi bằng nút Ghi sổ, Hủy.'))
            if self.filtered(lambda r: r.state != 'draft'):
                raise UserError(_('Chứng từ đã ghi sổ không sửa được. Hủy rồi lập chứng từ mới.'))
        return super().write(vals)

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được ghi sổ thuế TNDN tạm nộp.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            label = _('Thuế TNDN tạm nộp %s năm %s') % (dict(rec._fields['quarter'].selection)[rec.quarter], rec.year)
            rec._post_tax(rec.tax, rec.date_to, label)
            rec.with_context(lfood_cit_system=True).write({'state': 'posted'})
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=rec.name,
                                                      company_id=rec.company_id.id,
                                                      summary=_('%s: %s, hạn nộp %s') % (label, vnd(rec.tax),
                                                                                         rec.date_due.strftime('%d/%m/%Y')))
        return True

    def action_cancel(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được hủy chứng từ đã ghi sổ.'))
        for rec in self.filtered(lambda r: r.state == 'posted'):
            move = self.env['lfood.move']._active_for(rec)
            if move:
                move._reverse(memo=_('Hủy %s') % rec.name)
            rec.with_context(lfood_cit_system=True).write({'state': 'cancel'})
        return True


class LfoodCitFinalization(models.Model):
    _name = 'lfood.cit.finalization'
    _inherit = ['lfood.cit.mixin']
    _description = 'Quyết toán thuế TNDN năm'
    _order = 'year desc'

    name = fields.Char('Số chứng từ', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    year = fields.Integer('Năm quyết toán', required=True, default=lambda s: fields.Date.context_today(s).year - 1, index=True)
    date_from = fields.Date('Từ ngày', compute='_compute_period', store=True)
    date_to = fields.Date('Đến ngày', compute='_compute_period', store=True)
    date_due = fields.Date('Hạn nộp hồ sơ quyết toán', compute='_compute_period', store=True,
                           help='Chậm nhất ngày cuối cùng của tháng thứ 3 kể từ ngày kết thúc năm tài chính')
    accounting_profit = fields.Float('Tổng lợi nhuận kế toán trước thuế', digits=(16, 0),
                                     compute='_compute_base', store=True, readonly=False)
    revenue_prior = fields.Float('Tổng doanh thu năm liền kề trước', digits=(16, 0),
                                 compute='_compute_base', store=True, readonly=False,
                                 help='Căn cứ xác định thuế suất 15%, 17% theo Luật Thuế TNDN 67/2025')
    rate = fields.Float('Thuế suất (%)', digits=(16, 2), compute='_compute_base', store=True, readonly=False)
    adjust_line_ids = fields.One2many('lfood.cit.adjust', 'finalization_id', 'Điều chỉnh', copy=True)
    loss_line_ids = fields.One2many('lfood.cit.loss', 'finalization_id', 'Chuyển lỗ các năm trước', copy=True)
    adjust_increase = fields.Float('Cộng điều chỉnh tăng', digits=(16, 0), compute='_compute_tax', store=True)
    adjust_decrease = fields.Float('Trừ điều chỉnh giảm', digits=(16, 0), compute='_compute_tax', store=True)
    taxable_income = fields.Float('Thu nhập chịu thuế', digits=(16, 0), compute='_compute_tax', store=True)
    loss_used = fields.Float('Lỗ các năm trước được chuyển', digits=(16, 0), compute='_compute_tax', store=True)
    assessable_income = fields.Float('Thu nhập tính thuế', digits=(16, 0), compute='_compute_tax', store=True)
    tax = fields.Float('Thuế TNDN phải nộp', digits=(16, 0), compute='_compute_tax', store=True)
    provisional_tax = fields.Float('Đã tạm nộp 4 quý', digits=(16, 0), compute='_compute_tax', store=True)
    tax_remaining = fields.Float('Còn phải nộp', digits=(16, 0), compute='_compute_tax', store=True)
    shortfall_amount = fields.Float('Tạm nộp còn thiếu so với tỷ lệ tối thiểu', digits=(16, 0),
                                    compute='_compute_tax', store=True)
    loss_carry = fields.Float('Lỗ năm nay chuyển sang năm sau', digits=(16, 0), compute='_compute_tax', store=True)
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)
    note = fields.Text('Ghi chú')
    summary_html = fields.Html('Bảng tính thuế TNDN', compute='_compute_summary', sanitize=False)

    _year_uniq = models.Constraint('unique(company_id, year)', 'Năm này đã có bản quyết toán.')

    @api.depends('year')
    def _compute_period(self):
        for rec in self:
            rec.date_from = date(rec.year, 1, 1)
            rec.date_to = date(rec.year, 12, 31)
            rec.date_due = date(rec.year + 1, 3, 31)

    @api.depends('date_from', 'date_to', 'company_id')
    def _compute_base(self):
        for rec in self:
            if not (rec.date_from and rec.date_to and rec.company_id):
                continue
            rec.accounting_profit = rec._profit(rec.date_from, rec.date_to)
            rec.revenue_prior = rec._revenue(date(rec.year - 1, 1, 1), date(rec.year - 1, 12, 31))
            rec.rate = rate_for(rec.revenue_prior, rec._param('small_limit', rec.date_to),
                                rec._param('medium_limit', rec.date_to), rec._param('rate_small', rec.date_to),
                                rec._param('rate_medium', rec.date_to), rec._param('rate_standard', rec.date_to))

    @api.depends('accounting_profit', 'rate', 'adjust_line_ids.amount', 'adjust_line_ids.kind',
                 'loss_line_ids.amount_used', 'year', 'company_id')
    def _compute_tax(self):
        for rec in self:
            rec.adjust_increase = sum(rec.adjust_line_ids.filtered(lambda l: l.kind == 'increase').mapped('amount'))
            rec.adjust_decrease = sum(rec.adjust_line_ids.filtered(lambda l: l.kind == 'decrease').mapped('amount'))
            rec.taxable_income = rec.accounting_profit + rec.adjust_increase - rec.adjust_decrease
            rec.loss_used = sum(rec.loss_line_ids.mapped('amount_used'))
            rec.assessable_income = max(0, rec.taxable_income - rec.loss_used)
            rec.tax = round(rec.assessable_income * rec.rate / 100)
            rec.loss_carry = max(0, -rec.taxable_income)
            rec.provisional_tax = sum(self.env['lfood.cit.provisional'].search([
                ('company_id', '=', rec.company_id.id), ('year', '=', rec.year), ('state', '=', 'posted')]).mapped('tax'))
            rec.tax_remaining = rec.tax - rec.provisional_tax
            rec.shortfall_amount = shortfall(rec.provisional_tax, rec.tax, rec._param('min_ratio', rec.date_to))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.cit.finalization') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_cit_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái chỉ đổi bằng nút Ghi sổ, Hủy.'))
            if self.filtered(lambda r: r.state != 'draft'):
                raise UserError(_('Bản quyết toán đã ghi sổ không sửa được. Hủy rồi lập bản mới.'))
        return super().write(vals)

    def action_load(self):
        """Lấy số gợi ý: chi phí không được trừ đã biết và lỗ các năm trước còn trong hạn chuyển."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Chỉ lấy số gợi ý khi bản quyết toán còn là Nháp.'))
        self.adjust_line_ids.filtered(lambda l: l.source != 'manual').unlink()
        self.loss_line_ids.unlink()
        self._load_adjustments()
        self._load_losses()
        return True

    def _load_adjustments(self):
        """Khoản điều chỉnh gợi ý; phân hệ khác ghi đè để thêm khoản của mình."""
        tally = self.env['lfood.purchase.tally'].sudo().search([
            ('company_id', '=', self.company_id.id), ('state', '=', 'confirmed'),
            ('date', '>=', self.date_from), ('date', '<=', self.date_to)])
        nondeductible = sum(tally.mapped('amount_nondeductible'))
        if nondeductible:
            self.env['lfood.cit.adjust'].create({
                'finalization_id': self.id, 'kind': 'increase', 'source': 'tally',
                'name': _('Thu mua không có hóa đơn trả tiền mặt từ mức quy định trở lên, không được trừ'),
                'amount': nondeductible})

    def _load_losses(self):
        years = int(self._param('loss_years', self.date_to))
        prior = self.search([('company_id', '=', self.company_id.id), ('year', '<', self.year),
                             ('state', '=', 'posted')])
        losses = [(p.year, p.loss_carry - p._loss_already_used()) for p in prior if p.loss_carry]
        used, _remain = offset_losses(self.taxable_income, losses, self.year, years)
        for loss_year, amount in used:
            self.env['lfood.cit.loss'].create({'finalization_id': self.id, 'loss_year': loss_year,
                                               'amount_available': dict(losses)[loss_year], 'amount_used': amount})

    def _loss_already_used(self):
        """Số lỗ của năm này đã được các bản quyết toán sau đó sử dụng."""
        self.ensure_one()
        lines = self.env['lfood.cit.loss'].search([
            ('loss_year', '=', self.year), ('finalization_id.company_id', '=', self.company_id.id),
            ('finalization_id.state', '=', 'posted')])
        return sum(lines.mapped('amount_used'))

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được ghi sổ quyết toán thuế TNDN.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            for line in rec.loss_line_ids:
                if line.amount_used > line.amount_available + 1e-6:
                    raise UserError(_('Lỗ năm %s chỉ còn %s được chuyển.') % (line.loss_year, vnd(line.amount_available)))
            label = _('Quyết toán thuế TNDN năm %s') % rec.year
            rec._post_tax(rec.tax_remaining, rec.date_to, label)
            rec.with_context(lfood_cit_system=True).write({'state': 'posted'})
            summary = _('%s: thuế phải nộp %s, đã tạm nộp %s, còn phải nộp %s') % (
                label, vnd(rec.tax), vnd(rec.provisional_tax), vnd(rec.tax_remaining))
            if rec.shortfall_amount:
                summary += _('; tạm nộp 4 quý thiếu %s so với tỷ lệ tối thiểu nên bị tính tiền chậm nộp') \
                           % vnd(rec.shortfall_amount)
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=rec.name,
                                                      company_id=rec.company_id.id, summary=summary)
        return True

    def action_cancel(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được hủy bản quyết toán đã ghi sổ.'))
        for rec in self.filtered(lambda r: r.state == 'posted'):
            move = self.env['lfood.move']._active_for(rec)
            if move:
                move._reverse(memo=_('Hủy %s') % rec.name)
            rec.with_context(lfood_cit_system=True).write({'state': 'cancel'})
        return True

    @api.depends('accounting_profit', 'adjust_increase', 'adjust_decrease', 'loss_used', 'assessable_income',
                 'rate', 'tax', 'provisional_tax', 'tax_remaining', 'shortfall_amount')
    def _compute_summary(self):
        for rec in self:
            rows = [
                (_('Tổng lợi nhuận kế toán trước thuế'), rec.accounting_profit, True),
                (_('Cộng: các khoản điều chỉnh tăng thu nhập chịu thuế'), rec.adjust_increase, False),
                (_('Trừ: các khoản điều chỉnh giảm thu nhập chịu thuế'), rec.adjust_decrease, False),
                (_('Thu nhập chịu thuế'), rec.taxable_income, True),
                (_('Trừ: lỗ các năm trước được chuyển'), rec.loss_used, False),
                (_('Thu nhập tính thuế'), rec.assessable_income, True),
                (_('Thuế suất áp dụng: %s%%') % ('%g' % rec.rate), None, False),
                (_('Thuế TNDN phải nộp'), rec.tax, True),
                (_('Trừ: thuế đã tạm nộp 4 quý'), rec.provisional_tax, False),
                (_('Còn phải nộp'), rec.tax_remaining, True),
            ]
            body = Markup('').join(
                Markup('<tr%s><td>%s</td><td style="text-align:right">%s</td></tr>') % (
                    Markup(' style="font-weight:600"') if bold else Markup(''), label,
                    '' if value is None else vnd(round(value)))
                for label, value, bold in rows)
            warn = Markup('')
            if rec.shortfall_amount:
                warn = Markup('<p style="color:#B91C1C">%s</p>') % (
                    _('Tổng tạm nộp 4 quý thấp hơn tỷ lệ tối thiểu %s%% của số quyết toán: thiếu %s. '
                      'Phần thiếu bị tính tiền chậm nộp kể từ ngày tiếp sau hạn nộp thuế quý IV.')
                    % ('%g' % rec._param('min_ratio', rec.date_to), vnd(rec.shortfall_amount)))
            carry = Markup('')
            if rec.loss_carry:
                carry = Markup('<p>%s</p>') % (_('Lỗ năm %s là %s, được chuyển liên tục không quá %s năm kể từ năm %s.')
                                               % (rec.year, vnd(rec.loss_carry),
                                                  '%g' % rec._param('loss_years', rec.date_to), rec.year + 1))
            rec.summary_html = Markup(
                '<div class="o_lfood_changes"><h4>%s</h4><table>%s</table>%s%s<p class="text-muted">%s</p></div>') % (
                _('Bảng tính thuế TNDN năm %s') % rec.year, body, warn, carry,
                _('Số liệu để nhập tờ khai quyết toán mẫu 03/TNDN trên phần mềm của cơ quan thuế; '
                  'app không tạo tệp nộp vì cơ quan thuế không công bố đặc tả.'))


class LfoodCitAdjust(models.Model):
    _name = 'lfood.cit.adjust'
    _description = 'Khoản điều chỉnh thu nhập chịu thuế'
    _order = 'kind, id'

    finalization_id = fields.Many2one('lfood.cit.finalization', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='finalization_id.company_id', store=True)
    kind = fields.Selection([('increase', 'Điều chỉnh tăng'), ('decrease', 'Điều chỉnh giảm')], 'Loại',
                            required=True, default='increase')
    name = fields.Char('Nội dung', required=True)
    amount = fields.Float('Số tiền', digits=(16, 0), required=True)
    source = fields.Selection([('manual', 'Kế toán nhập'), ('tally', 'Từ bảng kê thu mua')], 'Nguồn',
                              default='manual', readonly=True)

    def write(self, vals):
        if not self.env.context.get('lfood_cit_system') and self.filtered(lambda l: l.finalization_id.state != 'draft'):
            raise UserError(_('Bản quyết toán đã ghi sổ không sửa được.'))
        return super().write(vals)


class LfoodCitLoss(models.Model):
    _name = 'lfood.cit.loss'
    _description = 'Lỗ năm trước được chuyển'
    _order = 'loss_year'

    finalization_id = fields.Many2one('lfood.cit.finalization', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='finalization_id.company_id', store=True)
    loss_year = fields.Integer('Năm phát sinh lỗ', required=True)
    amount_available = fields.Float('Lỗ còn được chuyển', digits=(16, 0), readonly=True)
    amount_used = fields.Float('Số chuyển vào năm nay', digits=(16, 0), required=True)

    def write(self, vals):
        if not self.env.context.get('lfood_cit_system') and self.filtered(lambda l: l.finalization_id.state != 'draft'):
            raise UserError(_('Bản quyết toán đã ghi sổ không sửa được.'))
        return super().write(vals)
