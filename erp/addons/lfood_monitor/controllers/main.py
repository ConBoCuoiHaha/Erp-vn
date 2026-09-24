"""Nhận lỗi JavaScript từ trình duyệt của người dùng. Không gửi đi đâu khác, chỉ ghi vào cơ sở dữ liệu này."""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class LfoodMonitor(http.Controller):

    @http.route('/lfood/monitor/js', type='http', auth='user', methods=['POST'], csrf=False, save_session=False)
    def js_error(self, message='', detail='', url='', **kw):
        try:
            request.env['lfood.error.log'].sudo()._record(
                'browser', message, detail=detail[:4000], url=url[:500],
                browser=(request.httprequest.headers.get('User-Agent') or '')[:200], user=request.env.user)
        except Exception:
            _logger.exception('Không ghi được lỗi trình duyệt')
        return request.make_response('', headers=[('Content-Type', 'text/plain')])
