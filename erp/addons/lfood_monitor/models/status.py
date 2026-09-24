"""Hai màn hình chỉ để xem: tình trạng hệ thống và nhật ký máy chủ."""
import os
import shutil

from markupsafe import Markup, escape

from odoo import api, fields, models, release, _
from odoo.tools import config

LEVELS = [('all', 'Tất cả'), ('warning', 'Từ cảnh báo trở lên'), ('error', 'Chỉ lỗi')]
BADGE = {'ok': ('#1f7a3d', 'Bình thường'), 'warn': ('#8a6d00', 'Cần để ý'), 'bad': ('#9C0006', 'Có vấn đề')}


def _gb(value):
    return '%.1f GB' % (value / 1024 ** 3)


class LfoodSystemStatus(models.TransientModel):
    _name = 'lfood.system.status'
    _description = 'Tình trạng hệ thống'

    html = fields.Html('Tình trạng', compute='_compute_html', sanitize=False)

    def _rows(self):
        env = self.env
        cr = env.cr
        cr.execute('SELECT pg_database_size(current_database()), current_database()')
        size, dbname = cr.fetchone()
        cr.execute("SELECT date_trunc('second', now() - pg_postmaster_start_time())")
        db_uptime = cr.fetchone()[0]
        data_dir = config.get('data_dir') or '/var/lib/odoo'
        usage = shutil.disk_usage(data_dir)
        Err = env['lfood.error.log'].sudo()
        last = Err._last_backup()
        today = fields.Date.context_today(self)
        rows = [
            (_('Phiên bản'), '%s | %s' % (release.version, dbname)),
            (_('Máy chủ cơ sở dữ liệu chạy liên tục'), str(db_uptime)),
            (_('Dung lượng cơ sở dữ liệu'), _gb(size)),
            (_('Đĩa còn trống'), '%s / %s' % (_gb(usage.free), _gb(usage.total))),
            (_('Bản sao lưu gần nhất'), fields.Datetime.to_string(last) if last else _('chưa có')),
            (_('Lỗi kỹ thuật chưa xem'), str(Err.search_count([('state', '=', 'new')]))),
            (_('Lỗi trình duyệt hôm nay'), str(Err.search_count([('source', '=', 'browser'), ('last_seen', '>=', today)]))),
            (_('Lượt đăng nhập hôm nay'), str(env['lfood.audit.log'].sudo().search_count(
                [('action', '=', 'login'), ('event_time', '>=', today)]))),
            (_('Đăng nhập sai hôm nay'), str(env['lfood.audit.log'].sudo().search_count(
                [('action', '=', 'login_failed'), ('event_time', '>=', today)]))),
            (_('Nhật ký máy chủ'), self._log_info()),
        ]
        return rows

    def _log_info(self):
        path = self.env['lfood.error.log']._log_path()
        if not path:
            return _('chưa bật ghi ra tệp (đang ghi ra màn hình Docker)')
        if not os.path.exists(path):
            return _('%s - chưa có tệp') % path
        return '%s - %.1f MB' % (path, os.path.getsize(path) / 1024 ** 2)

    @api.depends_context('uid')
    def _compute_html(self):
        for rec in self:
            problems = rec.env['lfood.error.log']._health_problems()
            level = 'bad' if any(p[0] == 'bad' for p in problems) else ('warn' if problems else 'ok')
            color, label = BADGE[level]
            head = Markup('<p style="font-size:15px"><b style="color:%s">%s</b></p>') % (color, label)
            if problems:
                head += Markup('<ul>') + Markup('').join(
                    Markup('<li><b>%s</b> - %s</li>') % (escape(title), escape(detail)) for _lv, title, detail in problems
                ) + Markup('</ul>')
            body = Markup('').join(Markup('<tr><td>%s</td><td><b>%s</b></td></tr>') % (escape(k), escape(v))
                                   for k, v in rec._rows())
            rec.html = head + Markup('<div class="o_lfood_changes"><table>%s</table></div>') % body


class LfoodServerLog(models.TransientModel):
    _name = 'lfood.server.log'
    _description = 'Nhật ký máy chủ'

    lines = fields.Integer('Số dòng cuối', default=200, required=True)
    level = fields.Selection(LEVELS, 'Mức', default='warning', required=True)
    keyword = fields.Char('Chứa chữ')
    html = fields.Html('Nội dung', compute='_compute_html', sanitize=False)

    @api.depends('lines', 'level', 'keyword')
    def _compute_html(self):
        for rec in self:
            path = rec.env['lfood.error.log']._log_path()
            if not path or not os.path.exists(path):
                rec.html = Markup('<p>Chưa bật ghi nhật ký ra tệp. Thêm <code>logfile = /var/log/odoo/odoo.log</code> '
                                  'vào <code>erp/config/odoo.conf</code> rồi khởi động lại.</p>')
                continue
            wanted = ('ERROR', 'CRITICAL') if rec.level == 'error' else \
                     ('WARNING', 'ERROR', 'CRITICAL') if rec.level == 'warning' else ()
            out = []
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    if wanted and not any(' %s ' % w in line for w in wanted):
                        continue
                    if rec.keyword and rec.keyword.lower() not in line.lower():
                        continue
                    out.append(line.rstrip())
            out = out[-max(rec.lines, 1):]
            body = Markup('').join(
                Markup('<div style="color:%s">%s</div>') % ('#9C0006' if ' ERROR ' in l or ' CRITICAL ' in l else
                                                            '#8a6d00' if ' WARNING ' in l else '#333333', escape(l))
                for l in out)
            rec.html = Markup('<pre style="white-space:pre-wrap;font-size:12px">%s</pre>') % body \
                if out else Markup('<p>Không có dòng nào khớp.</p>')
