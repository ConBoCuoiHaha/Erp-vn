from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .tools import allocate, vnd

# các trường đầu chứng từ được chụp lại theo từng phiên bản
HEADER_FIELDS = ['partner_id', 'accounting_date', 'document_date', 'memo', 'invoice_ref']
STATES = [
    ('draft', 'Nháp'),
    ('waiting', 'Chờ duyệt'),
    ('posted', 'Đã cất'),
    ('editing', 'Đang sửa'),
    ('cancel', 'Đã hủy'),
]


class LfoodServiceVoucher(models.Model):
    _name = 'lfood.service.voucher'
    _description = 'Chứng từ mua dịch vụ'
    _order = 'accounting_date desc, id desc'

    name = fields.Char('Số chứng từ', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    state = fields.Selection(STATES, 'Trạng thái', default='draft', required=True, readonly=True, copy=False, index=True)

    partner_id = fields.Many2one('res.partner', 'Nhà cung cấp', required=True, index=True)
    partner_vat = fields.Char('Mã số thuế', related='partner_id.vat')
    partner_address = fields.Char('Địa chỉ', related='partner_id.contact_address')
    buyer_id = fields.Many2one('res.users', 'Nhân viên mua hàng')
    accounting_date = fields.Date('Ngày hạch toán', required=True, default=fields.Date.context_today, index=True)
    document_date = fields.Date('Ngày chứng từ', default=fields.Date.context_today)
    memo = fields.Char('Diễn giải')
    invoice_ref = fields.Char('Tham chiếu (số hóa đơn)')
    payment_state = fields.Selection([('unpaid', 'Chưa thanh toán'), ('paid_now', 'Thanh toán ngay')],
                                     'Thanh toán', default='unpaid', required=True)
    payment_method = fields.Selection([('cash', 'Tiền mặt'), ('bank', 'Chuyển khoản')], 'Hình thức', default='bank')
    invoice_mode = fields.Selection([('with', 'Nhận kèm hóa đơn'), ('later', 'Nhận hóa đơn sau'), ('none', 'Không có hóa đơn')],
                                    'Hóa đơn', default='with')
    is_purchase_cost = fields.Boolean('Là chi phí mua hàng')
    credit_days = fields.Integer('Số ngày được nợ')
    due_date = fields.Date('Hạn thanh toán', compute='_compute_due_date', store=True, readonly=False)

    version_ids = fields.One2many('lfood.service.voucher.version', 'voucher_id', 'Các phiên bản', readonly=True)
    current_version_id = fields.Many2one('lfood.service.voucher.version', 'Phiên bản hiện hành', readonly=True, copy=False)
    report_version_id = fields.Many2one('lfood.service.voucher.version', 'Phiên bản báo cáo', readonly=True, copy=False,
                                        help='Phiên bản mà báo cáo và sổ sách đọc. Sửa chứng từ không đổi phiên bản này.')
    current_version_state = fields.Selection(related='current_version_id.state', string='Trạng thái phiên bản')
    version_count = fields.Integer('Số phiên bản', compute='_compute_counts')
    line_ids = fields.One2many('lfood.service.voucher.line', 'voucher_id', 'Hạch toán',
                               domain=[('is_current', '=', True)])

    amount_untaxed = fields.Float('Tổng tiền dịch vụ', digits=(16, 0), compute='_compute_amounts', store=True)
    amount_tax = fields.Float('Thuế GTGT', digits=(16, 0), compute='_compute_amounts', store=True)
    amount_total = fields.Float('Tổng tiền thanh toán', digits=(16, 0), compute='_compute_amounts', store=True)
    report_amount_total = fields.Float('Tổng theo báo cáo', digits=(16, 0), related='report_version_id.amount_total', store=True)
    report_differs = fields.Boolean('Khác số báo cáo', compute='_compute_report_differs', store=True)

    posted_by = fields.Many2one('res.users', 'Người cất', readonly=True, copy=False)
    posted_on = fields.Datetime('Thời điểm cất', readonly=True, copy=False)
    approved_by = fields.Many2one('res.users', 'Người duyệt', readonly=True, copy=False)
    approved_on = fields.Datetime('Thời điểm duyệt', readonly=True, copy=False)
    audit_count = fields.Integer('Nhật ký', compute='_compute_counts')
    cash_warning = fields.Char('Cảnh báo', compute='_compute_cash_warning')

    # ---------------------------------------------------------------- tính
    @api.depends('accounting_date', 'credit_days')
    def _compute_due_date(self):
        for rec in self:
            rec.due_date = rec.accounting_date + timedelta(days=rec.credit_days) if rec.accounting_date and rec.credit_days else rec.due_date

    @api.depends('current_version_id.amount_untaxed', 'current_version_id.amount_tax', 'current_version_id.amount_total')
    def _compute_amounts(self):
        for rec in self:
            v = rec.current_version_id
            rec.amount_untaxed, rec.amount_tax, rec.amount_total = v.amount_untaxed, v.amount_tax, v.amount_total

    @api.depends('current_version_id', 'report_version_id')
    def _compute_report_differs(self):
        for rec in self:
            rec.report_differs = bool(rec.report_version_id and rec.current_version_id != rec.report_version_id)

    def _compute_counts(self):
        Log = self.env['lfood.audit.log'].sudo()
        for rec in self:
            rec.version_count = len(rec.version_ids)
            rec.audit_count = Log.search_count(rec._audit_domain()) if rec.id else 0

    @api.depends('payment_method', 'amount_total', 'accounting_date')
    def _compute_cash_warning(self):
        Param = self.env['lfood.legal.param']
        for rec in self:
            rec.cash_warning = False
            if rec.payment_method == 'cash' and rec.amount_total and rec.accounting_date:
                limit = Param.get_value('NGUONG_TT_KHONG_TIEN_MAT', rec.accounting_date, default=0)
                if limit and rec.amount_total >= limit:
                    rec.cash_warning = _('Thanh toán tiền mặt từ %s đồng trở lên: không đủ điều kiện khấu trừ thuế GTGT '
                                         'và không được tính chi phí được trừ. Nên chuyển khoản.') % vnd(limit)

    def _audit_domain(self):
        self.ensure_one()
        return ['|', '|',
                '&', ('model', '=', self._name), ('res_id', '=', self.id),
                '&', ('model', '=', 'lfood.service.voucher.version'), ('res_id', 'in', self.version_ids.ids or [0]),
                '&', ('model', '=', 'lfood.service.voucher.line'),
                ('res_id', 'in', self.with_context(active_test=False).env['lfood.service.voucher.line'].search(
                    [('voucher_id', '=', self.id)]).ids or [0])]

    # ---------------------------------------------------------------- tạo, sửa
    @api.model_create_multi
    def create(self, vals_list):
        pending = []
        for vals in vals_list:
            pending.append(vals.pop('line_ids', None))
        vouchers = super().create(vals_list)
        Version = self.env['lfood.service.voucher.version']
        for voucher, lines in zip(vouchers, pending):
            version = Version.create({'voucher_id': voucher.id, 'number': 1, 'kind': 'original', 'state': 'draft'})
            voucher.with_context(lfood_voucher_system=True).current_version_id = version
            if lines:
                voucher.write({'line_ids': lines})
        return vouchers

    def write(self, vals):
        if not self.env.context.get('lfood_voucher_system'):
            locked_header = set(HEADER_FIELDS + ['payment_state', 'payment_method', 'invoice_mode', 'credit_days', 'company_id'])
            if locked_header & set(vals):
                for rec in self:
                    if rec.state in ('posted', 'waiting', 'cancel'):
                        raise UserError(_('Chứng từ %s đã cất. Bấm Sửa để tạo phiên bản mới rồi mới sửa được.') % rec.name)
            if 'line_ids' in vals:
                for rec in self:
                    if rec.state not in ('draft', 'editing'):
                        raise UserError(_('Chứng từ %s đã cất. Bấm Sửa để tạo phiên bản mới rồi mới sửa được.') % rec.name)
        return super().write(vals)

    def unlink(self):
        is_admin = self.env.user.has_group('lfood_base.group_sysadmin')
        for rec in self:
            if rec.state == 'cancel' and is_admin:
                continue
            if rec.state != 'draft':
                raise UserError(_('Chỉ xóa được chứng từ Nháp (Quản trị được xóa thêm chứng từ Đã hủy). '
                                  'Chứng từ %s đã cất, hãy dùng Hủy.') % rec.name)
        versions = self.mapped('version_ids')
        self.with_context(lfood_voucher_system=True).write({'current_version_id': False, 'report_version_id': False})
        versions.with_context(lfood_version_system=True).unlink()
        return super().unlink()

    # ---------------------------------------------------------------- tiện ích
    def _require(self, group, message):
        if not self.env.user.has_group(group):
            raise UserError(message)

    def _log_state(self, summary, changes=None):
        for rec in self:
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=rec.name,
                                                      company_id=rec.company_id.id, summary=summary, changes=changes)

    def _header_snapshot(self):
        self.ensure_one()
        return {
            'partner_id': self.partner_id.id, 'accounting_date': self.accounting_date,
            'document_date': self.document_date, 'memo': self.memo, 'invoice_ref': self.invoice_ref,
        }

    def _check_ready(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('Chứng từ chưa có dòng hạch toán.'))
            missing = rec.line_ids.filtered(lambda l: not l.cost_item_id)
            if missing:
                raise UserError(_('Dòng %s chưa chọn Khoản mục chi phí.') % ', '.join(missing.mapped('name')[:5]))

    # ---------------------------------------------------------------- Cất lần đầu
    def action_post(self):
        self._require('lfood_base.group_accountant', _('Bạn không có quyền Cất chứng từ.'))
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ Cất được chứng từ Nháp.'))
            rec._check_ready()
            vals = {'posted_by': self.env.uid, 'posted_on': fields.Datetime.now()}
            if rec.name in (False, '/'):
                vals['name'] = self.env['ir.sequence'].next_by_code('lfood.service.voucher') or '/'
            version = rec.current_version_id
            version.with_context(lfood_version_system=True).write(dict(
                rec._header_snapshot(), state='saved', saved_by=self.env.uid, saved_on=fields.Datetime.now()))
            over = rec.amount_total > rec.company_id.lfood_voucher_approval_limit > 0
            vals['state'] = 'waiting' if over else 'posted'
            if not over:
                vals['report_version_id'] = version.id
            rec.with_context(lfood_voucher_system=True).write(vals)
            if over:
                rec._log_state(_('Cất chứng từ %s, vượt hạn mức %s: chờ duyệt') % (rec.name, vnd(rec.company_id.lfood_voucher_approval_limit)))
            else:
                rec._log_state(_('Cất chứng từ %s, phiên bản 1 gốc lúc mua vào, tổng %s') % (rec.name, vnd(rec.amount_total)))
        return True

    def action_approve(self):
        if not (self.env.user.has_group('lfood_base.group_chief_accountant') or self.env.user.has_group('lfood_base.group_director')):
            raise UserError(_('Chỉ Kế toán trưởng hoặc Giám đốc được duyệt.'))
        for rec in self.filtered(lambda r: r.state == 'waiting'):
            rec.sudo().with_context(lfood_voucher_system=True).write({
                'state': 'posted', 'report_version_id': rec.current_version_id.id,
                'approved_by': self.env.uid, 'approved_on': fields.Datetime.now()})
            rec._log_state(_('Duyệt chứng từ %s, tổng %s') % (rec.name, vnd(rec.amount_total)))
        return True

    def action_reject(self):
        if not (self.env.user.has_group('lfood_base.group_chief_accountant') or self.env.user.has_group('lfood_base.group_director')):
            raise UserError(_('Chỉ Kế toán trưởng hoặc Giám đốc được trả lại chứng từ.'))
        for rec in self.filtered(lambda r: r.state == 'waiting'):
            rec.current_version_id.sudo().with_context(lfood_version_system=True).write({'state': 'draft'})
            rec.sudo().with_context(lfood_voucher_system=True).write({'state': 'draft'})
            rec._log_state(_('Trả lại chứng từ %s về Nháp') % rec.name)
        return True

    # ---------------------------------------------------------------- Sửa sau khi Cất
    def _new_version(self, kind, source=None, batch=None):
        self.ensure_one()
        source = source or self.current_version_id
        Version = self.env['lfood.service.voucher.version']
        number = max(self.version_ids.mapped('number') or [0]) + 1
        version = Version.create(dict(
            source._header_values(), voucher_id=self.id, number=number, kind=kind, state='draft',
            source_version_id=self.current_version_id.id, bulk_batch_id=batch.id if batch else False))
        for line in source.line_ids:
            line.with_context(lfood_version_system=True).copy({
                'version_id': version.id, 'voucher_id': self.id,
                'origin_line_id': (line.origin_line_id or line).id})
        return version

    def action_edit(self):
        self._require('lfood_base.group_chief_accountant', _('Chỉ Kế toán trưởng được Sửa chứng từ đã cất.'))
        for rec in self:
            if rec.state != 'posted':
                raise UserError(_('Chỉ Sửa được chứng từ đã cất.'))
            days = rec.company_id.lfood_edit_after_post_days
            if days and rec.posted_on and fields.Datetime.now() - rec.posted_on > timedelta(days=days):
                raise UserError(_('Đã quá %s ngày kể từ khi Cất, không Sửa được theo quy chế công ty.') % days)
            version = rec._new_version('edit')
            rec.with_context(lfood_voucher_system=True).write({'current_version_id': version.id, 'state': 'editing'})
            rec._log_state(_('Bấm Sửa chứng từ %s: tạo phiên bản %s') % (rec.name, version.number))
        return True

    def action_open_save_edit(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'lfood.voucher.reason', 'view_mode': 'form', 'target': 'new',
            'name': _('Lưu sửa đổi'), 'context': {'default_voucher_id': self.id, 'default_mode': 'save_edit'},
        }

    def _save_edit(self, reason):
        self.ensure_one()
        if self.state != 'editing':
            raise UserError(_('Chứng từ không ở chế độ Đang sửa.'))
        if not (reason or '').strip():
            raise UserError(_('Phải nhập lý do sửa.'))
        self._check_ready()
        version = self.current_version_id
        version.with_context(lfood_version_system=True).write(dict(
            self._header_snapshot(), state='saved', reason=reason, saved_by=self.env.uid, saved_on=fields.Datetime.now()))
        diffs = version._compute_diff()
        self.with_context(lfood_voucher_system=True).write({'state': 'posted'})
        self._log_state(_('Lưu sửa đổi chứng từ %s thành phiên bản %s. Lý do: %s. Báo cáo không đổi.') % (self.name, version.number, reason),
                        changes=[{'field': d['field'], 'label': d['label'], 'old': d['old'], 'new': d['new']} for d in diffs[:100]])
        return True

    def action_cancel_edit(self):
        for rec in self:
            if rec.state != 'editing':
                continue
            draft = rec.current_version_id
            source = draft.source_version_id
            rec.with_context(lfood_voucher_system=True).write(dict(
                source._header_values(), current_version_id=source.id, state='posted'))
            draft.with_context(lfood_version_system=True).unlink()
            rec._log_state(_('Hủy sửa chứng từ %s, giữ phiên bản %s') % (rec.name, source.number))
        return True

    def action_open_restore(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'lfood.voucher.reason', 'view_mode': 'form', 'target': 'new',
            'name': _('Khôi phục số liệu gốc lúc mua vào'), 'context': {'default_voucher_id': self.id, 'default_mode': 'restore'},
        }

    def _restore_original(self, reason):
        self.ensure_one()
        self._require('lfood_base.group_chief_accountant', _('Chỉ Kế toán trưởng được khôi phục số liệu.'))
        if self.state != 'posted':
            raise UserError(_('Chỉ khôi phục được chứng từ đã cất.'))
        original = self.version_ids.filtered(lambda v: v.kind == 'original')[:1]
        version = self._new_version('restore', source=original)
        self.with_context(lfood_voucher_system=True).write(dict(original._header_values(), current_version_id=version.id, state='editing'))
        return self._save_edit(reason or _('Khôi phục số liệu gốc lúc mua vào'))

    def action_apply_to_report(self):
        self._require('lfood_base.group_chief_accountant', _('Chỉ Kế toán trưởng được đưa sửa đổi vào báo cáo.'))
        for rec in self:
            if rec.state != 'posted' or not rec.report_differs:
                continue
            old = rec.report_version_id
            rec.with_context(lfood_voucher_system=True).write({'report_version_id': rec.current_version_id.id})
            rec._log_state(_('Đưa phiên bản %s của chứng từ %s vào báo cáo (thay phiên bản %s)') % (rec.current_version_id.number, rec.name, old.number),
                           changes=[{'field': 'report_amount_total', 'label': 'Tổng theo báo cáo', 'old': old.amount_total, 'new': rec.current_version_id.amount_total}])
        return True

    def action_cancel(self):
        self._require('lfood_base.group_chief_accountant', _('Chỉ Kế toán trưởng được Hủy chứng từ.'))
        for rec in self:
            if rec.state == 'editing':
                rec.action_cancel_edit()
            rec.with_context(lfood_voucher_system=True).write({'state': 'cancel'})
            rec._log_state(_('Hủy chứng từ %s') % rec.name)
        return True

    # ---------------------------------------------------------------- tự động tính
    def action_open_apply_total(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'lfood.voucher.reason', 'view_mode': 'form', 'target': 'new',
            'name': _('Sửa tổng tiền dịch vụ'),
            'context': {'default_voucher_id': self.id, 'default_mode': 'total', 'default_new_total': self.amount_untaxed},
        }

    def _apply_total(self, new_total):
        self.ensure_one()
        if self.state not in ('draft', 'editing'):
            raise UserError(_('Chỉ sửa tổng khi chứng từ Nháp hoặc Đang sửa.'))
        lines = self.line_ids
        free = lines.filtered(lambda l: not l.locked)
        if not free:
            raise UserError(_('Tất cả các dòng đang khóa, không phân bổ được.'))
        locked_sum = sum(lines.filtered('locked').mapped('amount'))
        rest = round(new_total) - locked_sum
        if rest < 0:
            raise UserError(_('Tổng mới nhỏ hơn tổng các dòng đang khóa (%s).') % vnd(locked_sum))
        old_total = self.amount_untaxed
        for line, part in zip(free, allocate(rest, free.mapped('amount'))):
            line.write({'amount': part})
        self._log_state(_('Phân bổ lại tổng tiền dịch vụ %s: %s → %s cho %s dòng') % (self.name, vnd(old_total), vnd(new_total), len(free)))
        return True

    def action_view_versions(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Phiên bản'), 'res_model': 'lfood.service.voucher.version',
                'view_mode': 'list,form', 'domain': [('voucher_id', '=', self.id)]}

    def action_view_audit(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Nhật ký chứng từ %s') % self.name,
                'res_model': 'lfood.audit.log', 'view_mode': 'list,form', 'domain': self._audit_domain()}
