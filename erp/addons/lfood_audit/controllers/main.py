import json
import logging

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.export import CSVExport, ExcelExport
from odoo.addons.web.controllers.session import Session

_logger = logging.getLogger(__name__)


def _log_on_own_cursor(uid, action, **kw):
    """Ghi nhật ký bằng kết nối riêng: vẫn còn dấu vết kể cả khi thao tác chính bị lỗi hoặc bị từ chối."""
    try:
        with request.env.registry.cursor() as cr:
            env = request.env(cr=cr, user=uid, su=True)
            user = env['res.users'].browse(uid)
            env['lfood.audit.log']._record_event(action, user=user, login=user.login, **kw)
    except Exception:
        _logger.exception('Không ghi được nhật ký %s', action)


def _export_info(data):
    params = json.loads(data)
    model = params.get('model')
    ids = params.get('ids') or []
    fields = [f.get('label') or f.get('name') for f in params.get('fields', [])]
    return model, ids, fields, params.get('domain') or []


def _export(controller_call, data, fmt):
    uid = request.session.uid
    model, ids, fields, domain = _export_info(data)
    changes = [{'field': 'fields', 'label': 'Cột xuất', 'old': None, 'new': fields[:40]},
               {'field': 'ids', 'label': 'Bản ghi', 'old': None, 'new': ids[:100]},
               {'field': 'domain', 'label': 'Điều kiện lọc', 'old': None, 'new': str(domain)[:300]}]
    try:
        response = controller_call(data)
    except Exception as exc:
        _log_on_own_cursor(uid, 'export', model=model, summary='Xuất dữ liệu %s ra %s BỊ TỪ CHỐI: %s' % (model, fmt, str(exc)[:150]),
                           changes=changes)
        raise
    count = len(ids) if ids else request.env[model].search_count(domain)
    _log_on_own_cursor(uid, 'export', model=model, res_id=ids[0] if len(ids) == 1 else False,
                       summary='Xuất %s bản ghi %s ra tệp %s' % (count, model, fmt), changes=changes)
    return response


class LfoodCSVExport(CSVExport):
    @http.route('/web/export/csv', type='http', auth='user')
    def web_export_csv(self, data):
        return _export(super().web_export_csv, data, 'CSV')


class LfoodExcelExport(ExcelExport):
    @http.route('/web/export/xlsx', type='http', auth='user')
    def web_export_xlsx(self, data):
        return _export(super().web_export_xlsx, data, 'Excel')


class LfoodSession(Session):
    @http.route('/web/session/logout', type='http', auth='none', readonly=False)
    def logout(self, redirect='/odoo'):
        uid = request.session.uid
        if uid and request.session.db:
            name = request.env(user=uid, su=True)['res.users'].browse(uid).name
            _log_on_own_cursor(uid, 'logout', model='res.users', res_id=uid, res_name=name, summary='Đăng xuất: %s' % name)
        return super().logout(redirect=redirect)
