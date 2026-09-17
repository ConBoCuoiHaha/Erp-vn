"""Lịch sử tham số và gói cập nhật (CH08).

Tra cứu: chọn một ngày, xem mức của mọi tham số áp dụng cho ngày đó và văn bản căn cứ.
Gói tham số: xuất toàn bộ tham số và các mức ra tệp JSON; nhập tệp ở bản khác (bản thử sang bản thật). Khi nhập, tham số
chưa có thì tạo mới, mức chưa có (cùng mã, ngày áp dụng, giá trị) thì thêm ở trạng thái Chờ duyệt; không mức nào được
duyệt tự động, Kế toán trưởng vẫn phải duyệt từng mức.
"""
import base64
import json

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import num

FORMAT = 'lfood-legal-params'


class LfoodParamTools(models.TransientModel):
    _name = 'lfood.param.tools'
    _description = 'Tra cứu và gói tham số pháp lý'

    date = fields.Date('Tra cứu tại ngày', default=fields.Date.context_today, required=True)
    history_html = fields.Html('Mức áp dụng', compute='_compute_history', sanitize=False)
    export_file = fields.Binary('Tệp gói tham số', readonly=True)
    export_name = fields.Char()
    import_file = fields.Binary('Tệp cần nhập')
    import_name = fields.Char()
    result = fields.Text('Kết quả nhập', readonly=True)

    @api.depends('date')
    def _compute_history(self):
        params = self.env['lfood.legal.param'].search([])
        for rec in self:
            rows = []
            for p in params:
                v = p.value_ids._find(rec.date)
                rows.append(Markup('<tr><td>%s</td><td>%s</td><td class="text-end">%s</td><td>%s</td><td>%s</td><td>%s</td></tr>') % (
                    p.code, p.name, num(v.value) if v else _('chưa có'),
                    v.date_from.strftime('%d/%m/%Y') if v else '', v.date_to.strftime('%d/%m/%Y') if v and v.date_to else '',
                    v.legal_ref or '' if v else ''))
            rec.history_html = Markup('<table class="table table-sm"><thead><tr><th>%s</th><th>%s</th><th>%s</th><th>%s</th>'
                                      '<th>%s</th><th>%s</th></tr></thead><tbody>%s</tbody></table>') % (
                _('Mã'), _('Tên'), _('Giá trị'), _('Từ'), _('Đến'), _('Căn cứ'), Markup('').join(rows))

    def action_export(self):
        self.ensure_one()
        data = {'format': FORMAT, 'version': 1, 'params': [{
            'code': p.code, 'name': p.name, 'group': p.group, 'value_type': p.value_type, 'kind': p.kind,
            'description': p.description or '',
            'values': [{'value': v.value, 'date_from': str(v.date_from), 'date_to': v.date_to and str(v.date_to) or None,
                        'legal_ref': v.legal_ref or '', 'note': v.note or '', 'state': v.state}
                       for v in p.value_ids.sorted('date_from')]}
            for p in self.env['lfood.legal.param'].search([])]}
        self.write({'export_file': base64.b64encode(json.dumps(data, ensure_ascii=False, indent=1).encode()),
                    'export_name': 'tham-so-phap-ly-%s.json' % fields.Date.context_today(self)})
        return self._reopen()

    def action_import(self):
        self.ensure_one()
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được nhập gói tham số.'))
        try:
            data = json.loads(base64.b64decode(self.import_file or b''))
            assert data.get('format') == FORMAT
            items = data['params']
        except Exception:
            raise UserError(_('Tệp không phải gói tham số pháp lý của app.'))
        Param = self.env['lfood.legal.param']
        new_params = new_values = 0
        for item in items:
            p = Param.search([('code', '=', item['code'])], limit=1)
            if not p:
                p = Param.create({k: item[k] for k in ('code', 'name', 'group', 'value_type', 'kind', 'description')})
                new_params += 1
            for v in item['values']:
                d = fields.Date.to_date(v['date_from'])
                if p.value_ids.filtered(lambda x: x.date_from == d and round(x.value - v['value'], 4) == 0):
                    continue
                p.value_ids.create({'param_id': p.id, 'value': v['value'], 'date_from': d,
                                    'date_to': v['date_to'] and fields.Date.to_date(v['date_to']),
                                    'legal_ref': v['legal_ref'], 'note': (v['note'] or _('Nhập từ gói %s') % (self.import_name or ''))[:200]})
                new_values += 1
        self.env['lfood.audit.log']._record_event(
            'state', model='lfood.legal.param', summary=_('Nhập gói tham số %s: %s tham số mới, %s mức chờ duyệt')
            % (self.import_name or '', new_params, new_values))
        self.result = _('Đã thêm %s tham số, %s mức ở trạng thái Chờ duyệt. Kế toán trưởng duyệt từng mức trong Tham số pháp lý.') % (
            new_params, new_values)
        return self._reopen()

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form',
                'target': 'new'}
