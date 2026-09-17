from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LfoodCostItem(models.Model):
    _name = 'lfood.cost.item'
    _description = 'Khoản mục chi phí'
    _parent_store = True
    _parent_name = 'parent_id'
    _order = 'code'
    _rec_names_search = ['code', 'name']

    code = fields.Char('Mã số', required=True, index=True)
    name = fields.Char('Tên khoản mục', required=True)
    parent_id = fields.Many2one('lfood.cost.item', 'Khoản mục cha', index=True, ondelete='restrict')
    child_ids = fields.One2many('lfood.cost.item', 'parent_id', 'Khoản mục con')
    parent_path = fields.Char(index=True)
    level = fields.Integer('Cấp', compute='_compute_level', store=True)
    accounts = fields.Char('Tài khoản', help='Các tài khoản được dùng với khoản mục, ví dụ 6417,6427')
    company_id = fields.Many2one('res.company', 'Công ty', help='Để trống là dùng chung cho mọi công ty')
    active = fields.Boolean(default=True)

    @api.depends('parent_path')
    def _compute_level(self):
        for rec in self:
            rec.level = len([p for p in (rec.parent_path or '').split('/') if p]) or 1

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s %s' % (rec.code or '', rec.name or '')

    @api.constrains('parent_id')
    def _check_parent(self):
        if self._has_cycle():
            raise ValidationError(_('Không thể chọn chính khoản mục hoặc khoản mục con làm khoản mục cha.'))

    @api.constrains('code', 'company_id')
    def _check_code_unique(self):
        for rec in self:
            dup = self.search_count([('code', '=', rec.code), ('company_id', '=', rec.company_id.id), ('id', '!=', rec.id)])
            if dup:
                raise ValidationError(_('Mã số khoản mục %s đã tồn tại.') % rec.code)
