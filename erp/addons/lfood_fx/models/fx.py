"""Ngoại tệ trên bút toán và đánh giá lại khoản mục tiền tệ có gốc ngoại tệ cuối kỳ (KT11).

Mỗi dòng bút toán có thể ghi loại ngoại tệ và số nguyên tệ (dấu theo Nợ trừ Có). Cuối kỳ, app cộng số dư
nguyên tệ và số dư đồng Việt Nam theo từng tài khoản, đối tượng, loại ngoại tệ; quy đổi theo tỷ giá kế toán
nhập (tỷ giá mua bán chuyển khoản trung bình của ngân hàng thương mại nơi thường xuyên giao dịch) rồi ghi
phần chênh lệch. Dòng chênh lệch vẫn mang loại ngoại tệ với số nguyên tệ bằng 0 để lần đánh giá sau cộng đúng.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd
from .fx_calc import average_rate, revalue, net_result

# khoản mục tiền tệ: tiền, tiền đang chuyển, phải thu, phải trả, vay
MONETARY_PREFIXES = ('111', '112', '113', '131', '136', '138', '141', '244', '331', '334', '336', '338', '341')


class LfoodMoveLine(models.Model):
    _inherit = 'lfood.move.line'

    currency_id = fields.Many2one('res.currency', 'Ngoại tệ', index=True,
                                  domain="[('name', '!=', 'VND')]")
    amount_currency = fields.Float('Số nguyên tệ', digits=(16, 2),
                                   help='Dương khi ghi Nợ, âm khi ghi Có, cùng chiều với số tiền đồng Việt Nam')

    @api.constrains('currency_id', 'amount_currency', 'debit', 'credit')
    def _check_currency(self):
        for rec in self:
            if rec.amount_currency and not rec.currency_id:
                raise ValidationError(_('Dòng có số nguyên tệ phải chọn loại ngoại tệ.'))
            balance = (rec.debit or 0) - (rec.credit or 0)
            if rec.amount_currency and balance and (rec.amount_currency > 0) != (balance > 0):
                raise ValidationError(_('Số nguyên tệ phải cùng chiều Nợ, Có với số tiền đồng Việt Nam (tài khoản %s).')
                                      % rec.account_id.code)


class LfoodFxRevaluation(models.Model):
    _name = 'lfood.fx.revaluation'
    _description = 'Đánh giá lại ngoại tệ cuối kỳ'
    _order = 'date desc, id desc'

    name = fields.Char('Số chứng từ', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    date = fields.Date('Ngày đánh giá lại', required=True, default=fields.Date.context_today, index=True)
    bank = fields.Char('Ngân hàng lấy tỷ giá', required=True,
                       help='Ngân hàng thương mại nơi doanh nghiệp thường xuyên có giao dịch')
    rate_ids = fields.One2many('lfood.fx.revaluation.rate', 'revaluation_id', 'Tỷ giá cuối kỳ', copy=True)
    line_ids = fields.One2many('lfood.fx.revaluation.line', 'revaluation_id', 'Chi tiết')
    gain = fields.Float('Tổng lãi', digits=(16, 0), compute='_compute_totals', store=True)
    loss = fields.Float('Tổng lỗ', digits=(16, 0), compute='_compute_totals', store=True)
    net = fields.Float('Số thuần', digits=(16, 0), compute='_compute_totals', store=True,
                       help='Dương ghi Có 515, âm ghi Nợ 635')
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)

    @api.depends('line_ids.diff')
    def _compute_totals(self):
        for rec in self:
            rec.gain, rec.loss, rec.net = net_result(rec.line_ids.mapped('diff'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.fx.revaluation') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_fx_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái chỉ đổi bằng nút Ghi sổ, Hủy.'))
            if self.filtered(lambda r: r.state != 'draft'):
                raise UserError(_('Chứng từ đã ghi sổ không sửa được.'))
        return super().write(vals)

    def _groups(self):
        """[(tài khoản, đối tượng, ngoại tệ, số dư nguyên tệ, số dư đồng)] tại ngày đánh giá."""
        self.ensure_one()
        self.env['lfood.move.line'].flush_model()
        clause = ' OR '.join(['a.code LIKE %s'] * len(MONETARY_PREFIXES))
        self.env.cr.execute("""
            SELECT l.account_id, l.partner_id, l.currency_id,
                   COALESCE(SUM(l.amount_currency), 0), COALESCE(SUM(l.balance), 0)
            FROM lfood_move_line l JOIN lfood_account a ON a.id = l.account_id
            WHERE l.company_id = %s AND l.state = 'posted' AND l.date <= %s AND l.currency_id IS NOT NULL
              AND (""" + clause + """)
            GROUP BY l.account_id, l.partner_id, l.currency_id
            ORDER BY l.account_id, l.partner_id, l.currency_id""",
                            [self.company_id.id, self.date] + [p + '%' for p in MONETARY_PREFIXES])
        return self.env.cr.fetchall()

    def action_load(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Chỉ lấy số dư khi chứng từ còn là Nháp.'))
        self.line_ids.unlink()
        rates = {r.currency_id.id: r.rate for r in self.rate_ids}
        Line = self.env['lfood.fx.revaluation.line']
        missing = set()
        for account_id, partner_id, currency_id, amount_currency, book in self._groups():
            if not round(amount_currency, 2) and not round(book):
                continue
            if currency_id not in rates:
                missing.add(currency_id)
                continue
            Line.create({'revaluation_id': self.id, 'account_id': account_id, 'partner_id': partner_id,
                         'currency_id': currency_id, 'amount_currency': amount_currency, 'book_value': round(book),
                         'rate': rates[currency_id]})
        if missing:
            names = ', '.join(self.env['res.currency'].browse(list(missing)).mapped('name'))
            raise UserError(_('Nhập tỷ giá cuối kỳ cho ngoại tệ: %s.') % names)
        return True

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được ghi sổ đánh giá lại ngoại tệ.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.line_ids:
                raise UserError(_('Chưa có số dư ngoại tệ nào để đánh giá lại.'))
            label = _('Đánh giá lại ngoại tệ ngày %s theo tỷ giá %s') % (rec.date.strftime('%d/%m/%Y'), rec.bank)
            lines = []
            for l in rec.line_ids.filtered('diff'):
                extra = {'currency_id': l.currency_id.id, 'amount_currency': 0.0}
                lines.append((l.account_id.code, max(l.diff, 0), max(-l.diff, 0), l.partner_id, label, None, extra))
            if rec.net > 0:
                lines.append(('515', 0, rec.net, None, label, None))
            elif rec.net < 0:
                lines.append(('635', -rec.net, 0, None, label, None))
            if lines:
                self.env['lfood.move']._create_from_source(rec, 'general', rec.date, lines, memo=label, ref=rec.name)
            rec.with_context(lfood_fx_system=True).write({'state': 'posted'})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('%s: lãi %s, lỗ %s, số thuần %s') % (label, vnd(rec.gain), vnd(rec.loss), vnd(rec.net)))
        return True

    def action_cancel(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được hủy.'))
        for rec in self.filtered(lambda r: r.state == 'posted'):
            move = self.env['lfood.move']._active_for(rec)
            if move:
                move._reverse(memo=_('Hủy %s') % rec.name)
            rec.with_context(lfood_fx_system=True).write({'state': 'cancel'})
        return True


class LfoodFxRevaluationRate(models.Model):
    _name = 'lfood.fx.revaluation.rate'
    _description = 'Tỷ giá đánh giá lại'

    revaluation_id = fields.Many2one('lfood.fx.revaluation', required=True, ondelete='cascade', index=True)
    currency_id = fields.Many2one('res.currency', 'Ngoại tệ', required=True, domain="[('name', '!=', 'VND')]")
    buy_rate = fields.Float('Tỷ giá mua chuyển khoản', digits=(16, 4), required=True)
    sell_rate = fields.Float('Tỷ giá bán chuyển khoản', digits=(16, 4), required=True)
    rate = fields.Float('Tỷ giá trung bình', digits=(16, 4), compute='_compute_rate', store=True)

    _currency_uniq = models.Constraint('unique(revaluation_id, currency_id)', 'Mỗi ngoại tệ chỉ nhập một dòng tỷ giá.')

    @api.depends('buy_rate', 'sell_rate')
    def _compute_rate(self):
        for rec in self:
            rec.rate = average_rate(rec.buy_rate, rec.sell_rate)

    @api.constrains('buy_rate', 'sell_rate')
    def _check_rates(self):
        for rec in self:
            if rec.buy_rate <= 0 or rec.sell_rate <= 0 or rec.buy_rate > rec.sell_rate:
                raise ValidationError(_('Tỷ giá phải lớn hơn 0 và tỷ giá mua không lớn hơn tỷ giá bán.'))


class LfoodFxRevaluationLine(models.Model):
    _name = 'lfood.fx.revaluation.line'
    _description = 'Dòng đánh giá lại ngoại tệ'
    _order = 'revaluation_id, account_id, partner_id'

    revaluation_id = fields.Many2one('lfood.fx.revaluation', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='revaluation_id.company_id', store=True)
    account_id = fields.Many2one('lfood.account', 'Tài khoản', required=True)
    partner_id = fields.Many2one('res.partner', 'Đối tượng')
    currency_id = fields.Many2one('res.currency', 'Ngoại tệ', required=True)
    amount_currency = fields.Float('Số dư nguyên tệ', digits=(16, 2), readonly=True)
    book_value = fields.Float('Số dư trên sổ (đồng)', digits=(16, 0), readonly=True)
    rate = fields.Float('Tỷ giá cuối kỳ', digits=(16, 4), readonly=True)
    revalued = fields.Float('Quy đổi theo tỷ giá cuối kỳ', digits=(16, 0), compute='_compute_diff', store=True)
    diff = fields.Float('Chênh lệch', digits=(16, 0), compute='_compute_diff', store=True,
                        help='Dương là lãi, âm là lỗ')

    @api.depends('amount_currency', 'book_value', 'rate')
    def _compute_diff(self):
        for rec in self:
            rec.revalued = round(rec.amount_currency * rec.rate)
            rec.diff = revalue(rec.amount_currency, rec.book_value, rec.rate)
