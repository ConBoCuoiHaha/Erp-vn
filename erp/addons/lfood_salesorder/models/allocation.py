"""Phân bổ chi phí chung cho nhãn hàng, kênh, bộ phận (NS05).

Chi phí chung đã ghi vào một khoản mục (ví dụ "Chi phí quản lý chung") trong kỳ được chia sang các khoản mục đích theo
tiêu thức: tỷ lệ nhập tay (diện tích, số người...) hoặc doanh thu thuần theo nhãn hàng, kênh lấy từ báo cáo lãi gộp.
Bút toán kết chuyển giữ nguyên tài khoản chi phí, chỉ đổi khoản mục: Nợ TK chi phí (khoản mục đích) / Có TK chi phí
(khoản mục nguồn); tổng chia đúng tới đồng. Dùng cho báo cáo quản trị theo cây khoản mục.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import allocate, vnd

BASES = [('manual', 'Tỷ lệ nhập tay'), ('revenue_brand', 'Doanh thu thuần theo nhãn hàng'),
         ('revenue_channel', 'Doanh thu thuần theo kênh')]


class LfoodCostAllocation(models.Model):
    _name = 'lfood.cost.allocation'
    _description = 'Phân bổ chi phí chung'
    _order = 'date_to desc, id desc'

    name = fields.Char('Nội dung', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    date_from = fields.Date('Từ ngày', required=True)
    date_to = fields.Date('Đến ngày', required=True)
    account_prefix = fields.Char('Tài khoản chi phí (đầu số)', required=True, default='642',
                                 help='Ví dụ 642 lấy mọi tài khoản 642x')
    source_cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục chi phí chung', required=True)
    basis = fields.Selection(BASES, 'Tiêu thức', required=True, default='manual')
    line_ids = fields.One2many('lfood.cost.allocation.line', 'allocation_id', 'Khoản mục nhận', copy=True)
    amount = fields.Float('Chi phí chung trong kỳ', digits=(16, 0), readonly=True)
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ')], 'Trạng thái', default='draft', required=True,
                             readonly=True, copy=False)

    def _source_balances(self):
        """{mã TK: số dư Nợ} của khoản mục nguồn trong kỳ, không tính các bút toán phân bổ."""
        self.ensure_one()
        self.env['lfood.move.line'].flush_model()
        lines = self.env['lfood.move.line'].sudo().search([
            ('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
            ('account_code', '=like', self.account_prefix + '%'), ('cost_item_id', '=', self.source_cost_item_id.id),
            ('date', '>=', self.date_from), ('date', '<=', self.date_to),
            ('move_id.source_model', '!=', self._name)])
        out = {}
        for l in lines:
            out[l.account_code] = out.get(l.account_code, 0) + l.balance
        return {k: round(v) for k, v in out.items() if round(v)}

    def action_compute(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.line_ids:
                raise UserError(_('Nhập các khoản mục nhận phân bổ.'))
            if rec.basis != 'manual':
                report = self.env['lfood.margin.report'].create({
                    'company_id': rec.company_id.id, 'date_from': rec.date_from, 'date_to': rec.date_to,
                    'dimension': 'brand' if rec.basis == 'revenue_brand' else 'channel'})
                rows = report._rows()
                for l in rec.line_ids:
                    l.weight = max(0, rows.get(l.key or '', [0])[0])
            rec.amount = sum(rec._source_balances().values())
            for l, share in zip(rec.line_ids, allocate(rec.amount, rec.line_ids.mapped('weight'))):
                l.amount = share
        return True

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được ghi sổ phân bổ.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            rec.action_compute()
            if not rec.amount:
                raise UserError(_('Khoản mục %s không có chi phí trong kỳ.') % rec.source_cost_item_id.display_name)
            if not any(rec.line_ids.mapped('weight')):
                raise UserError(_('Tiêu thức phân bổ đều bằng 0.'))
            label = _('Phân bổ %s') % rec.name
            lines = []
            for code, bal in rec._source_balances().items():
                for l, share in zip(rec.line_ids, allocate(bal, rec.line_ids.mapped('weight'))):
                    lines += [(code, share, 0, None, label, l.cost_item_id),
                              (code, 0, share, None, label, rec.source_cost_item_id)]
            self.env['lfood.move']._create_from_source(rec, 'general', rec.date_to, lines, memo=label, ref=rec.name)
            rec.state = 'posted'
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Ghi sổ %s: %s cho %s khoản mục') % (label, vnd(rec.amount), len(rec.line_ids)))
        return True

    def action_reset(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được hủy phân bổ.'))
        for rec in self.filtered(lambda r: r.state == 'posted'):
            self.env['lfood.move']._active_for(rec)._reverse(memo=_('Hủy phân bổ %s') % rec.name)
            rec.state = 'draft'
        return True


class LfoodCostAllocationLine(models.Model):
    _name = 'lfood.cost.allocation.line'
    _description = 'Khoản mục nhận phân bổ'

    allocation_id = fields.Many2one('lfood.cost.allocation', required=True, ondelete='cascade', index=True)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục nhận', required=True)
    key = fields.Char('Nhãn hàng / kênh', help='Tên nhãn hàng hoặc kênh đúng như trên báo cáo lãi gộp')
    weight = fields.Float('Tiêu thức')
    amount = fields.Float('Số phân bổ', digits=(16, 0), readonly=True)
