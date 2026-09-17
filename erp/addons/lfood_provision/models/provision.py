"""Trích lập và xử lý dự phòng: nợ phải thu khó đòi (2293) và giảm giá hàng tồn kho (2294).

Theo Thông tư 48/2019/TT-BTC, trích lập tại thời điểm lập báo cáo tài chính năm. App so số phải trích
kỳ này với số dự phòng đang có trên sổ rồi chỉ ghi phần chênh lệch:
- Nợ phải thu khó đòi: trích thêm Nợ 6426 / Có 2293; hoàn nhập ghi ngược lại.
- Giảm giá hàng tồn kho: trích thêm Nợ 632 / Có 2294; hoàn nhập ghi giảm giá vốn.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd
from .calc import months_overdue, receivable_rate, inventory_provision, adjustment

KINDS = [('receivable', 'Dự phòng nợ phải thu khó đòi'), ('inventory', 'Dự phòng giảm giá hàng tồn kho')]
SETUP = {
    'receivable': {'provision_account': '2293', 'expense_account': '6426'},
    'inventory': {'provision_account': '2294', 'expense_account': '632'},
}
BRACKET_PARAMS = [('DU_PHONG_PTKD_THANG_1', 'DU_PHONG_PTKD_TY_LE_1'), ('DU_PHONG_PTKD_THANG_2', 'DU_PHONG_PTKD_TY_LE_2'),
                  ('DU_PHONG_PTKD_THANG_3', 'DU_PHONG_PTKD_TY_LE_3'), ('DU_PHONG_PTKD_THANG_4', 'DU_PHONG_PTKD_TY_LE_4')]


class LfoodProvision(models.Model):
    _name = 'lfood.provision'
    _description = 'Trích lập dự phòng'
    _order = 'date desc, id desc'

    name = fields.Char('Số chứng từ', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    kind = fields.Selection(KINDS, 'Loại dự phòng', required=True, default='receivable', index=True)
    date = fields.Date('Thời điểm trích lập', required=True, index=True,
                       default=lambda s: fields.Date.context_today(s).replace(month=12, day=31),
                       help='Trích lập khi lập báo cáo tài chính năm theo Thông tư 48/2019/TT-BTC')
    memo = fields.Char('Diễn giải')
    line_ids = fields.One2many('lfood.provision.line', 'provision_id', 'Chi tiết', copy=True)
    required_amount = fields.Float('Số phải trích kỳ này', digits=(16, 0), compute='_compute_amounts', store=True)
    existing_amount = fields.Float('Số đã trích trên sổ', digits=(16, 0), compute='_compute_amounts', store=True)
    adjust_amount = fields.Float('Chênh lệch ghi kỳ này', digits=(16, 0), compute='_compute_amounts', store=True,
                                 help='Dương là trích thêm, âm là hoàn nhập')
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)

    @api.depends('line_ids.provision', 'date', 'kind', 'company_id', 'state')
    def _compute_amounts(self):
        for rec in self:
            rec.required_amount = sum(rec.line_ids.mapped('provision'))
            rec.existing_amount = rec._existing()
            rec.adjust_amount = adjustment(rec.required_amount, rec.existing_amount)

    def _existing(self):
        """Số dư dự phòng đang có trên sổ trước chứng từ này (số dư Có của 2293 hoặc 2294)."""
        self.ensure_one()
        if not self.date:
            return 0.0
        domain = [('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
                  ('account_code', '=', SETUP[self.kind]['provision_account']), ('date', '<=', self.date)]
        move = self.env['lfood.move']._active_for(self)
        if move:
            domain.append(('move_id', '!=', move.id))
        lines = self.env['lfood.move.line'].sudo().search(domain)
        return -sum(lines.mapped('balance'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.provision') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_provision_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái chỉ đổi bằng nút Ghi sổ, Hủy.'))
            if self.filtered(lambda r: r.state != 'draft'):
                raise UserError(_('Chứng từ đã ghi sổ không sửa được. Hủy rồi lập chứng từ mới.'))
        return super().write(vals)

    def _brackets(self):
        """Bậc tỷ lệ trích lập lấy từ Tham số pháp lý."""
        self.ensure_one()
        Param = self.env['lfood.legal.param']
        return [(int(Param.get_value(m, self.date)), Param.get_value(r, self.date)) for m, r in BRACKET_PARAMS]

    def action_load(self):
        """Lấy số liệu từ sổ: nợ phải thu quá hạn, hoặc hàng tồn kho đang còn."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Chỉ lấy số liệu khi chứng từ còn là Nháp.'))
        self.line_ids.unlink()
        if self.kind == 'receivable':
            self._load_receivable()
        else:
            self._load_inventory()
        return True

    def _load_receivable(self):
        """Từng hóa đơn bán hàng còn nợ, tính tuổi nợ theo hạn thanh toán của hóa đơn."""
        brackets = self._brackets()
        Line = self.env['lfood.provision.line']
        Payment = self.env['lfood.payment'].sudo()
        Invoice = self.env['lfood.sale.invoice'].sudo()
        for inv in Invoice.search([('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
                                   ('kind', '=', 'invoice'), ('date', '<=', self.date)]):
            paid = sum(p.amount if p.kind == 'in' else -p.amount for p in Payment.search(
                [('sale_invoice_id', '=', inv.id), ('state', '=', 'posted'), ('date', '<=', self.date)]))
            refunds = sum(Invoice.search([('origin_id', '=', inv.id), ('state', '=', 'posted'),
                                          ('date', '<=', self.date)]).mapped('amount_total'))
            residual = round(inv.amount_total - paid - refunds)
            if residual <= 0:
                continue
            due = inv.due_date or inv.date
            months = months_overdue(due, self.date)
            rate = receivable_rate(months, brackets)
            if not rate:
                continue
            Line.create({
                'provision_id': self.id, 'partner_id': inv.partner_id.id, 'due_date': due,
                'months_overdue': months, 'rate': rate, 'base_amount': residual,
                'note': inv.invoice_number or inv.name})

    def _load_inventory(self):
        """Hàng tồn kho đang còn; kế toán nhập giá trị thuần có thể thực hiện được của từng mặt hàng."""
        Line = self.env['lfood.provision.line']
        for product in self.env['lfood.product'].sudo().search([('company_id', 'in', (False, self.company_id.id))]):
            qty, value = product._position(upto=self.date)
            if qty <= 0:
                continue
            unit_cost = round(value / qty, 2)
            # mặc định giá trị thuần bằng giá gốc: chưa trích cho tới khi kế toán nhập giá trị thuần thấp hơn
            Line.create({'provision_id': self.id, 'product_id': product.id, 'quantity': qty,
                         'unit_cost': unit_cost, 'net_realisable': unit_cost, 'base_amount': round(value)})

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được ghi sổ trích lập dự phòng.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.line_ids:
                raise UserError(_('Chứng từ chưa có dòng nào.'))
            setup = SETUP[rec.kind]
            amount = rec.adjust_amount
            label = _('%s %s') % (dict(KINDS)[rec.kind], rec.date.strftime('%d/%m/%Y'))
            if amount > 0:
                lines = [(setup['expense_account'], amount, 0, None, label, None),
                         (setup['provision_account'], 0, amount, None, label, None)]
            elif amount < 0:
                lines = [(setup['provision_account'], -amount, 0, None, label, None),
                         (setup['expense_account'], 0, -amount, None, label, None)]
            else:
                lines = []
            if lines:
                self.env['lfood.move']._create_from_source(rec, 'general', rec.date, lines, memo=label, ref=rec.name)
            rec.with_context(lfood_provision_system=True).write({'state': 'posted'})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('%s: phải trích %s, đã trích %s, %s %s') % (
                    label, vnd(rec.required_amount), vnd(rec.existing_amount),
                    _('trích thêm') if amount >= 0 else _('hoàn nhập'), vnd(abs(amount))))
        return True

    def action_cancel(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được hủy chứng từ đã ghi sổ.'))
        for rec in self.filtered(lambda r: r.state == 'posted'):
            move = self.env['lfood.move']._active_for(rec)
            if move:
                move._reverse(memo=_('Hủy %s') % rec.name)
            rec.with_context(lfood_provision_system=True).write({'state': 'cancel'})
        return True


class LfoodProvisionLine(models.Model):
    _name = 'lfood.provision.line'
    _description = 'Dòng trích lập dự phòng'
    _order = 'provision_id, id'

    provision_id = fields.Many2one('lfood.provision', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='provision_id.company_id', store=True, index=True)
    kind = fields.Selection(related='provision_id.kind', store=True)
    # nợ phải thu khó đòi
    partner_id = fields.Many2one('res.partner', 'Đối tượng')
    due_date = fields.Date('Hạn thanh toán')
    months_overdue = fields.Integer('Số tháng quá hạn', readonly=True)
    rate = fields.Float('Tỷ lệ trích (%)', digits=(16, 2), readonly=True)
    # giảm giá hàng tồn kho
    product_id = fields.Many2one('lfood.product', 'Mặt hàng')
    quantity = fields.Float('Số lượng tồn', digits=(16, 3))
    unit_cost = fields.Float('Giá gốc một đơn vị', digits=(16, 2))
    net_realisable = fields.Float('Giá trị thuần có thể thực hiện được', digits=(16, 2))
    # chung
    base_amount = fields.Float('Giá trị gốc', digits=(16, 0))
    provision = fields.Float('Số dự phòng', digits=(16, 0), compute='_compute_provision', store=True, readonly=False)
    note = fields.Char('Ghi chú, hồ sơ chứng minh')

    @api.depends('kind', 'base_amount', 'rate', 'quantity', 'unit_cost', 'net_realisable')
    def _compute_provision(self):
        for rec in self:
            if rec.kind == 'inventory':
                rec.provision = inventory_provision(rec.quantity, rec.unit_cost, rec.net_realisable)
            else:
                rec.provision = round(rec.base_amount * rec.rate / 100)

    def write(self, vals):
        if not self.env.context.get('lfood_provision_system') and self.filtered(lambda l: l.provision_id.state != 'draft'):
            raise UserError(_('Chứng từ đã ghi sổ không sửa được.'))
        return super().write(vals)
