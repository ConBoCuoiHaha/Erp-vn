from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd

JOURNALS = [
    ('purchase', 'Mua hàng, dịch vụ'),
    ('cash', 'Tiền mặt'),
    ('bank', 'Tiền gửi'),
    ('asset', 'Tài sản cố định'),
    ('depreciation', 'Khấu hao'),
    ('general', 'Phiếu kế toán'),
    ('opening', 'Số dư đầu kỳ'),
    ('closing', 'Kết chuyển cuối kỳ'),
]
SYSTEM_FIELDS = {'state', 'name', 'posted_by', 'posted_on', 'reversed_by_id', 'reversal_of_id', 'source_model',
                 'source_id', 'source_key'}


class LfoodMove(models.Model):
    _name = 'lfood.move'
    _description = 'Bút toán'
    _order = 'date desc, id desc'

    name = fields.Char('Số bút toán', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    journal = fields.Selection(JOURNALS, 'Sổ nhật ký', required=True, default='general', index=True)
    date = fields.Date('Ngày hạch toán', required=True, default=fields.Date.context_today, index=True)
    ref = fields.Char('Số chứng từ gốc')
    memo = fields.Char('Diễn giải')
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ')], 'Trạng thái', default='draft',
                             readonly=True, copy=False, index=True)
    line_ids = fields.One2many('lfood.move.line', 'move_id', 'Định khoản', copy=True)
    amount = fields.Float('Tổng phát sinh', digits=(16, 0), compute='_compute_amount', store=True)
    source_model = fields.Char('Nguồn', readonly=True, copy=False, index=True)
    source_id = fields.Integer('Mã nguồn', readonly=True, copy=False, index=True)
    source_key = fields.Char('Khóa nguồn', readonly=True, copy=False, index=True,
                             help='Ví dụ phiên bản chứng từ đã ghi sổ; đổi phiên bản báo cáo thì đảo bút toán cũ')
    source_display = fields.Char('Chứng từ nguồn', compute='_compute_source_display')
    reversal_of_id = fields.Many2one('lfood.move', 'Đảo của bút toán', readonly=True, copy=False, index=True)
    reversed_by_id = fields.Many2one('lfood.move', 'Bị đảo bởi', readonly=True, copy=False, index=True)
    posted_by = fields.Many2one('res.users', 'Người ghi sổ', readonly=True, copy=False)
    posted_on = fields.Datetime('Thời điểm ghi sổ', readonly=True, copy=False)

    @api.depends('line_ids.debit')
    def _compute_amount(self):
        for rec in self:
            rec.amount = sum(rec.line_ids.mapped('debit'))

    def _compute_source_display(self):
        for rec in self:
            src = rec.source_model and self.env[rec.source_model].sudo().browse(rec.source_id).exists()
            rec.source_display = src.display_name if src else False

    # ------------------------------------------------------------ bảo vệ
    def write(self, vals):
        if not self.env.context.get('lfood_ledger_system'):
            if SYSTEM_FIELDS & set(vals):
                raise UserError(_('Trạng thái bút toán chỉ đổi bằng nút Ghi sổ, Đảo bút toán.'))
            if self.filtered(lambda m: m.state == 'posted'):
                raise UserError(_('Bút toán đã ghi sổ không sửa được. Hãy Đảo bút toán rồi lập bút toán mới.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda m: m.state == 'posted'):
            raise UserError(_('Bút toán đã ghi sổ không xóa được. Hãy Đảo bút toán.'))
        return super().unlink()

    def _check_lock(self, date=None):
        for rec in self:
            lock = rec.company_id.lfood_lock_date
            d = date or rec.date
            if lock and d <= lock:
                raise UserError(_('Kỳ kế toán đến ngày %s đã khóa sổ, không ghi được bút toán ngày %s.')
                                % (lock.strftime('%d/%m/%Y'), d.strftime('%d/%m/%Y')))

    # ------------------------------------------------------------ ghi sổ
    def _post(self):
        for rec in self:
            if rec.state == 'posted':
                continue
            lines = rec.line_ids
            if not lines:
                raise UserError(_('Bút toán chưa có dòng định khoản.'))
            debit, credit = round(sum(lines.mapped('debit'))), round(sum(lines.mapped('credit')))
            if debit != credit or debit == 0:
                raise UserError(_('Bút toán không cân: Nợ %s, Có %s.') % (vnd(debit), vnd(credit)))
            for line in lines:
                if not line.account_id.allow_posting:
                    raise UserError(_('Tài khoản %s có tài khoản con, phải hạch toán vào tài khoản chi tiết.') % line.account_id.code)
                if line.account_id.track_partner and not line.partner_id and rec.journal != 'closing':
                    raise UserError(_('Tài khoản %s phải ghi đối tượng (nhà cung cấp, khách hàng, nhân viên).') % line.account_id.code)
            rec._check_lock()
            name = rec.name if rec.name != '/' else self.env['ir.sequence'].with_company(rec.company_id).next_by_code('lfood.move.%s' % rec.journal) or '/'
            rec.with_context(lfood_ledger_system=True).write({
                'name': name, 'state': 'posted', 'posted_by': self.env.uid, 'posted_on': fields.Datetime.now()})
        return True

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được ghi sổ.'))
        for rec in self:
            if rec.source_model:
                raise UserError(_('Bút toán sinh từ chứng từ nguồn, ghi sổ tại chứng từ đó.'))
        self._post()
        for rec in self:
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=rec.name,
                                                      company_id=rec.company_id.id,
                                                      summary=_('Ghi sổ %s %s, tổng %s') % (dict(JOURNALS)[rec.journal], rec.name, vnd(rec.amount)))
        return True

    def _reverse(self, date=None, memo=None):
        """Đảo bút toán: lập bút toán ngược dấu. Kỳ gốc đã khóa thì ghi vào ngày được truyền (thường là hôm nay)."""
        reversals = self.browse()
        for rec in self.filtered(lambda m: m.state == 'posted' and not m.reversed_by_id and not m.reversal_of_id):
            rdate = date or rec.date
            lock = rec.company_id.lfood_lock_date
            if lock and rdate <= lock:
                rdate = fields.Date.context_today(self)
            rev = self.sudo().with_context(lfood_ledger_system=True).create({
                'company_id': rec.company_id.id, 'journal': rec.journal, 'date': rdate, 'ref': rec.ref,
                'memo': memo or _('Đảo bút toán %s') % rec.name,
                'source_model': rec.source_model, 'source_id': rec.source_id, 'source_key': rec.source_key,
                'reversal_of_id': rec.id,
                'line_ids': [(0, 0, {'account_id': l.account_id.id, 'partner_id': l.partner_id.id, 'name': l.name,
                                     'debit': l.credit, 'credit': l.debit, 'cost_item_id': l.cost_item_id.id})
                             for l in rec.line_ids],
            })
            rev.with_user(self.env.uid)._post()
            rec.with_context(lfood_ledger_system=True).write({'reversed_by_id': rev.id})
            reversals |= rev
        return reversals

    def action_reverse(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được đảo bút toán.'))
        for rec in self:
            if rec.source_model and rec.journal != 'closing':
                raise UserError(_('Bút toán sinh từ chứng từ nguồn: hãy Hủy tại chứng từ đó để hệ thống tự đảo.'))
        revs = self._reverse(date=fields.Date.context_today(self))
        for rev in revs:
            self.env['lfood.audit.log']._record_event('state', model=rev._name, res_id=rev.reversal_of_id.id,
                                                      res_name=rev.reversal_of_id.name, company_id=rev.company_id.id,
                                                      summary=_('Đảo bút toán %s bằng %s') % (rev.reversal_of_id.name, rev.name))
        return True

    def action_view_audit(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Nhật ký bút toán'), 'res_model': 'lfood.audit.log',
                'view_mode': 'list,form', 'domain': [('model', '=', self._name), ('res_id', '=', self.id)]}

    def action_open_source(self):
        self.ensure_one()
        if not self.source_model:
            return False
        return {'type': 'ir.actions.act_window', 'res_model': self.source_model, 'res_id': self.source_id,
                'view_mode': 'form', 'target': 'current'}

    # ------------------------------------------------------------ dùng cho các phân hệ
    @api.model
    def _create_from_source(self, source, journal, date, lines, memo, key=None, ref=None, company=None):
        """lines: [(mã TK, Nợ, Có, đối tượng, diễn giải, khoản mục[, trường bổ sung])] — gộp dòng 0, tự ghi sổ.

        Phần tử thứ bảy (không bắt buộc) là dict giá trị thêm cho dòng, ví dụ ngoại tệ.
        """
        Account = self.env['lfood.account']
        vals = []
        for code, debit, credit, partner, name, cost_item, *extra in lines:
            debit, credit = round(debit or 0), round(credit or 0)
            if not debit and not credit:
                continue
            line = {'account_id': Account.by_code(code).id, 'debit': debit, 'credit': credit,
                    'partner_id': partner.id if partner else False, 'name': name,
                    'cost_item_id': cost_item.id if cost_item else False}
            if extra and extra[0]:
                line.update(extra[0])
            vals.append((0, 0, line))
        if not vals:
            return self.browse()
        move = self.sudo().with_context(lfood_ledger_system=True).create({
            'company_id': (company or source.company_id).id, 'journal': journal, 'date': date, 'memo': memo,
            'ref': ref or source.display_name, 'source_model': source._name, 'source_id': source.id,
            'source_key': key or str(source.id), 'line_ids': vals,
        })
        move.with_user(self.env.uid)._post()
        return move

    @api.model
    def _active_for(self, source):
        return self.sudo().search([('source_model', '=', source._name), ('source_id', '=', source.id),
                                   ('state', '=', 'posted'), ('reversed_by_id', '=', False),
                                   ('reversal_of_id', '=', False)])


class LfoodMoveLine(models.Model):
    _name = 'lfood.move.line'
    _description = 'Dòng định khoản'
    _order = 'date desc, move_id desc, id'

    move_id = fields.Many2one('lfood.move', 'Bút toán', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='move_id.company_id', store=True, index=True)
    date = fields.Date(related='move_id.date', store=True, index=True)
    journal = fields.Selection(related='move_id.journal', store=True)
    state = fields.Selection(related='move_id.state', store=True, index=True)
    ref = fields.Char(related='move_id.ref', store=True)
    account_id = fields.Many2one('lfood.account', 'Tài khoản', required=True, index=True,
                                 domain=[('allow_posting', '=', True)])
    account_code = fields.Char(related='account_id.code', store=True, index=True)
    partner_id = fields.Many2one('res.partner', 'Đối tượng', index=True)
    name = fields.Char('Diễn giải')
    debit = fields.Float('Nợ', digits=(16, 0), default=0.0)
    credit = fields.Float('Có', digits=(16, 0), default=0.0)
    balance = fields.Float('Nợ trừ Có', digits=(16, 0), compute='_compute_balance', store=True)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP', index=True)

    @api.depends('debit', 'credit')
    def _compute_balance(self):
        for rec in self:
            rec.balance = (rec.debit or 0) - (rec.credit or 0)

    @api.constrains('debit', 'credit')
    def _check_amounts(self):
        for rec in self:
            if rec.debit < 0 or rec.credit < 0 or (rec.debit and rec.credit):
                raise ValidationError(_('Mỗi dòng chỉ ghi Nợ hoặc Có, số không âm.'))

    def write(self, vals):
        if not self.env.context.get('lfood_ledger_system') and self.filtered(lambda l: l.move_id.state == 'posted'):
            raise UserError(_('Bút toán đã ghi sổ không sửa được.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda l: l.move_id.state == 'posted'):
            raise UserError(_('Bút toán đã ghi sổ không xóa được.'))
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get('lfood_ledger_system') and lines.filtered(lambda l: l.move_id.state == 'posted'):
            raise UserError(_('Bút toán đã ghi sổ không thêm dòng được.'))
        return lines


class ResCompany(models.Model):
    _inherit = 'res.company'

    lfood_lock_date = fields.Date('Khóa sổ đến ngày', help='Không ghi, đảo bút toán có ngày từ ngày này trở về trước')
