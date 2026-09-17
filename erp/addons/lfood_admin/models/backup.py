import hashlib
import json
import os
import shutil
from datetime import datetime, timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

KINDS = [('daily', 'Hằng ngày'), ('weekly', 'Hằng tuần'), ('monthly', 'Hằng tháng')]


def _fmt_size(n):
    n = float(n or 0)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return '%.1f %s' % (n, unit) if unit != 'B' else '%d B' % n
        n /= 1024


class LfoodBackup(models.Model):
    _name = 'lfood.backup'
    _description = 'Bản sao lưu dữ liệu'
    _order = 'created desc, kind'

    name = fields.Char('Thư mục', required=True, readonly=True)
    kind = fields.Selection(KINDS, 'Loại', readonly=True)
    created = fields.Datetime('Thời điểm sao lưu', readonly=True)
    reason = fields.Char('Lý do', readonly=True)
    size_bytes = fields.Float('Dung lượng (byte)', readonly=True)
    size_display = fields.Char('Dung lượng', compute='_compute_size_display')
    count_vouchers = fields.Integer('Số chứng từ', readonly=True)
    count_lines = fields.Integer('Số dòng chứng từ', readonly=True)
    count_audit = fields.Integer('Số dòng nhật ký', readonly=True)
    count_users = fields.Integer('Số người dùng', readonly=True)
    last_audit_hash = fields.Char('Mã băm nhật ký cuối', readonly=True)
    verify_state = fields.Selection([('unchecked', 'Chưa kiểm tra'), ('ok', 'Nguyên vẹn'), ('bad', 'Hỏng hoặc bị sửa')],
                                    'Kiểm tra tệp', default='unchecked', readonly=True)
    verify_time = fields.Datetime('Lần kiểm tra', readonly=True)
    verify_note = fields.Text('Kết quả kiểm tra', readonly=True)
    note = fields.Text('Ghi chú')

    _name_uniq = models.Constraint('unique(name)', 'Thư mục sao lưu đã có trong danh sách.')

    # ------------------------------------------------------------ đường dẫn
    @api.model
    def _root(self):
        return self.env['ir.config_parameter'].sudo().get_param('lfood.backup_dir', '/mnt/backups')

    def _path(self):
        self.ensure_one()
        root = os.path.realpath(self._root())
        path = os.path.realpath(os.path.join(root, self.name))
        if not path.startswith(root + os.sep):
            raise UserError(_('Đường dẫn sao lưu không hợp lệ.'))
        return path

    def _compute_size_display(self):
        for rec in self:
            rec.size_display = _fmt_size(rec.size_bytes)

    def _check_admin(self):
        if not self.env.user.has_group('lfood_base.group_sysadmin'):
            raise UserError(_('Chỉ Quản trị hệ thống được thao tác với bản sao lưu.'))

    # ------------------------------------------------------------ đồng bộ
    @api.model
    def action_sync(self):
        """Đọc các thư mục sao lưu trên đĩa, cập nhật danh sách."""
        self._check_admin()
        root = self._root()
        found = set()
        for kind, _label in KINDS:
            base = os.path.join(root, kind)
            if not os.path.isdir(base):
                continue
            for folder in sorted(os.listdir(base)):
                manifest = os.path.join(base, folder, 'manifest.json')
                if not os.path.isfile(manifest):
                    continue
                try:
                    with open(manifest, encoding='utf-8') as fh:
                        data = json.load(fh)
                except (OSError, ValueError):
                    continue
                name = '%s/%s' % (kind, folder)
                found.add(name)
                counts = data.get('counts') or {}
                created = False
                try:
                    created = datetime.fromisoformat(data.get('created'))
                    created = (created - created.utcoffset()).replace(tzinfo=None) if created.utcoffset() else created
                except (TypeError, ValueError):
                    pass
                vals = {
                    'kind': kind, 'created': created, 'reason': data.get('reason'),
                    'size_bytes': data.get('size_bytes') or 0,
                    'count_vouchers': counts.get('vouchers') or 0, 'count_lines': counts.get('voucher_lines') or 0,
                    'count_audit': counts.get('audit_logs') or 0, 'count_users': counts.get('users') or 0,
                    'last_audit_hash': counts.get('last_audit_hash'),
                }
                rec = self.search([('name', '=', name)], limit=1)
                if rec:
                    rec.with_context(lfood_audit_skip=True).write(vals)
                else:
                    self.with_context(lfood_audit_skip=True).create(dict(vals, name=name))
        self.search([('name', 'not in', list(found))]).with_context(lfood_audit_skip=True).unlink()
        return True

    @api.model
    def action_open_list(self):
        self.action_sync()
        action = self.env['ir.actions.act_window']._for_xml_id('lfood_admin.action_backup')
        return action

    # ------------------------------------------------------------ thao tác
    @api.model
    def action_request_now(self):
        self._check_admin()
        root = self._root()
        if not os.path.isdir(root):
            raise UserError(_('Không thấy thư mục sao lưu %s. Kiểm tra docker-compose.yml.') % root)
        with open(os.path.join(root, '.request'), 'w') as fh:
            fh.write('%s %s\n' % (fields.Datetime.now(), self.env.user.login))
        self.env['lfood.audit.log']._record_event(
            'other', model=self._name, summary=_('Yêu cầu sao lưu ngay'))
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Đã gửi yêu cầu sao lưu'), 'type': 'success', 'sticky': False,
            'message': _('Dịch vụ sao lưu sẽ chạy trong khoảng 20 giây. Bấm Làm mới sau 1 phút để thấy bản mới.')}}

    def action_verify(self):
        self._check_admin()
        for rec in self:
            path = rec._path()
            problems, checked = [], 0
            sums = os.path.join(path, 'SHA256SUMS')
            if not os.path.isfile(sums):
                problems.append(_('Thiếu tệp SHA256SUMS'))
            else:
                with open(sums, encoding='utf-8') as fh:
                    for line in fh:
                        parts = line.split()
                        if len(parts) != 2:
                            continue
                        expected, fname = parts
                        fpath = os.path.join(path, os.path.basename(fname))
                        if not os.path.isfile(fpath):
                            problems.append(_('Thiếu tệp %s') % fname)
                            continue
                        digest = hashlib.sha256()
                        with open(fpath, 'rb') as data:
                            for chunk in iter(lambda: data.read(1 << 20), b''):
                                digest.update(chunk)
                        checked += 1
                        if digest.hexdigest() != expected:
                            problems.append(_('Tệp %s không khớp mã băm') % fname)
            ok = not problems and checked >= 2
            rec.with_context(lfood_audit_skip=True).write({
                'verify_state': 'ok' if ok else 'bad', 'verify_time': fields.Datetime.now(),
                'verify_note': _('Đã kiểm tra %s tệp, tất cả khớp mã băm.') % checked if ok else '\n'.join(problems or [_('Không đủ tệp')]),
            })
            self.env['lfood.audit.log']._record_event(
                'other', model=rec._name, res_id=rec.id, res_name=rec.name,
                summary=_('Kiểm tra bản sao lưu: %s') % ('nguyên vẹn' if ok else 'LỖI'))
        return True

    def action_download(self):
        self.ensure_one()
        self._check_admin()
        return {'type': 'ir.actions.act_url', 'target': 'self', 'url': '/lfood/backup/%s/download' % self.id}

    def unlink(self):
        if self.env.context.get('lfood_audit_skip'):
            return super().unlink()
        self._check_admin()
        daily = self.search([('kind', '=', 'daily')], order='created desc', limit=1)
        if daily & self:
            raise UserError(_('Không xóa được bản sao lưu hằng ngày mới nhất.'))
        for rec in self:
            path = rec._path()
            if os.path.isdir(path):
                shutil.rmtree(path)
            self.env['lfood.audit.log']._record_event(
                'unlink', model=rec._name, res_id=rec.id, res_name=rec.name,
                summary=_('Xóa bản sao lưu %s') % rec.name)
        return super(LfoodBackup, self.with_context(lfood_audit_skip=True)).unlink()


