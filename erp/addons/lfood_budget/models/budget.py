from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd
from .spread import spread, SpreadError

MONTHS = [(str(m), 'Tháng %d' % m) for m in range(1, 13)]
STATES = [('draft', 'Nháp'), ('approved', 'Đã duyệt'), ('locked', 'Đã khóa')]


class LfoodBudget(models.Model):
    _name = 'lfood.budget'
    _description = 'Ngân sách năm'
    _order = 'year desc, version desc'

    name = fields.Char('Tên ngân sách', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    year = fields.Integer('Năm', required=True, default=lambda s: fields.Date.context_today(s).year, index=True)
    version = fields.Integer('Phiên bản', required=True, default=1, readonly=True)
    state = fields.Selection(STATES, 'Trạng thái', default='draft', required=True, readonly=True, copy=False, index=True)
    line_ids = fields.One2many('lfood.budget.line', 'budget_id', 'Dòng ngân sách', copy=True)
    amount_total = fields.Float('Tổng kế hoạch', digits=(16, 0), compute='_compute_amount_total', store=True)
    approved_by = fields.Many2one('res.users', 'Người duyệt', readonly=True, copy=False)
    approved_on = fields.Datetime('Ngày duyệt', readonly=True, copy=False)
    note = fields.Text('Ghi chú')

    _year_version_uniq = models.Constraint('unique(company_id, year, version)',
                                           'Năm và phiên bản ngân sách này đã có.')

    @api.depends('line_ids.amount')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('amount'))

    @api.depends('name', 'year', 'version')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s %s (bản %s)' % (rec.name or '', rec.year, rec.version)

    def _check_editable(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Ngân sách %s đã duyệt, muốn sửa thì lập phiên bản mới.') % rec.display_name)

    def write(self, vals):
        if not self.env.context.get('lfood_budget_system') and set(vals) - {'note'}:
            self._check_editable()
        return super().write(vals)

    def action_load_items(self):
        """Tạo đủ dòng cho mọi khoản mục lá và 12 tháng, giữ nguyên số đã nhập."""
        self._check_editable()
        Line = self.env['lfood.budget.line']
        for rec in self:
            items = self.env['lfood.cost.item'].search([
                ('child_ids', '=', False), '|', ('company_id', '=', False), ('company_id', '=', rec.company_id.id)])
            have = {(l.cost_item_id.id, l.month) for l in rec.line_ids}
            vals = [{'budget_id': rec.id, 'cost_item_id': item.id, 'month': m, 'amount': 0.0}
                    for item in items for m, _label in MONTHS if (item.id, m) not in have]
            Line.create(vals)
        return True

    def action_approve(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng trở lên được duyệt ngân sách.'))
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ duyệt ngân sách đang ở trạng thái Nháp.'))
            rec.with_context(lfood_budget_system=True).write({
                'state': 'approved', 'approved_by': self.env.uid, 'approved_on': fields.Datetime.now()})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.display_name,
                summary=_('Duyệt ngân sách %s, tổng %s') % (rec.display_name, vnd(rec.amount_total)))
        return True

    def action_lock(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng trở lên được khóa ngân sách.'))
        for rec in self.filtered(lambda r: r.state == 'approved'):
            rec.with_context(lfood_budget_system=True).write({'state': 'locked'})
        return True

    def action_new_version(self):
        """Ngân sách đã duyệt không sửa được; muốn đổi thì lập phiên bản mới."""
        self.ensure_one()
        latest = self.search([('company_id', '=', self.company_id.id), ('year', '=', self.year)],
                             order='version desc', limit=1)
        new = self.copy({'version': latest.version + 1, 'state': 'draft', 'approved_by': False, 'approved_on': False})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': new.id, 'view_mode': 'form'}

    def set_amount(self, cost_item, month, amount):
        """Đặt số kế hoạch cho một khoản mục ở bất kỳ cấp nào.

        Khoản mục lá thì gán thẳng; khoản cha thì chia xuống các lá theo tỷ trọng
        hiện có, bỏ qua dòng đang khóa.
        """
        self.ensure_one()
        self._check_editable()
        leaves = self.line_ids.filtered(
            lambda l: l.month == str(month) and cost_item.id in l.cost_item_id._branch_ids())
        if not leaves:
            raise UserError(_('Chưa có dòng ngân sách nào của %s tháng %s. Bấm Nạp khoản mục trước.')
                            % (cost_item.display_name, month))
        try:
            new = spread(amount, leaves.mapped('amount'), leaves.mapped('locked'))
        except SpreadError as err:
            raise UserError(str(err))
        for line, value in zip(leaves, new):
            if line.amount != value:
                line.amount = value
        return True

    def amount_for(self, cost_item, month=None):
        """Số kế hoạch của một khoản mục: tổng các lá thuộc nhánh."""
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: cost_item.id in l.cost_item_id._branch_ids())
        if month:
            lines = lines.filtered(lambda l: l.month == str(month))
        return sum(lines.mapped('amount'))

    @api.model
    def check_over(self, cost_item, date):
        """So thực tế đã ghi sổ với ngân sách đang áp dụng của tháng đó.

        Trả về chuỗi cảnh báo nếu vượt, chuỗi rỗng nếu còn trong kế hoạch hoặc
        chưa lập ngân sách. Chỉ cảnh báo, không chặn chứng từ.
        """
        if not cost_item or not date:
            return ''
        budget = self.search([('company_id', '=', self.env.company.id), ('year', '=', date.year),
                              ('state', 'in', ('approved', 'locked'))], order='version desc', limit=1)
        plan = budget.amount_for(cost_item, date.month) if budget else 0.0
        if not plan:
            return ''
        actual = self.env['lfood.budget.report'].sudo().actual_for(cost_item, date.year, date.month)
        if actual <= plan:
            return ''
        return _('Khoản mục %s tháng %s/%s: kế hoạch %s, thực tế %s, vượt %s.') % (
            cost_item.display_name, date.month, date.year, vnd(plan), vnd(actual), vnd(actual - plan))


class LfoodBudgetLine(models.Model):
    _name = 'lfood.budget.line'
    _description = 'Dòng ngân sách'
    _order = 'cost_item_id, month'

    budget_id = fields.Many2one('lfood.budget', 'Ngân sách', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='budget_id.company_id', store=True, index=True)
    year = fields.Integer(related='budget_id.year', store=True, index=True)
    state = fields.Selection(related='budget_id.state', store=True, index=True)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục chi phí', required=True, index=True,
                                   domain=[('child_ids', '=', False)])
    month = fields.Selection(MONTHS, 'Tháng', required=True, index=True)
    amount = fields.Float('Số kế hoạch', digits=(16, 0), default=0.0)
    locked = fields.Boolean('Khóa', help='Dòng khóa giữ nguyên khi khoản mục cha chia lại số')

    _item_month_uniq = models.Constraint('unique(budget_id, cost_item_id, month)',
                                         'Mỗi khoản mục chỉ có một dòng cho mỗi tháng.')

    @api.constrains('cost_item_id')
    def _check_leaf(self):
        for rec in self:
            if rec.cost_item_id.child_ids:
                raise UserError(_('Chỉ nhập kế hoạch ở khoản mục chi tiết, không nhập ở khoản mục cha %s.')
                                % rec.cost_item_id.display_name)

    def write(self, vals):
        if not self.env.context.get('lfood_budget_system'):
            self.mapped('budget_id')._check_editable()
        return super().write(vals)


