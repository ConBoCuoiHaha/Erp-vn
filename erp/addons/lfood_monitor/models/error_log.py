"""Sổ lỗi kỹ thuật: gom lỗi xảy ra trên trình duyệt của người dùng và cảnh báo sức khỏe hệ thống.

Khác Nhật ký hệ thống (ghi ai làm gì, không sửa được): đây là chỗ để người quản trị biết app đang hỏng ở đâu khi
người dùng thật đang dùng. Lỗi giống nhau gom thành một dòng và đếm số lần, tránh ngập màn hình.
Toàn bộ dữ liệu nằm trên máy này, không gửi đi dịch vụ ngoài nào.
"""
import hashlib
import logging
import os
import shutil
from datetime import datetime, timezone

from odoo import api, fields, models, _
from odoo.tools import config

_logger = logging.getLogger(__name__)

SOURCES = [('browser', 'Trình duyệt người dùng'), ('server', 'Máy chủ')]
STATES = [('new', 'Mới'), ('seen', 'Đã xem'), ('ignored', 'Bỏ qua')]
LOG_MAX_MB = 20  # nhật ký máy chủ vượt mức này thì xoay vòng
LOG_KEEP = 5


class LfoodErrorLog(models.Model):
    _name = 'lfood.error.log'
    _description = 'Lỗi kỹ thuật'
    _order = 'last_seen desc'

    source = fields.Selection(SOURCES, 'Nơi xảy ra', required=True, default='browser', index=True)
    message = fields.Char('Lỗi', required=True)
    detail = fields.Text('Chi tiết')
    url = fields.Char('Màn hình')
    user_id = fields.Many2one('res.users', 'Người gặp', index=True)
    browser = fields.Char('Trình duyệt')
    count = fields.Integer('Số lần', default=1)
    first_seen = fields.Datetime('Lần đầu', default=fields.Datetime.now)
    last_seen = fields.Datetime('Lần gần nhất', default=fields.Datetime.now, index=True)
    state = fields.Selection(STATES, 'Trạng thái', default='new', required=True, index=True)
    fingerprint = fields.Char('Mã gom nhóm', index=True)
    note = fields.Char('Ghi chú của người xử lý')

    @api.model
    def _record(self, source, message, detail=False, url=False, browser=False, user=None):
        """Ghi một lỗi, gom vào dòng cũ nếu trùng. Luôn dùng hàm này."""
        message = (message or _('Lỗi không rõ'))[:300]
        key = '%s|%s|%s' % (source, message, (detail or '').strip().splitlines()[-1][:200] if detail else '')
        finger = hashlib.sha1(key.encode()).hexdigest()
        now = fields.Datetime.now()
        existing = self.sudo().search([('fingerprint', '=', finger), ('state', '!=', 'ignored')], limit=1)
        if existing:
            existing.write({'count': existing.count + 1, 'last_seen': now, 'url': url or existing.url})
            return existing
        return self.sudo().create({
            'source': source, 'message': message, 'detail': detail, 'url': url, 'browser': browser,
            'user_id': (user or self.env.user).id, 'fingerprint': finger, 'first_seen': now, 'last_seen': now})

    def action_seen(self):
        return self.write({'state': 'seen'})

    def action_ignore(self):
        return self.write({'state': 'ignored'})

    def action_reopen(self):
        return self.write({'state': 'new'})

    # ------------------------------------------------------------ sức khỏe hệ thống
    @api.model
    def _log_path(self):
        return config.get('logfile') or ''

    @api.model
    def _rotate_log(self):
        """Nhật ký máy chủ quá lớn thì xoay vòng, giữ LOG_KEEP tệp. Odoo mở lại tệp mới nên không mất dòng nào."""
        path = self._log_path()
        if not path or not os.path.exists(path) or os.path.getsize(path) < LOG_MAX_MB * 1024 * 1024:
            return False
        for i in range(LOG_KEEP - 1, 0, -1):
            older, newer = '%s.%s' % (path, i + 1), '%s.%s' % (path, i)
            if os.path.exists(newer):
                os.replace(newer, older)
        os.replace(path, '%s.1' % path)
        return True

    @api.model
    def _last_backup(self):
        """Thời điểm bản sao lưu gần nhất, đọc thẳng trên đĩa để không phụ thuộc việc quản trị bấm Đồng bộ."""
        root = self.env['lfood.backup'].sudo()._root()
        newest = 0
        for base, _dirs, files in os.walk(root):
            if 'manifest.json' in files:
                newest = max(newest, os.path.getmtime(os.path.join(base, 'manifest.json')))
        if newest:
            return fields.Datetime.to_datetime(datetime.fromtimestamp(newest, timezone.utc).replace(tzinfo=None))
        last = self.env['lfood.backup'].sudo().search([], order='created desc', limit=1)
        return last.created or False

    @api.model
    def _health_problems(self):
        """[(mức, tiêu đề, chi tiết)] - dùng chung cho màn hình tình trạng và việc kiểm tra hằng ngày."""
        out = []
        last = self._last_backup()
        if not last:
            out.append(('bad', _('Chưa có bản sao lưu nào'),
                        _('Kiểm tra dịch vụ sao lưu trong Docker: docker compose logs backup.')))
        else:
            hours = (fields.Datetime.now() - last).total_seconds() / 3600
            if hours > 36:
                out.append(('bad', _('Sao lưu quá hạn %s giờ') % int(hours),
                            _('Bản gần nhất lúc %s.') % fields.Datetime.to_string(last)))
        seen = set()
        for label, path in ((_('thư mục dữ liệu'), config.get('data_dir') or '/var/lib/odoo'),
                            (_('thư mục sao lưu'), self.env['lfood.backup'].sudo()._root())):
            try:
                device = os.stat(path).st_dev
                usage = shutil.disk_usage(path)
            except OSError:
                continue
            if device in seen:  # hai thư mục trên cùng một ổ thì chỉ báo một lần
                continue
            seen.add(device)
            free_gb = usage.free / 1024 ** 3
            if free_gb < 5:
                out.append(('bad', _('Đĩa của %s sắp đầy: còn %.1f GB') % (label, free_gb),
                            _('Xóa bớt bản sao lưu cũ hoặc chuyển sang ổ khác.')))
        breaks, checked = self.env['lfood.audit.log'].sudo()._chain_breaks()
        if breaks:
            out.append(('bad', _('Nhật ký hệ thống có %s dòng sai lệch') % len(breaks),
                        _('Các dòng: %s. Báo ngay Giám đốc.') % ', '.join(str(b) for b in breaks[:20])))
        new_errors = self.sudo().search_count([('state', '=', 'new')])
        if new_errors:
            out.append(('warn', _('Có %s lỗi kỹ thuật chưa xem') % new_errors, _('Mở Quản trị > Lỗi kỹ thuật.')))
        return out

    @api.model
    def _daily_check(self):
        """Việc chạy hằng ngày: xoay nhật ký máy chủ và ghi lại các vấn đề sức khỏe thành dòng lỗi."""
        self._rotate_log()
        for level, title, detail in self._health_problems():
            if level == 'bad':
                self._record('server', title, detail, user=self.env.ref('base.user_root'))
                _logger.warning('Giám sát: %s - %s', title, detail)
        return True