class LfoodBackupStatus(models.TransientModel):
    _name = 'lfood.backup.status'
    _description = 'Tình trạng sao lưu'

    html = fields.Html('Tình trạng', compute='_compute_html', sanitize=False)

    def _compute_html(self):
        Backup = self.env['lfood.backup']
        root = Backup._root()
        status = {}
        try:
            with open(os.path.join(root, 'status.json'), encoding='utf-8') as fh:
                status = json.load(fh)
        except (OSError, ValueError):
            pass
        ICP = self.env['ir.config_parameter'].sudo()
        rows, warn = [], None
        last_time = status.get('time')
        if not status:
            warn = _('Chưa có thông tin từ dịch vụ sao lưu. Kiểm tra container backup đang chạy.')
        else:
            try:
                t = datetime.fromisoformat(last_time)
                age = datetime.now(t.tzinfo) - t
                if status.get('result') != 'ok':
                    warn = _('Lần sao lưu gần nhất bị lỗi: %s') % status.get('message')
                elif age > timedelta(hours=26):
                    warn = _('Bản sao lưu gần nhất đã quá 26 giờ. Máy có thể đã tắt hoặc dịch vụ sao lưu dừng.')
            except (TypeError, ValueError):
                warn = _('Không đọc được thời điểm sao lưu.')
        rows = [
            (_('Lần chạy gần nhất'), last_time or '—'),
            (_('Kết quả'), status.get('message') or '—'),
            (_('Bản gần nhất'), status.get('folder') or '—'),
            (_('Lịch tự động'), _('Hằng ngày lúc %s; nếu máy tắt đúng giờ thì chạy bù khi bật lại (bản gần nhất quá 24 giờ)') % (status.get('times') or '12:00,17:30')),
            (_('Giữ lại'), _('14 bản hằng ngày, 8 bản hằng tuần (thứ Hai), 12 bản hằng tháng (ngày 1)')),
            (_('Nơi lưu trong máy'), ICP.get_param('lfood.backup_host_dir', 'C:\\Users\\ADMIN\\ERP-Backup')),
            (_('Bản sao ngoài máy'), ICP.get_param('lfood.backup_offsite_note', 'Chưa bật (cần đồng ý trước khi gửi dữ liệu lên OneDrive/đám mây)')),
            (_('Nội dung mỗi bản'), _('database.dump (toàn bộ CSDL), filestore.tar.gz (tệp đính kèm), SHA256SUMS, manifest.json')),
        ]
        body = Markup('').join(Markup('<tr><th style="width:220px">%s</th><td>%s</td></tr>') % (escape(k), escape(v)) for k, v in rows)
        banner = Markup('<div class="alert alert-warning" role="alert">%s</div>') % warn if warn else \
            Markup('<div class="alert alert-success" role="alert">%s</div>') % _('Sao lưu đang hoạt động bình thường.')
        for rec in self:
            rec.html = banner + Markup('<div class="o_lfood_changes"><table>%s</table></div>') % body

    def action_request_now(self):
        return self.env['lfood.backup'].action_request_now()

    def action_open_list(self):
        return self.env['lfood.backup'].action_open_list()
