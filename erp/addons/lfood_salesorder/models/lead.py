"""Cơ hội bán hàng (BH01): nhà phân phối, siêu thị tiềm năng và các giai đoạn chăm sóc.

Giai đoạn: mới, đã liên hệ, gửi mẫu, đàm phán, thành công, thất bại. Doanh số dự kiến nhân xác suất theo giai đoạn
ra doanh số có trọng số để dự báo. Thành công thì tạo khách hàng (gắn kênh) và báo giá nháp; thất bại phải ghi lý do.
Số điện thoại, email người liên hệ là dữ liệu cá nhân: chỉ dùng cho việc chào hàng (Luật Bảo vệ dữ liệu cá nhân 2025).
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

STAGES = [('new', 'Mới'), ('contacted', 'Đã liên hệ'), ('sample', 'Gửi mẫu, dùng thử'), ('negotiation', 'Đàm phán'),
          ('won', 'Thành công'), ('lost', 'Thất bại')]
PROBABILITY = {'new': 10, 'contacted': 20, 'sample': 40, 'negotiation': 70, 'won': 100, 'lost': 0}


class LfoodSaleLead(models.Model):
    _name = 'lfood.sale.lead'
    _description = 'Cơ hội bán hàng'
    _order = 'stage_sequence, next_date, id desc'

    name = fields.Char('Cơ hội', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    prospect = fields.Char('Tên đơn vị tiềm năng', required=True)
    vat = fields.Char('Mã số thuế')
    partner_id = fields.Many2one('res.partner', 'Khách hàng', help='Chọn nếu đã có trong danh mục')
    contact_name = fields.Char('Người liên hệ')
    phone = fields.Char('Điện thoại')
    email = fields.Char('Email')
    city = fields.Char('Tỉnh, thành')
    channel_id = fields.Many2one('lfood.sale.channel', 'Kênh')
    user_id = fields.Many2one('res.users', 'Nhân viên phụ trách', default=lambda s: s.env.user, index=True)
    stage = fields.Selection(STAGES, 'Giai đoạn', required=True, default='new', group_expand='_expand_stages', index=True)
    stage_sequence = fields.Integer(compute='_compute_stage_sequence', store=True)
    expected_revenue = fields.Float('Doanh số dự kiến / tháng', digits=(16, 0))
    probability = fields.Float('Xác suất (%)', compute='_compute_probability', store=True, readonly=False)
    weighted_revenue = fields.Float('Doanh số có trọng số', digits=(16, 0), compute='_compute_weighted', store=True)
    next_action = fields.Char('Việc tiếp theo')
    next_date = fields.Date('Hạn việc tiếp theo', index=True)
    lost_reason = fields.Char('Lý do thất bại')
    note = fields.Text('Ghi chú chăm sóc')
    order_id = fields.Many2one('lfood.sale.order', 'Báo giá', readonly=True, copy=False)

    @api.model
    def _expand_stages(self, stages, domain):
        return [s for s, _l in STAGES]

    @api.depends('stage')
    def _compute_stage_sequence(self):
        order = [s for s, _l in STAGES]
        for rec in self:
            rec.stage_sequence = order.index(rec.stage) if rec.stage in order else 0

    @api.depends('stage')
    def _compute_probability(self):
        for rec in self:
            rec.probability = PROBABILITY.get(rec.stage, 0)

    @api.depends('expected_revenue', 'probability')
    def _compute_weighted(self):
        for rec in self:
            rec.weighted_revenue = round(rec.expected_revenue * rec.probability / 100)

    def write(self, vals):
        if vals.get('stage') in ('won', 'lost') and not self.env.context.get('lfood_lead_system'):
            raise UserError(_('Dùng nút Thành công hoặc Thất bại để kết thúc cơ hội.'))
        return super().write(vals)

    def action_won(self):
        for rec in self.filtered(lambda r: r.stage not in ('won', 'lost')):
            partner = rec.partner_id
            if not partner and rec.vat:
                partner = self.env['res.partner'].search([('vat', '=', rec.vat)], limit=1)
            if not partner:
                partner = self.env['res.partner'].create({
                    'name': rec.prospect, 'is_company': True, 'vat': rec.vat, 'city': rec.city,
                    'lfood_channel_id': rec.channel_id.id})
                if rec.contact_name:
                    self.env['res.partner'].create({'name': rec.contact_name, 'parent_id': partner.id,
                                                    'phone': rec.phone, 'email': rec.email})
            order = self.env['lfood.sale.order'].create({
                'partner_id': partner.id, 'company_id': rec.company_id.id, 'user_id': rec.user_id.id,
                'memo': _('Từ cơ hội %s') % rec.name})
            rec.with_context(lfood_lead_system=True).write({'stage': 'won', 'partner_id': partner.id, 'order_id': order.id})
        return True

    def action_lost(self):
        for rec in self.filtered(lambda r: r.stage not in ('won', 'lost')):
            if not rec.lost_reason:
                raise UserError(_('Ghi lý do thất bại.'))
            rec.with_context(lfood_lead_system=True).write({'stage': 'lost'})
        return True

    def action_reopen(self):
        self.filtered(lambda r: r.stage == 'lost').with_context(lfood_lead_system=True).write({'stage': 'contacted'})
        return True
