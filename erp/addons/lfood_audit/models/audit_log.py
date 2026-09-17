import hashlib
import json
import logging

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

# khóa dùng để xếp hàng khi ghi nhật ký, giữ chuỗi mã băm đúng thứ tự
_CHAIN_LOCK = 842617

ACTIONS = [
    ('login', 'Đăng nhập'),
    ('login_failed', 'Đăng nhập thất bại'),
    ('logout', 'Đăng xuất'),
    ('create', 'Tạo mới'),
    ('write', 'Sửa'),
    ('unlink', 'Xóa'),
    ('view', 'Mở xem'),
    ('export', 'Xuất dữ liệu'),
    ('print', 'In, xuất báo cáo'),
    ('state', 'Đổi trạng thái'),
    ('bulk', 'Điều chỉnh hàng loạt'),
    ('permission', 'Đổi phân quyền'),
    ('config', 'Đổi cấu hình'),
    ('other', 'Khác'),
]


class LfoodAuditLog(models.Model):
    _name = 'lfood.audit.log'
    _description = 'Nhật ký hệ thống'
    _order = 'id desc'
    _log_access = False
    _rec_name = 'summary'

    event_time = fields.Datetime('Thời điểm', readonly=True, index=True)
    user_id = fields.Many2one('res.users', 'Người thực hiện', readonly=True, index=True, ondelete='restrict')
    login = fields.Char('Tên đăng nhập', readonly=True)
    action = fields.Selection(ACTIONS, 'Hành động', readonly=True, index=True)
    model = fields.Char('Đối tượng (kỹ thuật)', readonly=True, index=True)
    model_name = fields.Char('Đối tượng', readonly=True)
    res_id = fields.Integer('Mã bản ghi', readonly=True, index=True)
    res_name = fields.Char('Bản ghi', readonly=True)
    company_id = fields.Many2one('res.company', 'Công ty', readonly=True)
    summary = fields.Char('Nội dung', readonly=True)
    changes = fields.Json('Chi tiết thay đổi', readonly=True)
    changes_html = fields.Html('Chi tiết', compute='_compute_changes_html', sanitize=False)
    ip = fields.Char('Địa chỉ IP', readonly=True)
    user_agent = fields.Char('Trình duyệt', readonly=True)
    session_ref = fields.Char('Phiên', readonly=True)
    prev_hash = fields.Char('Mã băm trước', readonly=True)
    hash = fields.Char('Mã băm', readonly=True, index=True)

    # ------------------------------------------------------------------ khóa
    def init(self):
        # Chặn sửa, xóa ở tầng cơ sở dữ liệu - kể cả khi gọi thẳng SQL qua Odoo
        self.env.cr.execute("""
            CREATE OR REPLACE FUNCTION lfood_audit_block() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Nhật ký hệ thống không được sửa hoặc xóa';
            END; $$ LANGUAGE plpgsql;
            DROP TRIGGER IF EXISTS lfood_audit_block_row ON lfood_audit_log;
            CREATE TRIGGER lfood_audit_block_row BEFORE UPDATE OR DELETE ON lfood_audit_log
                FOR EACH ROW EXECUTE FUNCTION lfood_audit_block();
            DROP TRIGGER IF EXISTS lfood_audit_block_truncate ON lfood_audit_log;
            CREATE TRIGGER lfood_audit_block_truncate BEFORE TRUNCATE ON lfood_audit_log
                FOR EACH STATEMENT EXECUTE FUNCTION lfood_audit_block();
        """)

    def write(self, vals):
        raise UserError(_('Nhật ký hệ thống không được sửa.'))

    def unlink(self):
        raise UserError(_('Nhật ký hệ thống không được xóa.'))

    # ------------------------------------------------------------------ hiển thị
    @api.depends('changes')
    def _compute_changes_html(self):
        for rec in self:
            rows = rec.changes if isinstance(rec.changes, list) else []
            if not rows:
                rec.changes_html = False
                continue
            body = Markup('').join(
                Markup('<tr><td>%s</td><td>%s</td><td>%s</td></tr>') % (
                    escape(r.get('label') or r.get('field') or ''),
                    escape(_fmt(r.get('old'))), escape(_fmt(r.get('new'))))
                for r in rows)
            rec.changes_html = Markup(
                '<div class="o_lfood_changes"><table><thead><tr><th>Trường</th>'
                '<th>Giá trị cũ</th><th>Giá trị mới</th></tr></thead><tbody>%s</tbody></table></div>') % body

    # ------------------------------------------------------------------ ghi
    @api.model
    def _hash_payload(self, prev, vals):
        payload = json.dumps({
            'prev': prev or '',
            't': str(vals.get('event_time') or ''),
            'u': vals.get('user_id') or 0,
            'l': vals.get('login') or '',
            'a': vals.get('action') or '',
            'm': vals.get('model') or '',
            'r': vals.get('res_id') or 0,
            's': vals.get('summary') or '',
            'c': vals.get('changes') or [],
            'ip': vals.get('ip') or '',
        }, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    @api.model
    def _request_info(self):
        info = {'ip': False, 'user_agent': False, 'session_ref': False}
        try:
            if request and request.httprequest:
                info['ip'] = request.httprequest.remote_addr
                info['user_agent'] = (request.httprequest.user_agent.string or '')[:250]
                sid = getattr(request.session, 'sid', '') or ''
                info['session_ref'] = hashlib.sha1(sid.encode()).hexdigest()[:12] if sid else False
        except RuntimeError:
            pass
        return info

    @api.model
    def _record_event(self, action, model=False, res_id=False, res_name=False, summary=False,
                      changes=None, user=None, login=None, company_id=None):
        """Ghi 1 dòng nhật ký. Luôn dùng hàm này, không tạo trực tiếp."""
        env = self.env
        user = user or env.user
        vals = {
            'event_time': fields.Datetime.now(),
            'user_id': user.id if user else False,
            'login': login if login is not None else (user.login if user else False),
            'action': action,
            'model': model or False,
            'model_name': (env['ir.model']._get(model).name if model and model in env else model) or False,
            'res_id': res_id or False,
            'res_name': (res_name or '')[:250] or False,
            'company_id': company_id or (env.company.id if env.company else False),
            'summary': (summary or '')[:500] or False,
            'changes': changes or False,
        }
        vals.update(self._request_info())
        cr = env.cr
        cr.execute('SELECT pg_advisory_xact_lock(%s)', (_CHAIN_LOCK,))
        cr.execute('SELECT hash FROM lfood_audit_log ORDER BY id DESC LIMIT 1')
        row = cr.fetchone()
        vals['prev_hash'] = row[0] if row else False
        vals['hash'] = self._hash_payload(vals['prev_hash'], vals)
        return super(LfoodAuditLog, self.sudo().with_context(lfood_audit_skip=True)).create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        raise UserError(_('Nhật ký chỉ do hệ thống ghi.'))

    # ------------------------------------------------------------------ kiểm tra toàn vẹn
    def action_verify_chain(self):
        cr = self.env.cr
        cr.execute("""SELECT id, event_time, user_id, login, action, model, res_id, summary, changes, ip, prev_hash, hash
                      FROM lfood_audit_log ORDER BY id""")
        prev = False
        checked = 0
        for (rid, t, u, l, a, m, r, s, c, ip, ph, h) in cr.fetchall():
            vals = {'event_time': fields.Datetime.to_string(t) if t else '', 'user_id': u, 'login': l,
                    'action': a, 'model': m, 'res_id': r, 'summary': s, 'changes': c or [], 'ip': ip}
            expect = self._hash_payload(prev, vals)
            if (ph or False) != (prev or False) or h != expect:
                self._record_event('other', summary=_('Kiểm tra toàn vẹn nhật ký: PHÁT HIỆN SAI LỆCH tại dòng %s') % rid)
                return _notify(_('Phát hiện nhật ký bị can thiệp tại dòng %s. Báo ngay Giám đốc.') % rid, 'danger')
            prev = h
            checked += 1
        self._record_event('other', summary=_('Kiểm tra toàn vẹn nhật ký: %s dòng, không sai lệch') % checked)
        return _notify(_('Đã kiểm tra %s dòng nhật ký: không có dòng nào bị sửa hoặc xóa.') % checked, 'success')


def _fmt(v):
    if v is None or v is False:
        return ''
    if isinstance(v, (list, tuple)):
        return ', '.join(str(x) for x in v)
    return str(v)


def _notify(message, kind):
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {'title': 'Nhật ký hệ thống', 'message': message, 'type': kind, 'sticky': kind != 'success'},
    }
