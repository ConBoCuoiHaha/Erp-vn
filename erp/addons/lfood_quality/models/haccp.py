"""Giám sát điểm kiểm soát tới hạn HACCP (CL02).

Mỗi điểm kiểm soát tới hạn (CCP) có công đoạn, mối nguy, thông số giám sát (nhiệt độ, thời gian...), giới hạn tới hạn,
tần suất đo và hành động khắc phục định sẵn (theo kế hoạch HACCP của nhà máy, nguyên tắc HACCP của Codex và ISO 22000). Mỗi lần đo
ghi giá trị, lô đang sản xuất, người đo. Giá trị ngoài giới hạn: app giữ lô (cách ly) và mở hành động khắc phục; lô chỉ
được giải phóng theo quy trình giải phóng lô. Người phụ trách chất lượng xác nhận hồ sơ giám sát theo ngày.
"""
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class LfoodCcp(models.Model):
    _name = 'lfood.ccp'
    _description = 'Điểm kiểm soát tới hạn'
    _order = 'code'

    code = fields.Char('Mã CCP', required=True)
    name = fields.Char('Công đoạn', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    hazard = fields.Char('Mối nguy kiểm soát', required=True)
    parameter = fields.Char('Thông số giám sát', required=True, help='Ví dụ nhiệt độ tâm sản phẩm, thời gian tiệt trùng')
    unit = fields.Char('Đơn vị')
    limit_min = fields.Float('Giới hạn dưới', digits=(16, 3))
    limit_max = fields.Float('Giới hạn trên', digits=(16, 3))
    has_min = fields.Boolean('Có giới hạn dưới', default=True)
    has_max = fields.Boolean('Có giới hạn trên')
    frequency_hours = fields.Float('Tần suất đo (giờ/lần)', default=1)
    corrective_action = fields.Text('Hành động khắc phục định sẵn', required=True)
    product_ids = fields.Many2many('lfood.product', string='Áp dụng cho mặt hàng')
    reading_ids = fields.One2many('lfood.ccp.reading', 'ccp_id', 'Kết quả giám sát')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique(company_id, code)', 'Mã CCP đã có.')

    @api.constrains('has_min', 'has_max', 'limit_min', 'limit_max')
    def _check_limits(self):
        for rec in self:
            if not (rec.has_min or rec.has_max):
                raise ValidationError(_('CCP %s phải có ít nhất một giới hạn tới hạn.') % rec.code)
            if rec.has_min and rec.has_max and rec.limit_min > rec.limit_max:
                raise ValidationError(_('Giới hạn dưới lớn hơn giới hạn trên.'))

    def _in_limit(self, value):
        self.ensure_one()
        return (not self.has_min or value >= self.limit_min) and (not self.has_max or value <= self.limit_max)


class LfoodCcpReading(models.Model):
    _name = 'lfood.ccp.reading'
    _description = 'Kết quả giám sát CCP'
    _order = 'measured_at desc, id desc'

    ccp_id = fields.Many2one('lfood.ccp', 'CCP', required=True, index=True, ondelete='restrict')
    company_id = fields.Many2one(related='ccp_id.company_id', store=True, index=True)
    measured_at = fields.Datetime('Thời điểm đo', required=True, default=fields.Datetime.now)
    value = fields.Float('Giá trị đo', digits=(16, 3), required=True)
    unit = fields.Char(related='ccp_id.unit')
    lot_id = fields.Many2one('lfood.stock.lot', 'Lô đang sản xuất', index=True)
    operator = fields.Char('Người đo', required=True)
    in_limit = fields.Boolean('Trong giới hạn', compute='_compute_in_limit', store=True)
    deviation_note = fields.Char('Mô tả sai lệch')
    action_id = fields.Many2one('lfood.qc.action', 'Hành động khắc phục', readonly=True)
    verified_by = fields.Many2one('res.users', 'Người xác nhận hồ sơ', readonly=True)
    verified_on = fields.Datetime('Thời điểm xác nhận', readonly=True)

    @api.depends('value', 'ccp_id.limit_min', 'ccp_id.limit_max', 'ccp_id.has_min', 'ccp_id.has_max')
    def _compute_in_limit(self):
        for rec in self:
            rec.in_limit = rec.ccp_id._in_limit(rec.value) if rec.ccp_id else True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs.filtered(lambda r: not r.in_limit):
            ccp = rec.ccp_id
            limits = '%s%s%s' % ('%g' % ccp.limit_min if ccp.has_min else '', ' - ', '%g' % ccp.limit_max if ccp.has_max else '')
            reason = _('%s ngoài giới hạn tới hạn: %s %s (giới hạn %s)') % (ccp.code, '%g' % rec.value, ccp.unit or '', limits)
            if rec.lot_id:
                rec.lot_id.sudo().action_hold(reason)
            rec.action_id = self.env['lfood.qc.action'].sudo().create({
                'name': reason, 'company_id': rec.company_id.id, 'measure': ccp.corrective_action,
                'cause': rec.deviation_note or False, 'deadline': fields.Date.context_today(self) + timedelta(days=1)})
        return recs

    def write(self, vals):
        if set(vals) - {'verified_by', 'verified_on', 'deviation_note', 'action_id'}:
            raise UserError(_('Kết quả giám sát đã ghi không sửa được; ghi lần đo mới.'))
        return super().write(vals)

    def unlink(self):
        raise UserError(_('Hồ sơ giám sát CCP không được xóa.'))

    def action_verify(self):
        for rec in self.filtered(lambda r: not r.verified_by):
            if not rec.in_limit and rec.action_id.state != 'done':
                raise UserError(_('Lần đo %s ngoài giới hạn: hoàn thành hành động khắc phục trước khi xác nhận.')
                                % rec.ccp_id.code)
            rec.write({'verified_by': self.env.uid, 'verified_on': fields.Datetime.now()})
        return True


class LfoodReminder(models.Model):
    _inherit = 'lfood.reminder'

    def _collect_extra(self, company, today, horizon):
        """CCP quá một ngày làm việc chưa có kết quả giám sát (nhắc hôm nay)."""
        out = super()._collect_extra(company, today, horizon)
        for ccp in self.env['lfood.ccp'].sudo().search([('company_id', '=', company.id)]):
            last = ccp.reading_ids[:1]
            if last and self.env['lfood.holiday'].working_days_between(last.measured_at.date(), today) > 1:
                out.append({'key': 'ccp-gap-%s-%s' % (ccp.id, last.measured_at.date()), 'category': 'quality',
                            'title': _('CCP %s chưa có kết quả giám sát từ %s') % (
                                ccp.code, last.measured_at.date().strftime('%d/%m/%Y')),
                            'due_date': today, 'res_model': ccp._name, 'res_id': ccp.id})
        return out
