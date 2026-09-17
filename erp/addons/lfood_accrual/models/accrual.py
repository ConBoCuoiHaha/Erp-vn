"""Chi phí chờ phân bổ (TK 242) và chi phí phải trả, trích trước (TK 335) theo Thông tư 99/2025/TT-BTC.

Chi phí trả trước: khoản đã chi nhưng liên quan nhiều kỳ, ghi vào 242 rồi phân bổ dần vào chi phí
sản xuất kinh doanh từng kỳ. Chi phí phải trả: khoản chưa chi nhưng đã tính trước vào chi phí của kỳ,
ghi Có 335, khi phát sinh thực tế thì ghi giảm 335; chênh lệch giữa số trích trước và số thực tế
được ghi tăng chi phí hoặc hoàn nhập.

Lịch phân bổ dùng chung hàm build_schedule của phân hệ tài sản: kỳ đầu tính theo số ngày, kỳ cuối
nhận phần còn lại nên tổng phân bổ luôn bằng đúng số tiền gốc.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_asset.models.depr_tools import build_schedule
from odoo.addons.lfood_voucher.models.tools import vnd

EXPENSE_ACCOUNTS = [('6271', '6271 Chi phí nhân viên phân xưởng'), ('6277', '6277 Chi phí dịch vụ mua ngoài (sản xuất)'),
                    ('6417', '6417 Chi phí dịch vụ mua ngoài (bán hàng)'), ('6418', '6418 Chi phí bằng tiền khác (bán hàng)'),
                    ('6427', '6427 Chi phí dịch vụ mua ngoài (quản lý)'), ('6428', '6428 Chi phí bằng tiền khác (quản lý)'),
                    ('635', '635 Chi phí tài chính')]
# Thông tư 99 không chia 111, 112 thành tài khoản cấp 2
COUNTERPARTS = [('3311', '3311 Phải trả người bán'), ('111', '111 Tiền mặt'), ('112', '112 Tiền gửi không kỳ hạn')]
STATES = [('draft', 'Nháp'), ('running', 'Đang phân bổ'), ('done', 'Đã xong'), ('cancel', 'Đã hủy')]


class LfoodPrepaid(models.Model):
    _name = 'lfood.prepaid'
    _description = 'Chi phí trả trước chờ phân bổ'
    _order = 'date desc, id desc'

    name = fields.Char('Số chứng từ', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    label = fields.Char('Nội dung', required=True)
    partner_id = fields.Many2one('res.partner', 'Đối tượng')
    date = fields.Date('Ngày phát sinh', required=True, default=fields.Date.context_today, index=True)
    amount = fields.Float('Số tiền chờ phân bổ', digits=(16, 0), required=True)
    months = fields.Integer('Số kỳ phân bổ (tháng)', required=True, default=12)
    date_start = fields.Date('Bắt đầu phân bổ', required=True, default=fields.Date.context_today)
    expense_account = fields.Selection(EXPENSE_ACCOUNTS, 'TK chi phí', required=True, default='6428')
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP')
    post_initial = fields.Boolean('Ghi nhận ban đầu Nợ 242', default=False,
                                  help='Bật nếu khoản này chưa được ghi 242 bằng chứng từ mua dịch vụ hay phiếu chi')
    counterpart_account = fields.Selection(COUNTERPARTS, 'TK đối ứng khi ghi nhận ban đầu', default='3311')
    line_ids = fields.One2many('lfood.prepaid.line', 'prepaid_id', 'Lịch phân bổ', readonly=True)
    allocated = fields.Float('Đã phân bổ', digits=(16, 0), compute='_compute_progress', store=True)
    remaining = fields.Float('Còn lại', digits=(16, 0), compute='_compute_progress', store=True)
    state = fields.Selection(STATES, 'Trạng thái', default='draft', required=True, readonly=True, copy=False, index=True)

    @api.depends('line_ids.amount', 'line_ids.state', 'amount')
    def _compute_progress(self):
        for rec in self:
            rec.allocated = sum(rec.line_ids.filtered(lambda l: l.state == 'posted').mapped('amount'))
            rec.remaining = rec.amount - rec.allocated

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.prepaid') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_accrual_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái chỉ đổi bằng các nút trên màn hình.'))
            if self.filtered(lambda r: r.state != 'draft'):
                raise UserError(_('Chứng từ đã lập lịch phân bổ không sửa được. Hủy rồi lập chứng từ mới.'))
        return super().write(vals)

    def action_confirm(self):
        """Lập lịch phân bổ và ghi nhận ban đầu nếu được chọn."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ lập lịch cho chứng từ đang ở trạng thái Nháp.'))
            if rec.amount <= 0 or rec.months <= 0:
                raise UserError(_('Số tiền và số kỳ phân bổ phải lớn hơn 0.'))
            rec.line_ids.sudo().unlink()
            for period, amount in build_schedule(rec.amount, rec.months, rec.date_start):
                self.env['lfood.prepaid.line'].sudo().create({
                    'prepaid_id': rec.id, 'date': period, 'amount': amount})
            if rec.post_initial:
                label = _('%s %s') % (rec.name, rec.label)
                self.env['lfood.move']._create_from_source(
                    rec, 'general', rec.date,
                    [('242', rec.amount, 0, None, label, rec.cost_item_id),
                     (rec.counterpart_account, 0, rec.amount, rec.partner_id, label, None)],
                    memo=label, ref=rec.name, key='initial')
            rec.with_context(lfood_accrual_system=True).write({'state': 'running'})
        return True

    def action_cancel(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được hủy chứng từ đã lập lịch.'))
        for rec in self.filtered(lambda r: r.state in ('running', 'done')):
            if rec.line_ids.filtered(lambda l: l.state == 'posted'):
                raise UserError(_('Đã phân bổ %s nên không hủy được. Hoàn nhập bằng bút toán đảo trước.')
                                % vnd(rec.allocated))
            move = self.env['lfood.move']._active_for(rec)
            if move:
                move._reverse(memo=_('Hủy %s') % rec.name)
            rec.with_context(lfood_accrual_system=True).write({'state': 'cancel'})
        return True


class LfoodPrepaidLine(models.Model):
    _name = 'lfood.prepaid.line'
    _description = 'Kỳ phân bổ chi phí trả trước'
    _order = 'date, id'

    prepaid_id = fields.Many2one('lfood.prepaid', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='prepaid_id.company_id', store=True, index=True)
    date = fields.Date('Kỳ phân bổ', required=True, index=True)
    amount = fields.Float('Số phân bổ', digits=(16, 0), required=True)
    state = fields.Selection([('planned', 'Dự kiến'), ('posted', 'Đã ghi sổ')], 'Trạng thái',
                             default='planned', required=True, index=True)

    def _post(self):
        """Nợ TK chi phí / Có 242 cho từng kỳ."""
        Move = self.env['lfood.move']
        for line in self.filtered(lambda l: l.state == 'planned'):
            prepaid = line.prepaid_id
            label = _('Phân bổ %s kỳ %s') % (prepaid.label, line.date.strftime('%m/%Y'))
            Move._create_from_source(
                line, 'general', line.date,
                [(prepaid.expense_account, line.amount, 0, None, label, prepaid.cost_item_id),
                 ('242', 0, line.amount, None, label, None)],
                memo=label, ref=prepaid.name)
            line.sudo().write({'state': 'posted'})
            if not prepaid.line_ids.filtered(lambda l: l.state == 'planned'):
                prepaid.with_context(lfood_accrual_system=True).write({'state': 'done'})
        return True


class LfoodAccrued(models.Model):
    _name = 'lfood.accrued'
    _description = 'Chi phí phải trả, trích trước'
    _order = 'date desc, id desc'

    name = fields.Char('Số chứng từ', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    label = fields.Char('Nội dung', required=True)
    partner_id = fields.Many2one('res.partner', 'Đối tượng')
    date = fields.Date('Ngày lập', required=True, default=fields.Date.context_today, index=True)
    amount = fields.Float('Tổng số trích trước', digits=(16, 0), required=True)
    months = fields.Integer('Số kỳ trích trước (tháng)', required=True, default=12)
    date_start = fields.Date('Bắt đầu trích', required=True, default=fields.Date.context_today)
    expense_account = fields.Selection(EXPENSE_ACCOUNTS, 'TK chi phí', required=True, default='6428')
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP')
    line_ids = fields.One2many('lfood.accrued.line', 'accrued_id', 'Lịch trích trước', readonly=True)
    accrued_amount = fields.Float('Đã trích', digits=(16, 0), compute='_compute_progress', store=True)
    actual_amount = fields.Float('Số thực tế phát sinh', digits=(16, 0), readonly=True, copy=False)
    difference = fields.Float('Chênh lệch thực tế trừ đã trích', digits=(16, 0), compute='_compute_progress', store=True)
    state = fields.Selection(STATES + [('settled', 'Đã quyết toán')], 'Trạng thái', default='draft', required=True,
                             readonly=True, copy=False, index=True)

    @api.depends('line_ids.amount', 'line_ids.state', 'actual_amount')
    def _compute_progress(self):
        for rec in self:
            rec.accrued_amount = sum(rec.line_ids.filtered(lambda l: l.state == 'posted').mapped('amount'))
            rec.difference = rec.actual_amount - rec.accrued_amount if rec.actual_amount else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.accrued') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_accrual_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái chỉ đổi bằng các nút trên màn hình.'))
            if self.filtered(lambda r: r.state != 'draft'):
                raise UserError(_('Chứng từ đã lập lịch trích trước không sửa được.'))
        return super().write(vals)

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ lập lịch cho chứng từ đang ở trạng thái Nháp.'))
            if rec.amount <= 0 or rec.months <= 0:
                raise UserError(_('Số tiền và số kỳ trích trước phải lớn hơn 0.'))
            rec.line_ids.sudo().unlink()
            for period, amount in build_schedule(rec.amount, rec.months, rec.date_start):
                self.env['lfood.accrued.line'].sudo().create({'accrued_id': rec.id, 'date': period, 'amount': amount})
            rec.with_context(lfood_accrual_system=True).write({'state': 'running'})
        return True

    def action_settle(self):
        """Quyết toán khoản trích trước theo số thực tế; chênh lệch ghi tăng chi phí hoặc hoàn nhập."""
        self.ensure_one()
        if self.state not in ('running', 'done'):
            raise UserError(_('Chỉ quyết toán khoản trích trước đang theo dõi.'))
        if not self.actual_amount:
            raise UserError(_('Nhập số thực tế phát sinh trước khi quyết toán.'))
        diff = self.actual_amount - self.accrued_amount
        label = _('Quyết toán trích trước %s') % self.label
        if diff > 0:
            lines = [(self.expense_account, diff, 0, None, label, self.cost_item_id),
                     ('335', 0, diff, self.partner_id, label, None)]
        elif diff < 0:
            lines = [('335', -diff, 0, self.partner_id, label, None),
                     (self.expense_account, 0, -diff, None, label, self.cost_item_id)]
        else:
            lines = []
        if lines:
            self.env['lfood.move']._create_from_source(self, 'general', fields.Date.context_today(self), lines,
                                                       memo=label, ref=self.name, key='settle')
        self.with_context(lfood_accrual_system=True).write({'state': 'settled'})
        self.env['lfood.audit.log']._record_event(
            'state', model=self._name, res_id=self.id, res_name=self.name, company_id=self.company_id.id,
            summary=_('Quyết toán %s: đã trích %s, thực tế %s, chênh lệch %s')
                    % (self.name, vnd(self.accrued_amount), vnd(self.actual_amount), vnd(diff)))
        return True

    def action_cancel(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được hủy chứng từ đã lập lịch.'))
        for rec in self.filtered(lambda r: r.state in ('running', 'done')):
            if rec.line_ids.filtered(lambda l: l.state == 'posted'):
                raise UserError(_('Đã trích %s nên không hủy được. Dùng Quyết toán để hoàn nhập phần chênh lệch.')
                                % vnd(rec.accrued_amount))
            rec.with_context(lfood_accrual_system=True).write({'state': 'cancel'})
        return True


class LfoodAccruedLine(models.Model):
    _name = 'lfood.accrued.line'
    _description = 'Kỳ trích trước chi phí'
    _order = 'date, id'

    accrued_id = fields.Many2one('lfood.accrued', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='accrued_id.company_id', store=True, index=True)
    date = fields.Date('Kỳ trích', required=True, index=True)
    amount = fields.Float('Số trích', digits=(16, 0), required=True)
    state = fields.Selection([('planned', 'Dự kiến'), ('posted', 'Đã ghi sổ')], 'Trạng thái',
                             default='planned', required=True, index=True)

    def _post(self):
        """Nợ TK chi phí / Có 335 cho từng kỳ."""
        Move = self.env['lfood.move']
        for line in self.filtered(lambda l: l.state == 'planned'):
            accrued = line.accrued_id
            label = _('Trích trước %s kỳ %s') % (accrued.label, line.date.strftime('%m/%Y'))
            Move._create_from_source(
                line, 'general', line.date,
                [(accrued.expense_account, line.amount, 0, None, label, accrued.cost_item_id),
                 ('335', 0, line.amount, accrued.partner_id, label, None)],
                memo=label, ref=accrued.name)
            line.sudo().write({'state': 'posted'})
            if not accrued.line_ids.filtered(lambda l: l.state == 'planned'):
                accrued.with_context(lfood_accrual_system=True).write({'state': 'done'})
        return True


class LfoodAccrualRun(models.TransientModel):
    """Chạy phân bổ và trích trước cho các kỳ đã đến hạn, làm cùng lúc khi khóa sổ tháng."""
    _name = 'lfood.accrual.run'
    _description = 'Ghi phân bổ, trích trước theo kỳ'

    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company)
    date_to = fields.Date('Ghi các kỳ đến ngày', required=True, default=fields.Date.context_today)
    prepaid_count = fields.Integer('Số kỳ phân bổ 242 sẽ ghi', compute='_compute_counts')
    accrued_count = fields.Integer('Số kỳ trích trước 335 sẽ ghi', compute='_compute_counts')
    prepaid_amount = fields.Float('Tổng phân bổ 242', digits=(16, 0), compute='_compute_counts')
    accrued_amount = fields.Float('Tổng trích trước 335', digits=(16, 0), compute='_compute_counts')

    def _due(self):
        domain = [('state', '=', 'planned'), ('date', '<=', self.date_to), ('company_id', '=', self.company_id.id)]
        return (self.env['lfood.prepaid.line'].search(domain + [('prepaid_id.state', '=', 'running')]),
                self.env['lfood.accrued.line'].search(domain + [('accrued_id.state', '=', 'running')]))

    @api.depends('date_to', 'company_id')
    def _compute_counts(self):
        for rec in self:
            prepaid, accrued = rec._due()
            rec.prepaid_count, rec.accrued_count = len(prepaid), len(accrued)
            rec.prepaid_amount = sum(prepaid.mapped('amount'))
            rec.accrued_amount = sum(accrued.mapped('amount'))

    def action_run(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán mới ghi sổ phân bổ, trích trước.'))
        prepaid, accrued = self._due()
        if not prepaid and not accrued:
            raise UserError(_('Không có kỳ nào đến hạn tính tới ngày %s.') % self.date_to.strftime('%d/%m/%Y'))
        prepaid._post()
        accrued._post()
        self.env['lfood.audit.log']._record_event(
            'state', model=self._name, res_id=self.id, res_name=_('Phân bổ, trích trước'),
            company_id=self.company_id.id,
            summary=_('Ghi %s kỳ phân bổ 242 (%s) và %s kỳ trích trước 335 (%s) đến ngày %s')
                    % (len(prepaid), vnd(sum(prepaid.mapped('amount'))), len(accrued),
                       vnd(sum(accrued.mapped('amount'))), self.date_to.strftime('%d/%m/%Y')))
        return {'type': 'ir.actions.act_window_close'}
