"""Tính giá thành giản đơn (trực tiếp) cho doanh nghiệp sản xuất.

Luồng: xuất nguyên vật liệu cho sản xuất (621) và tiền lương công nhân trực tiếp (622) được gắn thẳng vào từng
sản phẩm; chi phí sản xuất chung (627) tập hợp chung rồi phân bổ theo tiêu thức chọn ở kỳ tính giá thành.
Cuối kỳ: đánh giá sản phẩm dở dang theo sản lượng hoàn thành tương đương, kết chuyển 621, 622, 627 sang 154,
tính giá thành đơn vị và nhập kho thành phẩm (Nợ 155 / Có 154).
"""
import calendar
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.lfood_voucher.models.tools import vnd
from . import calc

BASIS = [('622', 'Tiền lương công nhân trực tiếp'), ('621', 'Chi phí nguyên vật liệu trực tiếp'),
         ('qty', 'Sản lượng hoàn thành')]


class MoveLine(models.Model):
    _inherit = 'lfood.move.line'

    cost_product_id = fields.Many2one('lfood.product', 'Đối tượng tính giá thành', index=True, ondelete='restrict',
                                      help='Chi phí 621, 622, 627 gắn cho sản phẩm nào. Để trống ở 627 nghĩa là '
                                           'chi phí chung, sẽ phân bổ khi tính giá thành.')


class Employee(models.Model):
    _inherit = 'lfood.employee'

    cost_product_id = fields.Many2one('lfood.product', 'Sản phẩm trực tiếp làm ra', ondelete='restrict',
                                      domain="[('kind', '=', 'finished')]",
                                      help='Chỉ dành cho công nhân trực tiếp (TK chi phí lương 622).')


class PayrollRun(models.Model):
    _inherit = 'lfood.payroll.run'

    def _cost_extra(self, emp):
        if emp.cost_account == '622' and emp.cost_product_id:
            return {'cost_product_id': emp.cost_product_id.id}
        return super()._cost_extra(emp)


class Picking(models.Model):
    _inherit = 'lfood.stock.picking'

    purpose = fields.Selection(selection_add=[('production', 'Xuất cho sản xuất')],
                               ondelete={'production': 'set default'})
    cost_product_id = fields.Many2one('lfood.product', 'Đối tượng tính giá thành', ondelete='restrict',
                                      domain="[('kind', '=', 'finished')]")
    costing_run_id = fields.Many2one('lfood.costing.run', 'Kỳ tính giá thành', ondelete='set null', readonly=True)

    @api.depends('kind', 'purpose')
    def _compute_counterpart(self):
        super()._compute_counterpart()
        for rec in self:
            if rec.kind == 'out' and rec.purpose == 'production':
                rec.counterpart_account = '621'

    def _cost_extra(self):
        return {'cost_product_id': self.cost_product_id.id} if self.cost_product_id else super()._cost_extra()

    @api.constrains('purpose', 'cost_product_id')
    def _check_cost_product(self):
        for rec in self:
            if rec.purpose == 'production' and not rec.cost_product_id:
                raise ValidationError(_('Xuất cho sản xuất phải chọn đối tượng tính giá thành.'))


