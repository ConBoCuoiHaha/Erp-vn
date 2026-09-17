"""Vay và lãi vay (KT16) theo tài khoản 3411, Thông tư 99/2025/TT-BTC.

Giải ngân: Nợ 112 / Có 3411. Cuối kỳ trích lãi theo dư nợ thực tế từng ngày: Nợ 635 / Có 335. Trả lãi: Nợ 335 / Có 112;
trả gốc: Nợ 3411 / Có 112 (phiếu chi nội dung Trả nợ vay). Vay của tổ chức, cá nhân không phải tổ chức tín dụng:
phần lãi suất vượt mức Bộ luật Dân sự (20%/năm) không được trừ khi tính thuế TNDN (Nghị định 320/2025/NĐ-CP);
app ghi riêng phần vượt để điều chỉnh khi quyết toán. Chưa xét giới hạn lãi vay giao dịch liên kết (Nghị định
132/2020/NĐ-CP) và vốn hóa lãi vay.
"""
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd
from .loan_calc import interest, excess_part, equal_schedule, current_portion


class LfoodLoan(models.Model):
    _name = 'lfood.loan'
    _description = 'Hợp đồng vay'
    _order = 'date_start desc, id desc'

    name = fields.Char('Số', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    partner_id = fields.Many2one('res.partner', 'Bên cho vay', required=True, index=True)
    lender_type = fields.Selection([('bank', 'Tổ chức tín dụng'), ('other', 'Tổ chức, cá nhân khác')], 'Loại bên cho vay',
                                   required=True, default='bank')
    contract_ref = fields.Char('Số hợp đồng vay', required=True)
    purpose = fields.Char('Mục đích vay')
    principal = fields.Float('Số tiền vay', digits=(16, 0), required=True)
    rate = fields.Float('Lãi suất (%/năm)', digits=(6, 3), required=True)
    basis = fields.Selection([('365', '365 ngày'), ('360', '360 ngày')], 'Số ngày trong năm tính lãi', default='365',
                             required=True)
    date_start = fields.Date('Ngày giải ngân', required=True)
    date_end = fields.Date('Ngày đáo hạn', required=True)
    cash_account = fields.Selection([('112', '112 Tiền gửi ngân hàng'), ('111', '111 Tiền mặt')], 'Nhận tiền vào',
                                    default='112', required=True)
    payment_ids = fields.One2many('lfood.payment', 'loan_id', 'Phiếu trả nợ')
    accrual_ids = fields.One2many('lfood.loan.accrual', 'loan_id', 'Trích lãi')
    schedule_ids = fields.One2many('lfood.loan.schedule', 'loan_id', 'Lịch trả gốc', copy=True)
    installment_count = fields.Integer('Số kỳ trả gốc', default=1)
    installment_months = fields.Integer('Cách nhau (tháng)', default=12)
    first_due = fields.Date('Kỳ trả gốc đầu tiên')
    principal_paid = fields.Float('Gốc đã trả', digits=(16, 0), compute='_compute_balances')
    outstanding = fields.Float('Dư nợ gốc', digits=(16, 0), compute='_compute_balances')
    interest_accrued = fields.Float('Lãi đã trích', digits=(16, 0), compute='_compute_balances')
    interest_paid = fields.Float('Lãi đã trả', digits=(16, 0), compute='_compute_balances')
    accrued_to = fields.Date('Đã trích lãi đến ngày', compute='_compute_balances')
    state = fields.Selection([('draft', 'Nháp'), ('running', 'Đang vay'), ('closed', 'Đã tất toán')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)

    @api.depends('payment_ids.state', 'payment_ids.amount', 'accrual_ids.amount', 'principal', 'state')
    def _compute_balances(self):
        for rec in self:
            posted = rec.payment_ids.filtered(lambda p: p.state == 'posted')
            rec.principal_paid = sum(posted.filtered(lambda p: p.loan_part == 'principal').mapped('amount'))
            rec.interest_paid = sum(posted.filtered(lambda p: p.loan_part == 'interest').mapped('amount'))
            rec.outstanding = (rec.principal if rec.state != 'draft' else 0) - rec.principal_paid
            rec.interest_accrued = sum(rec.accrual_ids.mapped('amount'))
            rec.accrued_to = max(rec.accrual_ids.mapped('date_to')) if rec.accrual_ids else False

    @api.constrains('principal', 'rate', 'date_start', 'date_end')
    def _check_values(self):
        for rec in self:
            if rec.principal <= 0 or rec.rate < 0:
                raise ValidationError(_('Số tiền vay phải lớn hơn 0, lãi suất không âm.'))
            if rec.date_end <= rec.date_start:
                raise ValidationError(_('Ngày đáo hạn phải sau ngày giải ngân.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.loan') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_loan_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái hợp đồng vay chỉ đổi bằng các nút trên màn hình.'))
            if self.filtered(lambda r: r.state != 'draft') and set(vals) - {'purpose'}:
                raise UserError(_('Hợp đồng vay đã giải ngân không sửa được. Thay đổi lãi suất thì lập phụ lục là hợp đồng mới.'))
        return super().write(vals)

    def action_make_schedule(self):
        """Lập lịch trả gốc đều theo số kỳ; sửa tay từng kỳ được trước khi giải ngân."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ lập lịch cho hợp đồng chưa giải ngân.'))
            if rec.installment_count < 1 or rec.installment_months < 1 or not rec.first_due:
                raise UserError(_('Nhập số kỳ, số tháng giữa hai kỳ và ngày trả gốc kỳ đầu.'))
            rows = equal_schedule(rec.principal, rec.first_due, rec.installment_count, rec.installment_months)
            if rows[-1][0] > rec.date_end:
                raise UserError(_('Kỳ trả cuối %s sau ngày đáo hạn.') % rows[-1][0].strftime('%d/%m/%Y'))
            rec.schedule_ids.unlink()
            rec.write({'schedule_ids': [(0, 0, {'due_date': d, 'amount': a}) for d, a in rows]})
        return True

    def _current_part(self, report_date):
        """Dư nợ gốc tại report_date chia (ngắn hạn, dài hạn)."""
        self.ensure_one()
        paid = sum(self.payment_ids.filtered(
            lambda p: p.state == 'posted' and p.loan_part == 'principal' and p.date <= report_date).mapped('amount'))
        outstanding = self.principal - paid
        if self.schedule_ids:
            short = min(current_portion([(s.due_date, s.amount) for s in self.schedule_ids], paid, report_date), outstanding)
        else:
            short = outstanding if self.date_end <= fields.Date.add(report_date, years=1) else 0
        return short, outstanding - short

    def _events(self):
        self.ensure_one()
        pays = self.payment_ids.filtered(lambda p: p.state == 'posted' and p.loan_part == 'principal')
        return [(self.date_start, self.principal)] + [(p.date, -p.amount) for p in pays]

    def _cap(self, at):
        return self.env['lfood.legal.param'].get_value('LAI_VAY_TOI_DA_NAM', at, default=20)

    def action_disburse(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được ghi nhận khoản vay.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if rec.schedule_ids and round(sum(rec.schedule_ids.mapped('amount'))) != round(rec.principal):
                raise UserError(_('Tổng lịch trả gốc %s khác số tiền vay %s.') % (
                    vnd(sum(rec.schedule_ids.mapped('amount'))), vnd(rec.principal)))
            label = _('Nhận tiền vay %s theo hợp đồng %s') % (rec.partner_id.name, rec.contract_ref)
            self.env['lfood.move']._create_from_source(
                rec, 'bank' if rec.cash_account == '112' else 'cash', rec.date_start,
                [(rec.cash_account, rec.principal, 0, None, label, None),
                 ('3411', 0, rec.principal, rec.partner_id, label, None)],
                memo=label, key='disburse', ref=rec.contract_ref)
            rec.with_context(lfood_loan_system=True).write({'state': 'running'})
            msg = _('%s: %s, lãi suất %s%%/năm') % (label, vnd(rec.principal), '%g' % rec.rate)
            if rec.lender_type == 'other' and rec.rate > rec._cap(rec.date_start):
                msg += _('; vượt mức %s%%/năm của Bộ luật Dân sự, phần lãi vượt không được trừ khi tính thuế TNDN') \
                       % ('%g' % rec._cap(rec.date_start))
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id, summary=msg)
        return True

    def _accrue(self, date_to):
        """Trích lãi từ sau lần trích trước đến date_to; trả bản ghi trích lãi hoặc rỗng."""
        self.ensure_one()
        start = self.accrued_to + timedelta(days=1) if self.accrued_to else self.date_start
        end = min(date_to, self.date_end)
        amount = interest(self._events(), self.rate, start, end, int(self.basis))
        if amount <= 0:
            if end >= start:
                self.env['lfood.loan.accrual'].create({'loan_id': self.id, 'date_from': start, 'date_to': end, 'amount': 0})
            return self.env['lfood.loan.accrual']
        excess = excess_part(amount, self.rate, self._cap(end)) if self.lender_type == 'other' else 0
        accrual = self.env['lfood.loan.accrual'].create({
            'loan_id': self.id, 'date_from': start, 'date_to': end, 'amount': amount, 'nondeductible': excess})
        label = _('Lãi vay %s từ %s đến %s') % (self.contract_ref, start.strftime('%d/%m/%Y'), end.strftime('%d/%m/%Y'))
        self.env['lfood.move']._create_from_source(
            accrual, 'general', end, [('635', amount, 0, None, label, None),
                                      ('335', 0, amount, self.partner_id, label, None)],
            memo=label, ref=self.contract_ref, company=self.company_id)
        return accrual

    def _maybe_close(self):
        """Tất toán khi hết gốc, đã trích lãi đến ngày trước ngày trả gốc cuối và đã trả hết lãi."""
        for rec in self.filtered(lambda r: r.state == 'running' and r.outstanding <= 0):
            pays = rec.payment_ids.filtered(lambda p: p.state == 'posted' and p.loan_part == 'principal')
            last = max(pays.mapped('date')) if pays else rec.date_start
            if (rec.accrued_to or rec.date_start) < last - timedelta(days=1):
                continue
            if round(rec.interest_accrued - rec.interest_paid) <= 0:
                rec.with_context(lfood_loan_system=True).write({'state': 'closed'})

    def action_pay(self):
        """Lập phiếu trả nợ nháp: gốc còn lại hoặc lãi đã trích chưa trả."""
        self.ensure_one()
        part = self.env.context.get('loan_part', 'principal')
        amount = self.outstanding if part == 'principal' else self.interest_accrued - self.interest_paid
        if amount <= 0:
            raise UserError(_('Không còn số phải trả.'))
        payment = self.env['lfood.payment'].create({
            'company_id': self.company_id.id, 'kind': 'out', 'method': 'bank' if self.cash_account == '112' else 'cash',
            'purpose': 'loan', 'loan_id': self.id, 'loan_part': part, 'partner_id': self.partner_id.id,
            'amount': round(amount), 'date': fields.Date.context_today(self),
            'memo': (_('Trả gốc vay %s') if part == 'principal' else _('Trả lãi vay %s')) % self.contract_ref})
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.payment', 'res_id': payment.id, 'view_mode': 'form'}


class LfoodLedgerReport(models.TransientModel):
    _inherit = 'lfood.ledger.report'

    def _b01_rows(self, before):
        """Dư nợ gốc từng hợp đồng vay trình bày ngắn hạn nếu đáo hạn trong 12 tháng kể từ ngày báo cáo, dài hạn nếu sau đó."""
        rows = super()._b01_rows(before)
        report_date = before - timedelta(days=1)
        account = self.env['lfood.account'].by_code('3411')
        loans = self.env['lfood.loan'].sudo().search([('company_id', '=', self.company_id.id),
                                                     ('state', '!=', 'draft'), ('date_start', '<=', report_date)])
        other = 'long' if account.bs_term == 'short' else 'short'
        for loan in loans:
            short, long_ = loan._current_part(report_date)
            moved = long_ if account.bs_term == 'short' else short
            if moved:
                # dòng sổ 3411 là số dư Có (âm); chuyển phần `moved` từ kỳ hạn mặc định sang kỳ hạn còn lại
                rows += [('3411', account.bs_term, account.nature, moved), ('3411', other, account.nature, -moved)]
        return rows


class LfoodLoanSchedule(models.Model):
    _name = 'lfood.loan.schedule'
    _description = 'Kỳ trả gốc vay'
    _order = 'due_date, id'

    loan_id = fields.Many2one('lfood.loan', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='loan_id.company_id', store=True)
    due_date = fields.Date('Ngày trả gốc', required=True)
    amount = fields.Float('Số gốc phải trả', digits=(16, 0), required=True)

    def write(self, vals):
        if self.filtered(lambda s: s.loan_id.state != 'draft'):
            raise UserError(_('Lịch trả gốc của hợp đồng đã giải ngân không sửa được.'))
        return super().write(vals)


class LfoodLoanAccrual(models.Model):
    _name = 'lfood.loan.accrual'
    _description = 'Trích lãi vay'
    _order = 'date_to desc, id desc'

    loan_id = fields.Many2one('lfood.loan', 'Hợp đồng vay', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one(related='loan_id.company_id', store=True, index=True)
    date_from = fields.Date('Từ ngày', required=True)
    date_to = fields.Date('Đến ngày', required=True)
    amount = fields.Float('Tiền lãi', digits=(16, 0), required=True)
    nondeductible = fields.Float('Phần lãi không được trừ', digits=(16, 0),
                                 help='Lãi vượt mức Bộ luật Dân sự của khoản vay không phải từ tổ chức tín dụng')


class LfoodLoanAccrueWizard(models.TransientModel):
    _name = 'lfood.loan.accrue'
    _description = 'Trích lãi vay cuối kỳ'

    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company)
    date_to = fields.Date('Trích lãi đến ngày', required=True)
    result = fields.Text('Kết quả', readonly=True)

    def action_run(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được trích lãi vay.'))
        loans = self.env['lfood.loan'].search([('company_id', '=', self.company_id.id), ('state', '=', 'running'),
                                              ('date_start', '<=', self.date_to)])
        lines = []
        for loan in loans:
            acc = loan._accrue(self.date_to)
            if acc:
                lines.append(_('%s: %s') % (loan.contract_ref, vnd(acc.amount)))
        self.result = '\n'.join(lines) or _('Không có lãi phát sinh thêm.')
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form',
                'target': 'new'}


class LfoodPayment(models.Model):
    _inherit = 'lfood.payment'

    purpose = fields.Selection(selection_add=[('loan', 'Trả nợ vay')],
                               ondelete={'loan': lambda recs: recs.write({'purpose': 'other'})})
    loan_id = fields.Many2one('lfood.loan', 'Hợp đồng vay', index=True,
                              domain="[('company_id', '=', company_id), ('state', '=', 'running')]")
    loan_part = fields.Selection([('principal', 'Gốc'), ('interest', 'Lãi')], 'Trả phần')

    @api.depends('method', 'purpose', 'loan_part')
    def _compute_accounts(self):
        super()._compute_accounts()
        for rec in self.filtered(lambda p: p.purpose == 'loan'):
            rec.counterpart_account = '335' if rec.loan_part == 'interest' else '3411'

    def action_post(self):
        for rec in self.filtered(lambda p: p.state == 'draft' and p.purpose == 'loan'):
            loan = rec.loan_id
            if not (loan and rec.loan_part):
                raise UserError(_('Phiếu trả nợ vay phải chọn hợp đồng vay và phần gốc hay lãi.'))
            if rec.loan_part == 'principal' and loan.accrued_to and rec.date <= loan.accrued_to:
                raise UserError(_('Đã trích lãi đến %s theo dư nợ cũ; ngày trả gốc phải sau ngày đó.')
                                % loan.accrued_to.strftime('%d/%m/%Y'))
            limit = loan.outstanding if rec.loan_part == 'principal' else loan.interest_accrued - loan.interest_paid
            if rec.amount > round(limit):
                raise UserError(_('Số trả lớn hơn số còn phải trả %s. Trích lãi đến ngày trả trước khi trả lãi.') % vnd(limit))
        res = super().action_post()
        self.mapped('loan_id')._maybe_close()
        return res
