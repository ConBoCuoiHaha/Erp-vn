from odoo import api, fields, models, _
from odoo.exceptions import UserError

# thứ tự ưu tiên khi xác định vai trò hiển thị (vai trò trên bao gồm quyền vai trò dưới)
ROLES = [
    ('sysadmin', 'Quản trị hệ thống', 'lfood_base.group_sysadmin'),
    ('director', 'Giám đốc', 'lfood_base.group_director'),
    ('chief', 'Kế toán trưởng', 'lfood_base.group_chief_accountant'),
    ('accountant', 'Kế toán viên', 'lfood_base.group_accountant'),
    ('rnd', 'R&D', 'lfood_base.group_rnd'),
    ('employee', 'Nhân viên', 'lfood_base.group_employee'),
]


class ResUsers(models.Model):
    _inherit = 'res.users'

    lfood_role = fields.Selection(
        [(k, label) for k, label, _g in ROLES] + [('none', 'Chưa phân quyền')],
        string='Vai trò LiFeOOD', compute='_compute_lfood_role', inverse='_inverse_lfood_role')
    lfood_audit_count = fields.Integer('Số thao tác đã ghi', compute='_compute_lfood_audit_count')

    @api.depends('group_ids', 'all_group_ids')
    def _compute_lfood_role(self):
        for user in self:
            user.lfood_role = 'none'
            for key, _label, xmlid in ROLES:
                if user.has_group(xmlid):
                    user.lfood_role = key
                    break

    def _inverse_lfood_role(self):
        groups = {key: self.env.ref(xmlid) for key, _l, xmlid in ROLES}
        all_ids = [g.id for g in groups.values()]
        for user in self:
            if user == self.env.user and user.lfood_role != 'sysadmin' and user.has_group('lfood_base.group_sysadmin'):
                others = self.env.ref('lfood_base.group_sysadmin').all_user_ids - user
                if not others.filtered('active'):
                    raise UserError(_('Không thể bỏ vai trò Quản trị của chính mình khi không còn quản trị viên nào khác.'))
            commands = [(3, gid) for gid in all_ids]
            if user.lfood_role != 'sysadmin':
                commands += [(3, self.env.ref('base.group_system').id), (3, self.env.ref('base.group_erp_manager').id)]
            if user.lfood_role and user.lfood_role != 'none':
                commands.append((4, groups[user.lfood_role].id))
            user.write({'group_ids': commands})

    def _compute_lfood_audit_count(self):
        Log = self.env['lfood.audit.log'].sudo()
        for user in self:
            user.lfood_audit_count = Log.search_count([('user_id', '=', user.id)]) if user.id else 0

    def action_lfood_view_audit(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Nhật ký của %s') % self.name, 'res_model': 'lfood.audit.log',
                'view_mode': 'list,form', 'domain': [('user_id', '=', self.id)]}

    def action_lfood_change_password(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('base.change_password_wizard_action')
        action['context'] = {'active_model': 'res.users', 'active_ids': self.ids, 'active_id': self.id}
        return action

    def unlink(self):
        if self.env.user in self:
            raise UserError(_('Không thể xóa tài khoản đang đăng nhập.'))
        used = self.filtered(lambda u: self.env['lfood.audit.log'].sudo().search_count([('user_id', '=', u.id)]))
        if used:
            raise UserError(_('Tài khoản %s đã có thao tác trong nhật ký nên không xóa được, để giữ dấu vết trách nhiệm. '
                              'Hãy bấm Ngừng hoạt động.') % ', '.join(used.mapped('login')))
        return super().unlink()
