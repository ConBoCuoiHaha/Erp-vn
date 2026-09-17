from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class LfoodAccount(models.Model):
    _name = 'lfood.account'
    _description = 'Tài khoản kế toán'
    _order = 'code'
    _rec_names_search = ['code', 'name']
    _parent_store = True

    code = fields.Char('Số hiệu', required=True, index=True)
    name = fields.Char('Tên tài khoản', required=True)
    parent_id = fields.Many2one('lfood.account', 'Tài khoản cha', index=True, ondelete='restrict')
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('lfood.account', 'parent_id', 'Tài khoản con')
    level = fields.Integer('Cấp', compute='_compute_level', store=True, recursive=True)
    nature = fields.Selection([('debit', 'Dư Nợ'), ('credit', 'Dư Có'), ('both', 'Lưỡng tính')], 'Tính chất',
                              required=True, default='debit')
    is_official = fields.Boolean('Theo Thông tư 99', help='Bỏ chọn là tài khoản chi tiết do công ty tự mở')
    allow_posting = fields.Boolean('Được hạch toán', compute='_compute_allow_posting', store=True,
                                   help='Chỉ tài khoản không có tài khoản con mới được ghi sổ')
    track_partner = fields.Boolean('Theo dõi đối tượng', compute='_compute_track_partner', store=True, readonly=False)
    bs_term = fields.Selection([('short', 'Ngắn hạn'), ('long', 'Dài hạn'), ('equivalent', 'Tương đương tiền')],
                               'Kỳ hạn trên B01', required=True, default='short',
                               help='Khoản dài hạn (trên 12 tháng) mở tài khoản chi tiết riêng và chọn Dài hạn, ví dụ 33112 phải trả người bán dài hạn')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique(code)', 'Số hiệu tài khoản đã tồn tại.')

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s %s' % (rec.code, rec.name) if rec.code else rec.name

    @api.depends('parent_id.level')
    def _compute_level(self):
        for rec in self:
            rec.level = (rec.parent_id.level or 0) + 1 if rec.parent_id else 1

    @api.depends('child_ids')
    def _compute_allow_posting(self):
        for rec in self:
            rec.allow_posting = not rec.child_ids

    @api.depends('code')
    def _compute_track_partner(self):
        for rec in self:
            code = rec.code or ''
            # 1381, 1383, 3381-3387 (tài sản thiếu, thừa, bảo hiểm, công đoàn...) không theo đối tượng
            rec.track_partner = code[:3] in ('131', '136', '141', '331', '334', '336') or code[:4] in ('1388', '3388')

    @api.constrains('code', 'parent_id')
    def _check_code(self):
        for rec in self:
            if not rec.code.isdigit() or len(rec.code) < 3:
                raise ValidationError(_('Số hiệu tài khoản phải là chữ số, ít nhất 3 số.'))
            if rec.parent_id and not rec.code.startswith(rec.parent_id.code):
                raise ValidationError(_('Tài khoản %s phải bắt đầu bằng số hiệu tài khoản cha %s.') % (rec.code, rec.parent_id.code))
            if rec._has_cycle():
                raise ValidationError(_('Tài khoản cha bị vòng lặp.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('parent_id') and vals.get('code'):
                code = vals['code']
                for k in range(len(code) - 1, 2, -1):
                    parent = self.search([('code', '=', code[:k])], limit=1)
                    if parent:
                        vals['parent_id'] = parent.id
                        break
        accounts = super().create(vals_list)
        used = self.env['lfood.move.line'].sudo().search([('account_id', 'in', accounts.parent_id.ids)], limit=1)
        if used:
            raise UserError(_('Tài khoản %s đã có số phát sinh, không mở thêm tài khoản con được.') % used.account_id.code)
        return accounts

    def unlink(self):
        if self.env['lfood.move.line'].sudo().search_count([('account_id', 'in', self.ids)]):
            raise UserError(_('Tài khoản đã có số phát sinh không xóa được, hãy bỏ chọn Đang dùng.'))
        return super().unlink()

    @api.model
    def by_code(self, code, company=None):
        """Tìm tài khoản hạch toán theo số hiệu; báo lỗi rõ ràng nếu sai."""
        code = (code or '').strip()
        acc = self.sudo().search([('code', '=', code)], limit=1)
        if not acc:
            raise UserError(_('Tài khoản %s chưa có trong hệ thống tài khoản. Vào Sổ kế toán > Hệ thống tài khoản để mở.') % code)
        if not acc.allow_posting:
            raise UserError(_('Tài khoản %s có tài khoản con, phải hạch toán vào tài khoản chi tiết: %s')
                            % (code, ', '.join(acc.child_ids.mapped('code'))))
        if not acc.active:
            raise UserError(_('Tài khoản %s đã ngừng sử dụng.') % code)
        return acc
