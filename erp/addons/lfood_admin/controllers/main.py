import io
import os
import zipfile

from odoo import http
from odoo.http import request, content_disposition

from odoo.addons.lfood_audit.controllers.main import _log_on_own_cursor


class LfoodBackupController(http.Controller):

    @http.route('/lfood/backup/<int:backup_id>/download', type='http', auth='user')
    def download(self, backup_id, **kw):
        uid = request.session.uid
        user = request.env.user
        backup = request.env['lfood.backup'].browse(backup_id).exists()
        if not user.has_group('lfood_base.group_sysadmin') or not backup:
            _log_on_own_cursor(uid, 'export', model='lfood.backup', res_id=backup_id,
                               summary='Tải bản sao lưu #%s BỊ TỪ CHỐI' % backup_id)
            return request.not_found()
        path = backup._path()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:
            for fname in sorted(os.listdir(path)):
                full = os.path.join(path, fname)
                if os.path.isfile(full):
                    zf.write(full, fname)
        filename = 'lfood-backup-%s.zip' % backup.name.replace('/', '-')
        _log_on_own_cursor(uid, 'export', model='lfood.backup', res_id=backup.id, res_name=backup.name,
                           summary='Tải về bản sao lưu %s (%s byte)' % (backup.name, buf.tell()))
        return request.make_response(buf.getvalue(), headers=[
            ('Content-Type', 'application/zip'), ('Content-Disposition', content_disposition(filename))])