class LfoodCostItem(models.Model):
    _inherit = 'lfood.cost.item'

    def _branch_ids(self):
        """Mã của chính khoản mục và mọi khoản mục cha, lấy từ parent_path."""
        self.ensure_one()
        return [int(x) for x in (self.parent_path or '').split('/') if x]


class LfoodBudgetSpreadWizard(models.TransientModel):
    _name = 'lfood.budget.spread'
    _description = 'Chia số kế hoạch xuống khoản mục con'

    budget_id = fields.Many2one('lfood.budget', 'Ngân sách', required=True,
                                default=lambda s: s.env.context.get('active_id'))
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục', required=True)
    month = fields.Selection(MONTHS, 'Tháng', required=True)
    amount = fields.Float('Số kế hoạch', digits=(16, 0), required=True)
    current_amount = fields.Float('Số hiện tại', digits=(16, 0), compute='_compute_current', readonly=True)

    @api.depends('budget_id', 'cost_item_id', 'month')
    def _compute_current(self):
        for rec in self:
            rec.current_amount = rec.budget_id.amount_for(rec.cost_item_id, rec.month) \
                if rec.budget_id and rec.cost_item_id and rec.month else 0.0

    def action_apply(self):
        self.ensure_one()
        self.budget_id.set_amount(self.cost_item_id, self.month, self.amount)
        return {'type': 'ir.actions.act_window_close'}