class CostingRun(models.Model):
    _name = 'lfood.costing.run'
    _description = 'Kỳ tính giá thành'
    _order = 'date_to desc, id desc'
    _rec_name = 'display_name'

    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    year = fields.Integer('Năm', required=True, default=lambda s: fields.Date.context_today(s).year)
    month = fields.Selection([(str(m), '%02d' % m) for m in range(1, 13)], 'Tháng', required=True,
                             default=lambda s: str(fields.Date.context_today(s).month))
    date_from = fields.Date('Từ ngày', compute='_compute_dates', store=True)
    date_to = fields.Date('Đến ngày', compute='_compute_dates', store=True)
    basis = fields.Selection(BASIS, 'Tiêu thức phân bổ chi phí sản xuất chung', required=True, default='622')
    complete_pct = fields.Float('Mức độ hoàn thành của sản phẩm dở dang (%)', default=50,
                                help='Chi phí nguyên vật liệu trực tiếp bỏ vào ngay từ đầu nên dở dang chịu đủ; '
                                     'chi phí nhân công và sản xuất chung chịu theo mức độ hoàn thành này.')
    warehouse_id = fields.Many2one('lfood.warehouse', 'Kho nhập thành phẩm', required=True,
                                   domain="[('company_id', '=', company_id)]")
    create_picking = fields.Boolean('Tự lập phiếu nhập kho thành phẩm', default=True,
                                    help='Bỏ chọn khi kế toán đã lập phiếu nhập kho thành phẩm trong kỳ; '
                                         'khi đó kỳ tính giá thành chỉ tính và kết chuyển chi phí.')
    line_ids = fields.One2many('lfood.costing.line', 'run_id', 'Sản phẩm')
    overhead_pool = fields.Float('Chi phí sản xuất chung chờ phân bổ', digits=(16, 0), readonly=True)
    total_cost = fields.Float('Tổng giá thành', compute='_compute_total', digits=(16, 0))
    state = fields.Selection([('draft', 'Nháp'), ('done', 'Đã ghi sổ')], 'Trạng thái', default='draft', required=True)
    picking_ids = fields.One2many('lfood.stock.picking', 'costing_run_id', 'Phiếu nhập kho thành phẩm', readonly=True)
    note = fields.Text('Diễn giải')

    _period_uniq = models.Constraint('unique(company_id, year, month)', 'Mỗi công ty mỗi tháng chỉ tính giá thành một lần.')

    @api.depends('year', 'month')
    def _compute_dates(self):
        for rec in self:
            m = int(rec.month or 1)
            rec.date_from = date(rec.year, m, 1)
            rec.date_to = date(rec.year, m, calendar.monthrange(rec.year, m)[1])

    @api.depends('line_ids.total_cost')
    def _compute_total(self):
        for rec in self:
            rec.total_cost = sum(rec.line_ids.mapped('total_cost'))

    @api.depends('year', 'month', 'company_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('Giá thành %s/%s') % (rec.month, rec.year)

    def _sum(self, prefix, product=None, tagged=True):
        """Tổng phát sinh Nợ trong kỳ của nhóm tài khoản, theo sản phẩm hoặc phần chưa gắn sản phẩm."""
        self.ensure_one()
        domain = [('state', '=', 'posted'), ('company_id', '=', self.company_id.id),
                  ('date', '>=', self.date_from), ('date', '<=', self.date_to),
                  ('account_code', '=like', prefix + '%')]
        domain.append(('cost_product_id', '=', product.id if product else False))
        lines = self.env['lfood.move.line'].sudo().search(domain)
        return round(sum(lines.mapped('debit')) - sum(lines.mapped('credit')))

    def _balances_by_account(self):
        """Phát sinh trong kỳ của 621, 622, 627 theo từng tài khoản chi tiết, để kết chuyển đúng tài khoản."""
        self.ensure_one()
        lines = self.env['lfood.move.line'].sudo().search([
            ('state', '=', 'posted'), ('company_id', '=', self.company_id.id),
            ('date', '>=', self.date_from), ('date', '<=', self.date_to),
            '|', '|', ('account_code', '=like', '621%'), ('account_code', '=like', '622%'),
            ('account_code', '=like', '627%')])
        out = {}
        for l in lines:
            out[l.account_code] = round(out.get(l.account_code, 0) + l.debit - l.credit)
        return out

    def action_collect(self):
        """Tập hợp chi phí thực tế trong kỳ từ sổ kế toán và dở dang đầu kỳ từ kỳ trước."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Kỳ đã ghi sổ, không tập hợp lại.'))
            if not rec.line_ids:
                raise UserError(_('Chưa khai sản phẩm cần tính giá thành.'))
            rec.overhead_pool = rec._sum('627')
            prev = rec.search([('company_id', '=', rec.company_id.id), ('state', '=', 'done'),
                               ('date_to', '<', rec.date_from)], order='date_to desc', limit=1)
            for line in rec.line_ids:
                old = prev.line_ids.filtered(lambda l: l.product_id == line.product_id)[:1]
                line.write({
                    'cost_dm': rec._sum('621', line.product_id),
                    'cost_labor': rec._sum('622', line.product_id),
                    'cost_overhead_direct': rec._sum('627', line.product_id),
                    'pct': line.pct or rec.complete_pct,
                    'open_dm': old.wip_dm_end if old else line.open_dm,
                    'open_conv': old.wip_conv_end if old else line.open_conv,
                })
            rec._allocate()
        return True

    def _allocate(self):
        """Phân bổ chi phí sản xuất chung chưa gắn sản phẩm theo tiêu thức đã chọn."""
        self.ensure_one()
        weights = {}
        for line in self.line_ids:
            weights[line.id] = {'622': line.cost_labor, '621': line.cost_dm, 'qty': line.qty_done}[self.basis]
        shares = calc.allocate(self.overhead_pool, weights)
        for line in self.line_ids:
            line.cost_overhead_alloc = shares.get(line.id, 0)

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được ghi sổ kỳ tính giá thành.'))
        Move = self.env['lfood.move']
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.line_ids:
                raise UserError(_('Chưa khai sản phẩm cần tính giá thành.'))
            if any(l.qty_done <= 0 for l in rec.line_ids):
                raise UserError(_('Sản lượng hoàn thành phải lớn hơn 0.'))
            rec._allocate()
            label = _('Kết chuyển chi phí sản xuất %s/%s') % (rec.month, rec.year)
            lines = []
            for code, total in sorted(rec._balances_by_account().items()):
                if total:
                    lines += [('154', total, 0, None, label, None), (code, 0, total, None, label, None)]
            if lines:
                Move._create_from_source(rec, 'general', rec.date_to, lines, memo=label, key='costing',
                                         ref=rec.display_name)
            pick = self.env['lfood.stock.picking']
            if rec.create_picking:
                pick = self.env['lfood.stock.picking'].with_company(rec.company_id).create({
                    'kind': 'in', 'purpose': 'factory', 'date': rec.date_to, 'warehouse_id': rec.warehouse_id.id,
                    'company_id': rec.company_id.id, 'costing_run_id': rec.id,
                    'memo': _('Nhập kho thành phẩm theo giá thành %s/%s') % (rec.month, rec.year),
                    'line_ids': [(0, 0, {'product_id': l.product_id.id, 'quantity': l.qty_done,
                                         'price_unit': l.unit_cost}) for l in rec.line_ids],
                })
                pick.action_done()
            rec.state = 'done'
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.display_name, company_id=rec.company_id.id,
                summary=_('Tính giá thành %s/%s: %s, nhập kho %s') % (
                    rec.month, rec.year, ', '.join('%s %s đ/%s' % (l.product_id.code, vnd(l.unit_cost), l.product_id.uom)
                                                   for l in rec.line_ids), pick.name or _('kế toán tự lập')))
        return True

    def action_open_moves(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Bút toán'), 'res_model': 'lfood.move',
                'view_mode': 'list,form',
                'domain': [('source_model', '=', self._name), ('source_id', '=', self.id)]}


class CostingLine(models.Model):
    _name = 'lfood.costing.line'
    _description = 'Giá thành từng sản phẩm'

    run_id = fields.Many2one('lfood.costing.run', 'Kỳ tính giá thành', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('lfood.product', 'Sản phẩm', required=True, ondelete='restrict',
                                 domain="[('kind', '=', 'finished')]")
    open_dm = fields.Float('Dở dang đầu kỳ: nguyên vật liệu', digits=(16, 0))
    open_conv = fields.Float('Dở dang đầu kỳ: nhân công và sản xuất chung', digits=(16, 0))
    cost_dm = fields.Float('Chi phí nguyên vật liệu trực tiếp (621)', digits=(16, 0), readonly=True)
    cost_labor = fields.Float('Chi phí nhân công trực tiếp (622)', digits=(16, 0), readonly=True)
    cost_overhead_direct = fields.Float('Chi phí chung gắn thẳng (627)', digits=(16, 0), readonly=True)
    cost_overhead_alloc = fields.Float('Chi phí chung phân bổ (627)', digits=(16, 0), readonly=True)
    qty_done = fields.Float('Sản lượng hoàn thành', digits=(16, 2))
    qty_wip = fields.Float('Sản lượng dở dang cuối kỳ', digits=(16, 2))
    pct = fields.Float('Mức độ hoàn thành (%)', default=50)
    wip_dm_end = fields.Float('Dở dang cuối kỳ: nguyên vật liệu', compute='_compute_cost', store=True, digits=(16, 0))
    wip_conv_end = fields.Float('Dở dang cuối kỳ: chế biến', compute='_compute_cost', store=True, digits=(16, 0))
    total_cost = fields.Float('Tổng giá thành', compute='_compute_cost', store=True, digits=(16, 0))
    unit_cost = fields.Float('Giá thành đơn vị', compute='_compute_cost', store=True, digits=(16, 0))

    @api.depends('open_dm', 'open_conv', 'cost_dm', 'cost_labor', 'cost_overhead_direct', 'cost_overhead_alloc',
                 'qty_done', 'qty_wip', 'pct')
    def _compute_cost(self):
        for rec in self:
            conv = rec.cost_labor + rec.cost_overhead_direct + rec.cost_overhead_alloc
            total, unit, dm_end, conv_end = calc.unit_cost(rec.open_dm, rec.cost_dm, rec.open_conv, conv,
                                                           rec.qty_done, rec.qty_wip, rec.pct)
            rec.wip_dm_end, rec.wip_conv_end, rec.total_cost, rec.unit_cost = dm_end, conv_end, total, unit
