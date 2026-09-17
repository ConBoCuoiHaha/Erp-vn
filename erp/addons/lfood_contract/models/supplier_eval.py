"""Đánh giá nhà cung cấp (MH13): tỷ lệ giao đúng hạn, tỷ lệ lô đạt kiểm tra chất lượng lấy từ app, điểm giá và dịch vụ
chấm tay; tổng điểm quyết định chấp thuận, chấp thuận có điều kiện hoặc loại. Nhà cung cấp bị loại không đặt hàng được.
Tiêu chí và trọng số là quy chế nội bộ (ISO 22000 yêu cầu đánh giá nhà cung cấp), sửa được trên từng phiếu.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

STATUS = [('approved', 'Chấp thuận'), ('conditional', 'Chấp thuận có điều kiện'), ('rejected', 'Loại')]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    lfood_supplier_status = fields.Selection(STATUS, 'Kết quả đánh giá nhà cung cấp', readonly=True)


class LfoodSupplierEvaluation(models.Model):
    _name = 'lfood.supplier.evaluation'
    _description = 'Đánh giá nhà cung cấp'
    _order = 'date_to desc, id desc'

    name = fields.Char('Số', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    partner_id = fields.Many2one('res.partner', 'Nhà cung cấp', required=True, index=True)
    date_from = fields.Date('Kỳ đánh giá từ', required=True)
    date_to = fields.Date('Đến', required=True)
    orders = fields.Integer('Số đơn mua', readonly=True)
    on_time_rate = fields.Float('Giao đúng hạn (%)', digits=(5, 1), readonly=True)
    quality_rate = fields.Float('Lô đạt kiểm tra chất lượng (%)', digits=(5, 1), readonly=True)
    price_score = fields.Float('Điểm giá cả (0-100)', digits=(5, 1), default=80)
    service_score = fields.Float('Điểm dịch vụ, hồ sơ (0-100)', digits=(5, 1), default=80)
    weight_delivery = fields.Float('Trọng số giao hàng (%)', default=30)
    weight_quality = fields.Float('Trọng số chất lượng (%)', default=40)
    weight_price = fields.Float('Trọng số giá (%)', default=20)
    weight_service = fields.Float('Trọng số dịch vụ (%)', default=10)
    score = fields.Float('Tổng điểm', digits=(5, 1), compute='_compute_score', store=True)
    result = fields.Selection(STATUS, 'Kết quả', compute='_compute_score', store=True)
    note = fields.Text('Nhận xét, yêu cầu khắc phục')
    state = fields.Selection([('draft', 'Nháp'), ('done', 'Đã kết luận')], 'Trạng thái', default='draft', required=True,
                             readonly=True, copy=False)

    @api.depends('on_time_rate', 'quality_rate', 'price_score', 'service_score', 'weight_delivery', 'weight_quality',
                 'weight_price', 'weight_service')
    def _compute_score(self):
        for rec in self:
            rec.score = round((rec.on_time_rate * rec.weight_delivery + rec.quality_rate * rec.weight_quality
                               + rec.price_score * rec.weight_price + rec.service_score * rec.weight_service) / 100, 1)
            rec.result = 'approved' if rec.score >= 80 else 'conditional' if rec.score >= 60 else 'rejected'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('lfood.supplier.evaluation') or '/'
        return super().create(vals_list)

    @api.constrains('weight_delivery', 'weight_quality', 'weight_price', 'weight_service')
    def _check_weights(self):
        for rec in self:
            if round(rec.weight_delivery + rec.weight_quality + rec.weight_price + rec.weight_service, 2) != 100:
                raise ValidationError(_('Tổng trọng số phải bằng 100%.'))

    def action_compute(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            orders = self.env['lfood.purchase.order'].sudo().search([
                ('company_id', '=', rec.company_id.id), ('partner_id', '=', rec.partner_id.id),
                ('state', 'in', ('confirmed', 'done')), ('date', '>=', rec.date_from), ('date', '<=', rec.date_to)])
            timed = orders.filtered('date_expected')
            on_time = 0
            for o in timed:
                first = o.picking_ids.filtered(lambda p: p.state == 'done').sorted('date')[:1]
                on_time += bool(first) and first.date <= o.date_expected
            checks = self.env['lfood.qc.check'].sudo().search([
                ('picking_id.partner_id', '=', rec.partner_id.id), ('company_id', '=', rec.company_id.id),
                ('state', 'in', ('passed', 'failed')), ('date', '>=', rec.date_from), ('date', '<=', rec.date_to)])
            rec.write({
                'orders': len(orders),
                'on_time_rate': round(on_time * 100 / len(timed), 1) if timed else 100,
                'quality_rate': round(len(checks.filtered(lambda c: c.state == 'passed')) * 100 / len(checks), 1)
                if checks else 100,
            })
        return True

    def action_done(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if rec.result != 'approved' and not rec.note:
                raise UserError(_('Ghi nhận xét, yêu cầu khắc phục khi nhà cung cấp không đạt chấp thuận.'))
            rec.write({'state': 'done'})
            rec.partner_id.sudo().write({'lfood_supplier_status': rec.result})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Đánh giá %s: %s điểm, %s') % (rec.partner_id.name, rec.score,
                                                         dict(STATUS)[rec.result]))
        return True
