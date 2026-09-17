from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

PARAM_GROUPS = [
    ('vat', 'Thuế GTGT'), ('cit', 'Thuế TNDN'), ('pit', 'Thuế TNCN'), ('salary', 'Tiền lương'),
    ('insurance', 'Bảo hiểm & công đoàn'), ('labor', 'Lao động'), ('accounting', 'Kế toán'),
    ('asset', 'Tài sản'), ('other', 'Khác'),
]


class LfoodLegalParam(models.Model):
    _name = 'lfood.legal.param'
    _description = 'Tham số pháp lý'
    _order = 'group, code'

    code = fields.Char('Mã tham số', required=True, index=True,
                       help='Mã dùng trong công thức, ví dụ LUONG_CO_SO')
    name = fields.Char('Tên', required=True)
    group = fields.Selection(PARAM_GROUPS, 'Nhóm', required=True, default='other')
    value_type = fields.Selection([('amount', 'Số tiền (đồng)'), ('percent', 'Tỷ lệ (%)'), ('number', 'Số')],
                                  'Kiểu giá trị', required=True, default='amount')
    kind = fields.Selection([('law', 'Theo luật'), ('policy', 'Quy chế công ty')], 'Loại', default='law', required=True)
    description = fields.Text('Dùng ở đâu')
    value_ids = fields.One2many('lfood.legal.param.value', 'param_id', 'Các mức theo thời gian')
    current_value = fields.Float('Mức đang áp dụng', compute='_compute_current', digits=(16, 4))
    current_ref = fields.Char('Căn cứ hiện hành', compute='_compute_current')

    @api.constrains('code')
    def _check_code(self):
        for rec in self:
            if self.search_count([('code', '=', rec.code), ('id', '!=', rec.id)]):
                raise ValidationError(_('Mã tham số %s đã tồn tại.') % rec.code)

    def _compute_current(self):
        today = fields.Date.context_today(self)
        for rec in self:
            val = rec.value_ids._find(today)
            rec.current_value = val.value if val else 0.0
            rec.current_ref = val.legal_ref if val else False

    def unlink(self):
        used = self.filtered(lambda p: p.value_ids.filtered(lambda v: v.state == 'approved'))
        if used:
            raise UserError(_('Tham số %s đã có mức được duyệt nên không xóa được.') % ', '.join(used.mapped('code')))
        return super().unlink()

    @api.model
    def get_value(self, code, date=None, default=None):
        """Lấy giá trị đã duyệt của tham số tại một ngày. Mọi công thức gọi hàm này."""
        sim = self.env.context.get('lfood_param_sim') or {}
        if code in sim:  # tính thử (CH03): mức chưa duyệt, không ghi gì
            return sim[code]
        date = date or fields.Date.context_today(self)
        param = self.sudo().search([('code', '=', code)], limit=1)
        val = param.value_ids._find(date) if param else None
        if not val:
            if default is not None:
                return default
            raise UserError(_('Chưa cấu hình tham số %s áp dụng cho ngày %s. Vào Cấu hình > Tham số pháp lý.') % (code, date))
        return val.value


class LfoodLegalParamValue(models.Model):
    _name = 'lfood.legal.param.value'
    _description = 'Mức tham số theo thời gian'
    _order = 'date_from desc'

    param_id = fields.Many2one('lfood.legal.param', 'Tham số', required=True, ondelete='cascade', index=True)
    value = fields.Float('Giá trị', digits=(16, 4), required=True)
    date_from = fields.Date('Áp dụng từ', required=True)
    date_to = fields.Date('Áp dụng đến')
    legal_ref = fields.Char('Văn bản căn cứ')
    note = fields.Char('Ghi chú')
    state = fields.Selection([('draft', 'Chờ duyệt'), ('approved', 'Đang áp dụng / đã duyệt')],
                             'Trạng thái', default='draft', required=True)
    approved_by = fields.Many2one('res.users', 'Người duyệt', readonly=True)
    approved_on = fields.Datetime('Thời điểm duyệt', readonly=True)

    def _find(self, date):
        for v in self.filtered(lambda x: x.state == 'approved').sorted('date_from', reverse=True):
            if v.date_from <= date and (not v.date_to or v.date_to >= date):
                return v
        return self.browse()

    @api.constrains('date_from', 'date_to', 'state', 'param_id')
    def _check_overlap(self):
        for rec in self.filtered(lambda r: r.state == 'approved'):
            if rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_('Ngày kết thúc phải sau ngày bắt đầu.'))
            for other in rec.param_id.value_ids.filtered(lambda o: o.state == 'approved' and o.id != rec.id):
                a1, a2 = rec.date_from, rec.date_to or fields.Date.to_date('2999-12-31')
                b1, b2 = other.date_from, other.date_to or fields.Date.to_date('2999-12-31')
                if a1 <= b2 and b1 <= a2:
                    raise ValidationError(_('Tham số %s có 2 mức đã duyệt chồng thời gian áp dụng.') % rec.param_id.code)

    def write(self, vals):
        locked = {'value', 'date_from'}
        if not self.env.context.get('lfood_param_system') and locked & set(vals):
            if self.filtered(lambda v: v.state == 'approved'):
                raise UserError(_('Mức đã duyệt không sửa được giá trị. Hãy thêm mức mới với ngày áp dụng mới.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda v: v.state == 'approved'):
            raise UserError(_('Mức đã duyệt không xóa được, vì có thể đã dùng để tính số liệu.'))
        return super().unlink()

    def action_approve(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được duyệt tham số.'))
        for rec in self.filtered(lambda v: v.state == 'draft'):
            if not rec.legal_ref and rec.param_id.kind == 'law':
                raise UserError(_('Tham số theo luật phải ghi văn bản căn cứ trước khi duyệt.'))
            prev = rec.param_id.value_ids.filtered(
                lambda o: o.state == 'approved' and o.date_from < rec.date_from and (not o.date_to or o.date_to >= rec.date_from))
            prev.with_context(lfood_param_system=True).write({'date_to': rec.date_from - timedelta(days=1)})
            rec.with_context(lfood_param_system=True).write({
                'state': 'approved', 'approved_by': self.env.user.id, 'approved_on': fields.Datetime.now()})


class LfoodVatRate(models.Model):
    _name = 'lfood.vat.rate'
    _description = 'Thuế suất GTGT'
    _order = 'sequence, rate'

    name = fields.Char('Tên', required=True)
    rate = fields.Float('Thuế suất (%)', digits=(5, 2))
    date_from = fields.Date('Áp dụng từ')
    date_to = fields.Date('Áp dụng đến')
    legal_ref = fields.Char('Văn bản căn cứ')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    def _is_valid_on(self, date):
        self.ensure_one()
        return (not self.date_from or self.date_from <= date) and (not self.date_to or self.date_to >= date)
