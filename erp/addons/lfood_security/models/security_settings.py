"""Cấu hình đăng nhập an toàn (HT03).

Dùng cơ chế có sẵn của Odoo Community: khóa tạm sau nhiều lần đăng nhập sai (base.login_cooldown_*), hết phiên khi
không thao tác (sessions.max_inactivity_seconds), độ dài mật khẩu (auth_password_policy), mã xác thực 2 lớp (auth_totp,
mỗi người tự bật trong hồ sơ của mình).
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

PARAMS = {
    'cooldown_after': ('base.login_cooldown_after', 5),
    'cooldown_minutes': ('base.login_cooldown_duration', 900),
    'inactivity_minutes': ('sessions.max_inactivity_seconds', 1800),
    'password_minlength': ('auth_password_policy.minlength', 10),
}
SECONDS = {'cooldown_minutes', 'inactivity_minutes'}


class LfoodSecuritySettings(models.TransientModel):
    _name = 'lfood.security.settings'
    _description = 'Cấu hình đăng nhập an toàn'

    cooldown_after = fields.Integer('Khóa tạm sau số lần đăng nhập sai liên tiếp')
    cooldown_minutes = fields.Integer('Thời gian khóa tạm (phút)')
    inactivity_minutes = fields.Integer('Tự đăng xuất khi không thao tác (phút)')
    password_minlength = fields.Integer('Độ dài mật khẩu tối thiểu')
    no_totp_html = fields.Html('Người dùng chưa bật mã xác thực 2 lớp', compute='_compute_no_totp', sanitize=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ICP = self.env['ir.config_parameter'].sudo()
        for name, (key, default) in PARAMS.items():
            value = int(ICP.get_param(key, default))
            res[name] = value // 60 if name in SECONDS else value
        return res

    def _compute_no_totp(self):
        users = self.env['res.users'].sudo().search([('share', '=', False), ('active', '=', True)])
        missing = users.filtered(lambda u: not u.totp_enabled)
        rows = ''.join('<li>%s (%s)</li>' % (u.name, u.login) for u in missing)
        for rec in self:
            rec.no_totp_html = ('<ul>%s</ul>' % rows) if rows else _('<p>Mọi người dùng đã bật mã xác thực 2 lớp.</p>')

    def action_apply(self):
        self.ensure_one()
        if self.cooldown_after < 0 or self.cooldown_minutes < 1 or self.inactivity_minutes < 5 or self.password_minlength < 8:
            raise UserError(_('Khóa tạm từ 1 phút, tự đăng xuất từ 5 phút, mật khẩu tối thiểu 8 ký tự.'))
        ICP = self.env['ir.config_parameter'].sudo()
        changes = []
        for name, (key, default) in PARAMS.items():
            value = self[name] * 60 if name in SECONDS else self[name]
            old = ICP.get_param(key, default)
            if str(old) != str(value):
                ICP.set_param(key, str(value))
                changes.append('%s: %s -> %s' % (self._fields[name].string, old, value))
        if changes:
            self.env['lfood.audit.log']._record_event('config', summary=_('Đổi cấu hình đăng nhập: %s') % '; '.join(changes))
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'message': _('Đã lưu cấu hình đăng nhập.'), 'type': 'success'}}
