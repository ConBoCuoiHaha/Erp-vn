"""Bảng nhập liệu: một lưới giống sổ Nhật ký chung trong Excel, mỗi dòng là một vế Nợ - Có.

Nhập xong bấm Kiểm tra để soát theo ràng buộc đã cấu hình, rồi Ghi sổ để sinh bút toán hàng loạt.
Ô Ngày, Số chứng từ, Diễn giải bỏ trống thì lấy của dòng ngay trên, giống kéo ô trong Excel.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_ledger.models.move import JOURNALS
from odoo.addons.lfood_voucher.models.tools import vnd

INHERIT = ('date', 'ref', 'memo')


class LfoodEntrySheet(models.Model):
    _name = 'lfood.entry.sheet'
    _description = 'Bảng nhập liệu'
    _order = 'id desc'

    name = fields.Char('Tên bảng', required=True,
                       default=lambda s: _('Nhập liệu %s') % fields.Date.context_today(s).strftime('%d/%m/%Y'))
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    journal = fields.Selection(JOURNALS, 'Sổ nhật ký', required=True, default='general')
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ')], 'Trạng thái', default='draft',
                             readonly=True, copy=False)
    line_ids = fields.One2many('lfood.entry.line', 'sheet_id', 'Các dòng', copy=True)
    move_ids = fields.One2many('lfood.move', 'entry_sheet_id', 'Bút toán đã sinh', readonly=True)
    move_count = fields.Integer('Số bút toán', compute='_compute_totals')
    total_debit = fields.Float('Cộng Nợ', digits=(16, 0), compute='_compute_totals')
    total_credit = fields.Float('Cộng Có', digits=(16, 0), compute='_compute_totals')
    error_count = fields.Integer('Số dòng còn lỗi', compute='_compute_totals')
    note = fields.Char('Ghi chú')

    @api.depends('line_ids.amount', 'line_ids.debit_account_id', 'line_ids.credit_account_id', 'line_ids.error', 'move_ids')
    def _compute_totals(self):
        for rec in self:
            rec.total_debit = sum(l.amount for l in rec.line_ids if l.debit_account_id)
            rec.total_credit = sum(l.amount for l in rec.line_ids if l.credit_account_id)
            rec.error_count = len(rec.line_ids.filtered('error'))
            rec.move_count = len(rec.move_ids)

    def _fill_down(self):
        """Ô Ngày, Số chứng từ, Diễn giải để trống thì lấy của dòng trên (giống kéo ô trong Excel)."""
        for rec in self:
            prev = {}
            for line in rec.line_ids.sorted(lambda l: (l.sequence, l.id)):
                missing = {f: prev[f] for f in INHERIT if not line[f] and prev.get(f)}
                if missing:
                    line.write(missing)
                prev = {f: line[f] for f in INHERIT}

    def _groups(self):
        """Gộp các dòng cùng ngày, cùng số chứng từ thành một bút toán."""
        self.ensure_one()
        groups = {}
        for line in self.line_ids.sorted(lambda l: (l.sequence, l.id)):
            groups.setdefault((line.date, line.ref or ''), []).append(line)
        return groups

    def _check_lines(self):
        """Ghi lỗi vào từng dòng, trả về True nếu cả bảng hợp lệ."""
        self.ensure_one()
        self._fill_down()
        rules = self.env['lfood.entry.rule']._for_company(self.company_id)
        for line in self.line_ids:
            line.error = ' | '.join(line._errors(rules)) or False
        for (day, ref), lines in self._groups().items():
            debit = round(sum(l.amount for l in lines if l.debit_account_id))
            credit = round(sum(l.amount for l in lines if l.credit_account_id))
            if debit != credit:
                msg = _('Bút toán ngày %s chứng từ %s không cân: Nợ %s, Có %s') % (
                    day.strftime('%d/%m/%Y') if day else '?', ref or _('(trống)'), vnd(debit), vnd(credit))
                for line in lines:
                    line.error = '%s | %s' % (line.error, msg) if line.error else msg
        return not self.line_ids.filtered('error')

    def action_check(self):
        for rec in self:
            rec._check_lines()
        return True

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được ghi sổ.'))
        Move = self.env['lfood.move']
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.line_ids:
                raise UserError(_('Bảng chưa có dòng nào.'))
            if not rec._check_lines():
                raise UserError(_('Còn %s dòng chưa hợp lệ, xem cột Lỗi.') % len(rec.line_ids.filtered('error')))
            moves = Move.browse()
            for (day, ref), lines in rec._groups().items():
                vals = []
                for line in lines:
                    for account, debit, credit in ((line.debit_account_id, line.amount, 0),
                                                   (line.credit_account_id, 0, line.amount)):
                        if account:
                            vals.append((0, 0, {'account_id': account.id, 'debit': debit, 'credit': credit,
                                                'partner_id': line.partner_id.id, 'name': line.memo,
                                                'cost_item_id': line.cost_item_id.id}))
                move = Move.create({'company_id': rec.company_id.id, 'journal': rec.journal, 'date': day, 'ref': ref,
                                    'memo': lines[0].memo or rec.name, 'entry_sheet_id': rec.id, 'line_ids': vals})
                move._post()
                moves |= move
            rec.state = 'posted'
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Ghi sổ bảng nhập liệu %s: %s dòng thành %s bút toán, tổng %s')
                % (rec.name, len(rec.line_ids), len(moves), vnd(rec.total_debit)))
        return True

    def action_open_moves(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Bút toán từ %s') % self.name, 'res_model': 'lfood.move',
                'view_mode': 'list,form', 'domain': [('entry_sheet_id', '=', self.id)]}

    def write(self, vals):
        if self.filtered(lambda r: r.state == 'posted') and set(vals) - {'note'}:
            raise UserError(_('Bảng đã ghi sổ không sửa được. Hãy đảo bút toán rồi lập bảng mới.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda r: r.state == 'posted'):
            raise UserError(_('Bảng đã ghi sổ không xóa được.'))
        return super().unlink()


class LfoodEntryLine(models.Model):
    _name = 'lfood.entry.line'
    _description = 'Dòng bảng nhập liệu'
    _order = 'sequence, id'

    sheet_id = fields.Many2one('lfood.entry.sheet', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='sheet_id.company_id', store=True, index=True)
    sequence = fields.Integer('Thứ tự', default=10)
    date = fields.Date('Ngày')
    ref = fields.Char('Số chứng từ')
    memo = fields.Char('Diễn giải')
    debit_account_id = fields.Many2one('lfood.account', 'TK Nợ', domain=[('allow_posting', '=', True)])
    credit_account_id = fields.Many2one('lfood.account', 'TK Có', domain=[('allow_posting', '=', True)])
    amount = fields.Float('Số tiền', digits=(16, 0))
    partner_id = fields.Many2one('res.partner', 'Đối tượng')
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP')
    error = fields.Char('Lỗi', readonly=True, copy=False)

    def _errors(self, rules):
        """Lỗi của riêng dòng: thiếu dữ liệu, khóa sổ, và các ràng buộc tự cấu hình."""
        self.ensure_one()
        out = []
        if not self.date:
            out.append(_('Thiếu ngày'))
        if round(self.amount or 0) <= 0:
            out.append(_('Số tiền phải lớn hơn 0'))
        if not self.debit_account_id and not self.credit_account_id:
            out.append(_('Phải có ít nhất một tài khoản'))
        if self.debit_account_id and self.debit_account_id == self.credit_account_id:
            out.append(_('TK Nợ và TK Có trùng nhau'))
        lock = self.sheet_id.company_id.lfood_lock_date
        if self.date and lock and self.date <= lock:
            out.append(_('Kỳ đến %s đã khóa sổ') % lock.strftime('%d/%m/%Y'))
        for account, side in ((self.debit_account_id, 'debit'), (self.credit_account_id, 'credit')):
            if not account:
                continue
            if not account.allow_posting:
                out.append(_('TK %s có tài khoản con, phải ghi vào tài khoản chi tiết') % account.code)
            if account.track_partner and not self.partner_id:
                out.append(_('TK %s phải ghi đối tượng') % account.code)
            out += rules._errors(account, side, round(self.amount or 0), self.partner_id, self.cost_item_id,
                                 self.memo, self.ref)
        return out


class LfoodMove(models.Model):
    _inherit = 'lfood.move'

    entry_sheet_id = fields.Many2one('lfood.entry.sheet', 'Bảng nhập liệu', readonly=True, copy=False, index=True)
