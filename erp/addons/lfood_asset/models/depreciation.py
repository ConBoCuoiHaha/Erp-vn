from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd
from .asset import USAGES
from .depr_tools import month_end


class LfoodAssetDepreciation(models.Model):
    _name = 'lfood.asset.depreciation'
    _description = 'Chứng từ khấu hao TSCĐ'
    _order = 'date desc, id desc'

    name = fields.Char('Số chứng từ', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    date = fields.Date('Kỳ khấu hao (cuối tháng)', required=True, index=True,
                       default=lambda s: month_end(fields.Date.context_today(s)))
    memo = fields.Char('Diễn giải', compute='_compute_memo', store=True, readonly=False)
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             default='draft', readonly=True, copy=False, index=True)
    line_ids = fields.One2many('lfood.asset.depreciation.line', 'depreciation_id', 'Chi tiết', readonly=True)
    amount_total = fields.Float('Tổng khấu hao', digits=(16, 0), compute='_compute_total', store=True)
    posted_by = fields.Many2one('res.users', 'Người ghi sổ', readonly=True, copy=False)
    posted_on = fields.Datetime('Thời điểm ghi sổ', readonly=True, copy=False)

    @api.depends('date')
    def _compute_memo(self):
        for rec in self:
            rec.memo = _('Khấu hao TSCĐ tháng %s') % rec.date.strftime('%m/%Y') if rec.date else False

    @api.depends('line_ids.amount')
    def _compute_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('date'):
                vals['date'] = month_end(fields.Date.to_date(vals['date']))
        return super().create(vals_list)

    def write(self, vals):
        if {'state', 'name', 'posted_by', 'posted_on'} & set(vals) and not self.env.context.get('lfood_depr_system'):
            raise UserError(_('Trạng thái chứng từ khấu hao chỉ đổi bằng nút Ghi sổ, Hủy.'))
        if 'date' in vals:
            if self.filtered(lambda r: r.state != 'draft' or r.line_ids):
                raise UserError(_('Đổi kỳ khấu hao thì phải xóa các dòng đã lấy trước.'))
            vals['date'] = month_end(fields.Date.to_date(vals['date']))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda r: r.state == 'posted'):
            raise UserError(_('Chứng từ khấu hao đã ghi sổ không xóa được, hãy Hủy.'))
        return super().unlink()

    def _log(self, summary):
        for rec in self:
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=rec.name,
                                                      company_id=rec.company_id.id, summary=summary)

    def _require(self, group, msg):
        if not self.env.user.has_group(group):
            raise UserError(msg)

    # ------------------------------------------------------------ nghiệp vụ
    def action_compute(self):
        """Lấy số khấu hao kỳ này từ lịch của mọi tài sản đang khấu hao (và tài sản thanh lý trong kỳ)."""
        self._require('lfood_base.group_accountant', _('Chỉ kế toán được tính khấu hao.'))
        Schedule = self.env['lfood.asset.schedule'].sudo()
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ tính lại được chứng từ Nháp.'))
            rec.line_ids.unlink()
            # kỳ trước chưa ghi sổ thì không cho nhảy kỳ
            missing = Schedule.search([('company_id', '=', rec.company_id.id), ('date', '<', rec.date),
                                       ('posted', '=', False),
                                       ('asset_id.state', 'in', ('running', 'closed', 'disposed'))], limit=1)
            if missing:
                raise UserError(_('Tài sản %s còn kỳ %s chưa khấu hao. Làm chứng từ khấu hao kỳ đó trước.')
                                % (missing.asset_id.code, missing.date.strftime('%m/%Y')))
            rows = Schedule.search([('company_id', '=', rec.company_id.id), ('date', '=', rec.date),
                                    ('depreciation_line_id', '=', False),
                                    ('asset_id.state', 'in', ('running', 'closed', 'disposed'))])
            if not rows:
                raise UserError(_('Kỳ %s không có tài sản nào cần khấu hao, hoặc đã có chứng từ khấu hao khác.')
                                % rec.date.strftime('%m/%Y'))
            for row in rows:
                line = self.env['lfood.asset.depreciation.line'].create({
                    'depreciation_id': rec.id, 'asset_id': row.asset_id.id, 'amount': row.amount,
                    'account_expense': row.asset_id.account_expense, 'account_depreciation': row.asset_id.account_depreciation,
                    'usage': row.asset_id.usage, 'cost_item_id': row.asset_id.cost_item_id.id,
                })
                row.depreciation_line_id = line
        return True

    def action_post(self):
        self._require('lfood_base.group_accountant', _('Chỉ kế toán được ghi sổ khấu hao.'))
        for rec in self:
            if rec.state != 'draft' or not rec.line_ids:
                raise UserError(_('Bấm Tính khấu hao trước khi ghi sổ.'))
            name = rec.name if rec.name != '/' else (
                self.env['ir.sequence'].with_company(rec.company_id).next_by_code('lfood.asset.depreciation') or '/')
            rec.with_context(lfood_depr_system=True).write({
                'name': name, 'state': 'posted', 'posted_by': self.env.user.id, 'posted_on': fields.Datetime.now()})
            for asset in rec.line_ids.asset_id.filtered(lambda a: a.state == 'running'):
                if not asset.schedule_ids.filtered(lambda s: not s.posted):
                    asset.with_context(lfood_asset_system=True).state = 'closed'
            by_acc = {}
            for line in rec.line_ids:
                by_acc[line.account_expense] = by_acc.get(line.account_expense, 0) + line.amount
            rec._log(_('Ghi sổ khấu hao %s, %s tài sản, tổng %s: %s / Có 214')
                     % (rec.date.strftime('%m/%Y'), len(rec.line_ids), vnd(rec.amount_total),
                        ', '.join('Nợ %s %s' % (k, vnd(v)) for k, v in sorted(by_acc.items()))))
        return True

    def action_cancel(self):
        self._require('lfood_base.group_chief_accountant', _('Chỉ Kế toán trưởng được hủy chứng từ khấu hao.'))
        Schedule = self.env['lfood.asset.schedule'].sudo()
        for rec in self:
            if rec.state == 'cancel':
                continue
            later = Schedule.search([('asset_id', 'in', rec.line_ids.asset_id.ids), ('date', '>', rec.date),
                                     ('posted', '=', True)], limit=1)
            if later:
                raise UserError(_('Tài sản %s đã có chứng từ khấu hao kỳ %s. Hủy từ kỳ mới nhất trở về.')
                                % (later.asset_id.code, later.date.strftime('%m/%Y')))
            Schedule.search([('depreciation_line_id', 'in', rec.line_ids.ids)]).write({'depreciation_line_id': False})
            rec.line_ids.asset_id.filtered(lambda a: a.state == 'closed').with_context(lfood_asset_system=True).write({'state': 'running'})
            was_posted = rec.state == 'posted'
            rec.with_context(lfood_depr_system=True).state = 'cancel'
            if was_posted:
                rec._log(_('Hủy chứng từ khấu hao %s, tổng %s') % (rec.date.strftime('%m/%Y'), vnd(rec.amount_total)))
        return True

    def action_view_audit(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Nhật ký chứng từ khấu hao'), 'res_model': 'lfood.audit.log',
                'view_mode': 'list,form', 'domain': [('model', '=', self._name), ('res_id', '=', self.id)]}


class LfoodAssetDepreciationLine(models.Model):
    _name = 'lfood.asset.depreciation.line'
    _description = 'Dòng chứng từ khấu hao'
    _order = 'depreciation_id, account_expense, id'

    depreciation_id = fields.Many2one('lfood.asset.depreciation', 'Chứng từ', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='depreciation_id.company_id', store=True)
    date = fields.Date(related='depreciation_id.date', store=True)
    state = fields.Selection(related='depreciation_id.state', store=True)
    asset_id = fields.Many2one('lfood.asset', 'Tài sản', required=True, index=True)
    asset_code = fields.Char(related='asset_id.code', string='Mã tài sản')
    usage = fields.Selection(USAGES, 'Bộ phận sử dụng')
    account_expense = fields.Char('TK Nợ')
    account_depreciation = fields.Char('TK Có')
    amount = fields.Float('Số tiền khấu hao', digits=(16, 0))
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP', index=True)
