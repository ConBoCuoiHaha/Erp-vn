from odoo import models
from odoo.exceptions import AccessDenied


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _login(self, credential, user_agent_env):
        login = credential.get('login') if isinstance(credential, dict) else None
        try:
            auth_info = super()._login(credential, user_agent_env)
        except AccessDenied:
            # giao dịch hiện tại sẽ bị hủy -> ghi bằng kết nối riêng để không mất dấu
            with self.env.registry.cursor() as cr:
                env = self.env(cr=cr, su=True)
                user = env['res.users'].with_context(active_test=False).search([('login', '=', login)], limit=1)
                env['lfood.audit.log']._record_event(
                    'login_failed', model='res.users', res_id=user.id or False, res_name=login,
                    user=user or env['res.users'], login=login or '',
                    summary='Đăng nhập thất bại: %s' % (login or ''))
            raise
        uid = auth_info.get('uid') if isinstance(auth_info, dict) else None
        if uid:
            user = self.env['res.users'].sudo().browse(uid)
            self.env['lfood.audit.log']._record_event(
                'login', model='res.users', res_id=uid, res_name=user.name, user=user, login=user.login,
                company_id=user.company_id.id, summary='Đăng nhập: %s' % user.name)
        return auth_info
