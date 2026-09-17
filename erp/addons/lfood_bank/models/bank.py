"""Tài khoản ngân hàng (DM11) và đối soát sổ phụ ngân hàng với sổ tiền gửi 112 (KT03).

Sổ phụ nhập tay hoặc từ tệp CSV. App tự khớp từng dòng sổ phụ với dòng 112 đã ghi sổ cùng số tiền, cùng chiều,
chênh ngày không quá số ngày cho phép. Bảng đối chiếu: số dư sổ kế toán, trừ khoản sổ đã ghi mà ngân hàng chưa ghi,
cộng khoản ngân hàng đã ghi mà sổ chưa có, phải bằng số dư cuối sổ phụ. Khoản ngân hàng ghi mà sổ chưa có
(phí, lãi tiền gửi) thì lập phiếu thu chi từ dòng sổ phụ rồi khớp lại.
"""
import base64
import csv
import io
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd

MATCH_DAYS = 5


class LfoodBankAccount(models.Model):
    _name = 'lfood.bank.account'
    _description = 'Tài khoản ngân hàng'
    _order = 'company_id, bank'

    name = fields.Char('Tên gọi', compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    bank = fields.Char('Ngân hàng', required=True)
    branch = fields.Char('Chi nhánh')
    number = fields.Char('Số tài khoản', required=True)
    currency_id = fields.Many2one('res.currency', 'Loại tiền', default=lambda s: s.env.ref('base.VND'))
    reconcile_from = fields.Date('Đối soát từ ngày', required=True, default=fields.Date.context_today,
                                 help='Dòng sổ 112 trước ngày này coi như đã đối chiếu; số dư đầu sổ phụ đầu tiên phải bằng '
                                      'số dư sổ kế toán ngày trước đó')
    active = fields.Boolean(default=True)

    _number_uniq = models.Constraint('unique(company_id, number)', 'Số tài khoản đã khai báo.')

    @api.depends('bank', 'number')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s - %s' % (rec.bank or '', rec.number or '')

    def _book_domain(self, date_to=None):
        """Dòng 112 thuộc tài khoản này; công ty chỉ có một tài khoản thì tính cả dòng chưa gán tài khoản."""
        self.ensure_one()
        domain = [('company_id', '=', self.company_id.id), ('state', '=', 'posted'), ('account_code', '=like', '112%')]
        single = self.search_count([('company_id', '=', self.company_id.id)]) == 1
        domain += ['|', ('bank_account_id', '=', self.id), ('bank_account_id', '=', False)] if single \
            else [('bank_account_id', '=', self.id)]
        if date_to:
            domain.append(('date', '<=', date_to))
        return domain


class LfoodMoveLine(models.Model):
    _inherit = 'lfood.move.line'

    bank_account_id = fields.Many2one('lfood.bank.account', 'Tài khoản ngân hàng', index=True)


class LfoodPayment(models.Model):
    _inherit = 'lfood.payment'

    bank_account_id = fields.Many2one('lfood.bank.account', 'Tài khoản ngân hàng',
                                      domain="[('company_id', '=', company_id)]")
    statement_line_id = fields.Many2one('lfood.bank.statement.line', 'Lập từ dòng sổ phụ', readonly=True, copy=False)

    def action_post(self):
        for rec in self.filtered(lambda p: p.state == 'draft' and p.method == 'bank' and not p.bank_account_id):
            accounts = self.env['lfood.bank.account'].search([('company_id', '=', rec.company_id.id)])
            if len(accounts) > 1:
                raise UserError(_('Công ty có nhiều tài khoản ngân hàng: chọn tài khoản cho phiếu %s.') % (rec.memo or ''))
            if accounts:
                rec.bank_account_id = accounts
        res = super().action_post()
        for rec in self.filtered(lambda p: p.state == 'posted' and p.bank_account_id):
            lines = self.env['lfood.move']._active_for(rec).line_ids.filtered(lambda l: l.account_code.startswith('112'))
            lines.with_context(lfood_ledger_system=True).write({'bank_account_id': rec.bank_account_id.id})
        return res


class LfoodBankStatement(models.Model):
    _name = 'lfood.bank.statement'
    _description = 'Sổ phụ ngân hàng'
    _order = 'date_to desc, id desc'

    name = fields.Char('Số', default='/', readonly=True, copy=False, index=True)
    bank_account_id = fields.Many2one('lfood.bank.account', 'Tài khoản ngân hàng', required=True, index=True)
    company_id = fields.Many2one(related='bank_account_id.company_id', store=True, index=True)
    date_from = fields.Date('Từ ngày', required=True)
    date_to = fields.Date('Đến ngày', required=True)
    balance_start = fields.Float('Số dư đầu sổ phụ', digits=(16, 0))
    balance_end = fields.Float('Số dư cuối sổ phụ', digits=(16, 0))
    import_file = fields.Binary('Tệp CSV', attachment=False)
    import_filename = fields.Char('Tên tệp')
    line_ids = fields.One2many('lfood.bank.statement.line', 'statement_id', 'Giao dịch')
    lines_total = fields.Float('Tổng phát sinh', digits=(16, 0), compute='_compute_recon')
    book_balance = fields.Float('Số dư sổ kế toán 112', digits=(16, 0), compute='_compute_recon')
    book_only = fields.Float('Sổ đã ghi, ngân hàng chưa ghi', digits=(16, 0), compute='_compute_recon')
    bank_only = fields.Float('Ngân hàng đã ghi, sổ chưa có', digits=(16, 0), compute='_compute_recon')
    difference = fields.Float('Chênh lệch còn lại', digits=(16, 0), compute='_compute_recon')
    statement_error = fields.Char('Sổ phụ không khớp', compute='_compute_recon')
    report_html = fields.Html('Bảng đối chiếu', compute='_compute_recon', sanitize=False)
    state = fields.Selection([('draft', 'Đang đối soát'), ('done', 'Đã đối soát xong')], 'Trạng thái', default='draft',
                             required=True, readonly=True, copy=False, index=True)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_to < rec.date_from:
                raise ValidationError(_('Ngày cuối phải sau ngày đầu.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('lfood.bank.statement') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_bank_system') and self.filtered(lambda r: r.state == 'done'):
            raise UserError(_('Sổ phụ đã đối soát xong không sửa được.'))
        return super().write(vals)

    def _matched_line_ids(self):
        return set(self.env['lfood.bank.statement.line'].search([
            ('statement_id.bank_account_id', '=', self.bank_account_id.id),
            ('move_line_id', '!=', False)]).mapped('move_line_id').ids)

    def _outstanding_book_lines(self):
        """Dòng 112 đến ngày cuối kỳ chưa khớp với sổ phụ nào."""
        self.ensure_one()
        lines = self.env['lfood.move.line'].search(self.bank_account_id._book_domain(self.date_to), order='date, id')
        matched = self._matched_line_ids()
        start = self.bank_account_id.reconcile_from
        return lines.filtered(lambda l: l.id not in matched and l.date >= start)

    @api.depends('line_ids.amount', 'line_ids.move_line_id', 'balance_start', 'balance_end', 'date_to', 'bank_account_id')
    def _compute_recon(self):
        ML = self.env['lfood.move.line']
        for rec in self:
            if not (rec.bank_account_id and rec.date_to):
                rec.update({'lines_total': 0, 'book_balance': 0, 'book_only': 0, 'bank_only': 0, 'difference': 0,
                            'statement_error': False, 'report_html': False})
                continue
            ML.flush_model()
            rec.lines_total = sum(rec.line_ids.mapped('amount'))
            rec.book_balance = round(sum(ML.search(rec.bank_account_id._book_domain(rec.date_to)).mapped('balance')))
            outstanding = rec._outstanding_book_lines() if rec.id else ML
            unmatched_bank = rec.line_ids.filtered(lambda l: not l.move_line_id)
            rec.book_only = round(sum(outstanding.mapped('balance')))
            rec.bank_only = round(sum(unmatched_bank.mapped('amount')))
            rec.difference = round(rec.book_balance - rec.book_only + rec.bank_only - rec.balance_end)
            gap = round(rec.balance_start + rec.lines_total - rec.balance_end)
            rec.statement_error = _('Số dư đầu cộng phát sinh lệch số dư cuối %s') % vnd(gap) if gap else False
            rows = ''.join('<tr><td>%s</td><td>%s</td><td class="text-end">%s</td></tr>' % (
                l.date.strftime('%d/%m/%Y'), ' '.join(filter(None, [l.move_id.ref, l.name])), vnd(l.balance))
                for l in outstanding)
            rows_b = ''.join('<tr><td>%s</td><td>%s</td><td class="text-end">%s</td></tr>' % (
                l.date.strftime('%d/%m/%Y'), l.description or '', vnd(l.amount)) for l in unmatched_bank)
            rec.report_html = (
                '<h4>BẢNG ĐỐI CHIẾU SỐ DƯ TIỀN GỬI NGÂN HÀNG</h4><p>%s, đến ngày %s</p>'
                '<table class="table table-sm"><tbody>'
                '<tr><td>Số dư sổ kế toán TK 112</td><td class="text-end">%s</td></tr>'
                '<tr><td>Trừ: sổ đã ghi, ngân hàng chưa ghi</td><td class="text-end">%s</td></tr>'
                '<tr><td>Cộng: ngân hàng đã ghi, sổ chưa có</td><td class="text-end">%s</td></tr>'
                '<tr><td><b>Số dư sau điều chỉnh</b></td><td class="text-end"><b>%s</b></td></tr>'
                '<tr><td>Số dư cuối sổ phụ ngân hàng</td><td class="text-end">%s</td></tr>'
                '<tr><td><b>Chênh lệch</b></td><td class="text-end"><b>%s</b></td></tr></tbody></table>'
                '<h5>Sổ đã ghi, ngân hàng chưa ghi</h5><table class="table table-sm"><tbody>%s</tbody></table>'
                '<h5>Ngân hàng đã ghi, sổ chưa có</h5><table class="table table-sm"><tbody>%s</tbody></table>') % (
                rec.bank_account_id.name, rec.date_to.strftime('%d/%m/%Y'), vnd(rec.book_balance), vnd(rec.book_only),
                vnd(rec.bank_only), vnd(rec.book_balance - rec.book_only + rec.bank_only), vnd(rec.balance_end),
                vnd(rec.difference), rows or '<tr><td>Không có</td></tr>', rows_b or '<tr><td>Không có</td></tr>')

    def action_import(self):
        """Tệp CSV có dòng tiêu đề: ngay (dd/mm/yyyy), so_tham_chieu, noi_dung, tien_ra, tien_vao."""
        self.ensure_one()
        if not self.import_file:
            raise UserError(_('Chọn tệp CSV sổ phụ.'))
        text = base64.b64decode(self.import_file).decode('utf-8-sig')
        dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=',;\t')
        vals = []
        for i, row in enumerate(csv.DictReader(io.StringIO(text), dialect=dialect), start=2):
            row = {(k or '').strip().lower(): (v or '').strip() for k, v in row.items()}
            try:
                day = datetime.strptime(row['ngay'], '%d/%m/%Y').date()
                out = float(row.get('tien_ra') or 0)
                inn = float(row.get('tien_vao') or 0)
            except (KeyError, ValueError):
                raise UserError(_('Dòng %s của tệp sai định dạng. Cột cần có: ngay, so_tham_chieu, noi_dung, tien_ra, tien_vao; '
                                  'ngày dạng dd/mm/yyyy, số tiền không có dấu phân cách.') % i)
            if not (self.date_from <= day <= self.date_to):
                raise UserError(_('Dòng %s ngày %s nằm ngoài kỳ sổ phụ.') % (i, row['ngay']))
            vals.append((0, 0, {'date': day, 'ref': row.get('so_tham_chieu'), 'description': row.get('noi_dung'),
                                'amount': inn - out}))
        self.write({'line_ids': vals, 'import_file': False})
        return True

    def action_match(self):
        """Khớp tự động: cùng số tiền và chiều, chênh ngày không quá MATCH_DAYS; ưu tiên trùng số tham chiếu, rồi ngày gần."""
        for rec in self:
            pool = rec._outstanding_book_lines()
            for line in rec.line_ids.filtered(lambda l: not l.move_line_id).sorted('date'):
                cands = pool.filtered(lambda m: round(m.balance) == round(line.amount)
                                      and abs((m.date - line.date).days) <= MATCH_DAYS)
                if not cands:
                    continue
                ref = (line.ref or '').lower()
                best = sorted(cands, key=lambda m: (
                    not (ref and ref in ('%s %s' % (m.move_id.ref or '', m.name or '')).lower()),
                    abs((m.date - line.date).days), m.id))[0]
                line.move_line_id = best
                pool -= best
        return True

    def action_done(self):
        for rec in self:
            if rec.statement_error:
                raise UserError(rec.statement_error)
            if rec.line_ids.filtered(lambda l: not l.move_line_id):
                raise UserError(_('Còn giao dịch ngân hàng chưa khớp. Lập phiếu thu chi cho các khoản này rồi khớp lại.'))
            if rec.difference:
                raise UserError(_('Bảng đối chiếu còn chênh lệch %s.') % vnd(rec.difference))
            rec.with_context(lfood_bank_system=True).write({'state': 'done'})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Đối soát xong %s đến %s: số dư %s') % (
                    rec.bank_account_id.name, rec.date_to.strftime('%d/%m/%Y'), vnd(rec.balance_end)))
        return True

    def action_reopen(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được mở lại sổ phụ đã đối soát.'))
        self.with_context(lfood_bank_system=True).write({'state': 'draft'})
        return True


class LfoodBankStatementLine(models.Model):
    _name = 'lfood.bank.statement.line'
    _description = 'Giao dịch trên sổ phụ ngân hàng'
    _order = 'date, id'

    statement_id = fields.Many2one('lfood.bank.statement', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='statement_id.company_id', store=True)
    date = fields.Date('Ngày', required=True)
    ref = fields.Char('Số tham chiếu')
    description = fields.Char('Nội dung')
    amount = fields.Float('Số tiền (+ vào, - ra)', digits=(16, 0), required=True)
    move_line_id = fields.Many2one('lfood.move.line', 'Dòng sổ 112 đã khớp', index=True,
                                   domain="[('company_id', '=', company_id), ('state', '=', 'posted'), "
                                          "('account_code', '=like', '112%')]")
    payment_ids = fields.One2many('lfood.payment', 'statement_line_id', 'Phiếu lập từ dòng này')

    _move_line_uniq = models.Constraint('unique(move_line_id)', 'Dòng sổ 112 này đã khớp với giao dịch khác.')

    @api.constrains('move_line_id', 'amount')
    def _check_match(self):
        for rec in self.filtered('move_line_id'):
            if round(rec.move_line_id.balance) != round(rec.amount):
                raise ValidationError(_('Dòng sổ %s số tiền %s không bằng giao dịch ngân hàng %s.') % (
                    rec.move_line_id.move_id.ref or '', vnd(rec.move_line_id.balance), vnd(rec.amount)))

    def write(self, vals):
        if not self.env.context.get('lfood_bank_system') and self.filtered(lambda l: l.statement_id.state == 'done'):
            raise UserError(_('Sổ phụ đã đối soát xong không sửa được.'))
        return super().write(vals)

    def action_make_payment(self):
        """Lập phiếu thu chi nháp cho khoản ngân hàng đã ghi mà sổ chưa có (phí, lãi tiền gửi...)."""
        self.ensure_one()
        if self.move_line_id:
            raise UserError(_('Giao dịch đã khớp với sổ.'))
        income = self.amount > 0
        payment = self.env['lfood.payment'].create({
            'company_id': self.company_id.id, 'kind': 'in' if income else 'out', 'method': 'bank',
            'purpose': 'other' if income else 'expense', 'date': self.date, 'amount': abs(self.amount),
            'memo': self.description or self.ref or _('Giao dịch theo sổ phụ'),
            'bank_account_id': self.statement_id.bank_account_id.id, 'statement_line_id': self.id,
            'cash_account': '112', 'counterpart_account': '515' if income else '6427'})
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.payment', 'res_id': payment.id, 'view_mode': 'form'}
