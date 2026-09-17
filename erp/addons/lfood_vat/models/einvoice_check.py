"""Đối chiếu hóa đơn trong sổ với dữ liệu hóa đơn điện tử của cơ quan thuế (THUE04).

Kế toán tải bảng kê hóa đơn mua vào hoặc bán ra trên cổng hoadondientu.gdt.gov.vn (Excel), hoặc lưu thành CSV, rồi
nhập vào đây. App tìm dòng tiêu đề có "Số hóa đơn", nhận cột theo tên (ký hiệu, số, ngày lập, mã số thuế người bán
hoặc người mua, tổng tiền chưa thuế, tổng tiền thuế, trạng thái), nên không phụ thuộc thứ tự cột.
Hóa đơn trong sổ lấy đúng nguồn của bảng kê tờ khai 01/GTGT cùng kỳ. Khóa so khớp: mã số thuế đối tác + số hóa đơn.
Kết quả: khớp; lệch tiền; có trong sổ mà không có trên cổng (không được khấu trừ nếu hóa đơn không tồn tại);
có trên cổng mà sổ chưa ghi; hóa đơn đã hủy, bị thay thế trên cổng mà sổ vẫn ghi.
"""
import base64
import csv
import io
import re
from datetime import datetime

from odoo import fields, models, _
from odoo.exceptions import UserError

RESULTS = [('match', 'Khớp'), ('diff', 'Lệch tiền'), ('book_only', 'Sổ có, cổng thuế không có'),
           ('portal_only', 'Cổng thuế có, sổ chưa ghi'), ('cancelled', 'Hóa đơn đã hủy, bị thay thế')]
BAD_STATUS = ('hủy', 'bị thay thế', 'huỷ')


def norm_vat(v):
    return re.sub(r'[^0-9-]', '', str(v or '')).strip('-')


def invoice_no(v):
    """Số hóa đơn: nhóm chữ số cuối cùng, bỏ số 0 đầu ('C26TAA 0000123' -> 123)."""
    if isinstance(v, float):
        v = int(v)
    groups = re.findall(r'\d+', str(v or ''))
    return int(groups[-1]) if groups else None


def to_number(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or '').strip().replace(' ', '')
    if not s:
        return 0.0
    if re.fullmatch(r'-?[\d.]+,\d{1,2}', s) or re.fullmatch(r'-?\d{1,3}(\.\d{3})+', s):
        s = s.replace('.', '').replace(',', '.')  # kiểu Việt Nam 1.234.567,5
    else:
        s = s.replace(',', '')
    return float(s)


def to_date(v):
    if isinstance(v, datetime):
        return v.date()
    if hasattr(v, 'year'):
        return v
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(str(v).strip()[:10], fmt).date()
        except ValueError:
            continue
    return None


def map_columns(rows, kind):
    """Tìm dòng tiêu đề và vị trí cột. Tiêu đề 2 tầng (Thông tin người bán / MST) thì ghép với dòng dưới."""
    for i, row in enumerate(rows[:20]):
        cells = [str(c or '').strip().lower() for c in row]
        num_col = next((j for j, c in enumerate(cells) if c.startswith('số hóa đơn')), None)
        if num_col is None:
            continue
        below = [str(c or '').strip().lower() for c in rows[i + 1]] if i + 1 < len(rows) else []
        # tiêu đề 2 tầng: dòng dưới không có số hóa đơn
        two_tier = bool(below) and not invoice_no(below[num_col] if num_col < len(below) else '')
        heads = [(c + ' ' + below[j]).strip() if two_tier and j < len(below) else c for j, c in enumerate(cells)]
        side = 'bán' if kind == 'in' else 'mua'
        col = {}
        for j, h in enumerate(heads):
            if 'ký hiệu hóa đơn' in h:
                col.setdefault('symbol', j)
            elif h.startswith('số hóa đơn'):
                col.setdefault('number', j)
            elif 'ngày lập' in h:
                col.setdefault('date', j)
            elif 'mst' in h or 'mã số thuế' in h:
                if side in h:
                    col['vat'] = j
                else:
                    col.setdefault('vat_any', j)
            elif 'chưa thuế' in h or 'chưa có thuế' in h:
                col.setdefault('base', j)
            elif 'tiền thuế' in h:
                col.setdefault('tax', j)
            elif 'trạng thái' in h:
                col.setdefault('status', j)
        col.setdefault('vat', col.pop('vat_any', None))
        missing = [k for k in ('number', 'vat', 'base', 'tax') if col.get(k) is None]
        if missing:
            raise UserError(_('Không nhận được cột %s trong tệp.') % ', '.join(missing))
        return col, i + (2 if two_tier else 1)
    raise UserError(_('Không tìm thấy dòng tiêu đề có cột "Số hóa đơn".'))


class LfoodEinvoiceCheck(models.Model):
    _name = 'lfood.einvoice.check'
    _description = 'Đối chiếu hóa đơn với cơ quan thuế'
    _order = 'date_to desc, id desc'

    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    kind = fields.Selection([('in', 'Hóa đơn mua vào'), ('out', 'Hóa đơn bán ra')], 'Loại', required=True, default='in')
    date_from = fields.Date('Từ ngày', required=True)
    date_to = fields.Date('Đến ngày', required=True)
    import_file = fields.Binary('Bảng kê tải từ cổng thuế (xlsx, csv)', attachment=True, required=True)
    import_name = fields.Char()
    line_ids = fields.One2many('lfood.einvoice.check.line', 'check_id', 'Kết quả')
    summary = fields.Char('Tóm tắt', readonly=True)
    checked_on = fields.Datetime('Lúc đối chiếu', readonly=True)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('Đối chiếu %s %s - %s') % (
                dict(self._fields['kind'].selection)[rec.kind].lower(), rec.date_from or '', rec.date_to or '')

    def _read_rows(self):
        raw = base64.b64decode(self.import_file)
        if raw[:2] == b'PK':
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            return [list(r) for r in wb.active.iter_rows(values_only=True)]
        text = raw.decode('utf-8-sig')
        delimiter = max(';,\t', key=text[:4096].count)
        return list(csv.reader(io.StringIO(text), delimiter=delimiter))

    def _portal_invoices(self):
        rows = self._read_rows()
        col, start = map_columns(rows, self.kind)
        get = lambda row, k: row[col[k]] if col.get(k) is not None and col[k] < len(row) else None
        out = {}
        for row in rows[start:]:
            no, vat = invoice_no(get(row, 'number')), norm_vat(get(row, 'vat'))
            if not no or not vat:
                continue
            d = to_date(get(row, 'date'))
            if d and not self.date_from <= d <= self.date_to:
                continue
            key = (vat, no)
            item = out.setdefault(key, {'base': 0, 'tax': 0, 'date': d, 'status': '',
                                        'ref': ('%s %s' % (get(row, 'symbol') or '', get(row, 'number'))).strip()})
            item['base'] += to_number(get(row, 'base'))
            item['tax'] += to_number(get(row, 'tax'))
            item['status'] = str(get(row, 'status') or '')
        return out

    def _book_invoices(self):
        probe = self.env['lfood.vat.return'].sudo().new({
            'company_id': self.company_id.id, 'period_type': 'month', 'year': self.date_from.year,
            'month': self.date_from.month})
        # tờ khai tạm theo đúng khoảng ngày đối chiếu
        probe.date_from, probe.date_to = self.date_from, self.date_to
        lines = probe._purchase_lines() if self.kind == 'in' else probe._sale_lines()
        no_invoice = _('Chưa có hóa đơn GTGT hợp pháp')
        out = {}
        for v in lines:
            if v.get('reason') == no_invoice or v.get('source_model') == 'lfood.move':
                continue  # chứng từ không có hóa đơn, bút toán tổng hợp
            partner = self.env['res.partner'].browse(v['partner_id']) if v.get('partner_id') else None
            no = invoice_no(v.get('ref'))
            if not no:
                continue
            key = (norm_vat(partner.vat if partner else ''), no)
            item = out.setdefault(key, {'base': 0, 'tax': 0, 'date': v['date'], 'ref': v.get('ref'),
                                        'partner_id': partner.id if partner else False,
                                        'source_model': v.get('source_model'), 'source_id': v.get('source_id')})
            item['base'] += v['base']
            item['tax'] += v['tax']
        return out

    def action_check(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được đối chiếu hóa đơn.'))
        Partner = self.env['res.partner']
        for rec in self:
            portal, book = rec._portal_invoices(), rec._book_invoices()
            rec.line_ids.unlink()
            vals = []
            for key in sorted(set(portal) | set(book), key=lambda k: (k[0], k[1])):
                p, b = portal.get(key), book.get(key)
                if p and b:
                    if any(s in p['status'].lower() for s in BAD_STATUS):
                        result = 'cancelled'
                    elif abs(abs(p['base']) - abs(b['base'])) >= 1 or abs(abs(p['tax']) - abs(b['tax'])) >= 1:  # hóa đơn điều chỉnh giảm: cổng có thể ghi số dương
                        result = 'diff'
                    else:
                        result = 'match'
                elif p and any(s in p['status'].lower() for s in BAD_STATUS):
                    continue
                else:
                    result = 'portal_only' if p else 'book_only'
                partner = (b or {}).get('partner_id') or Partner.search([('vat', '=', key[0])], limit=1).id
                vals.append({
                    'check_id': rec.id, 'result': result, 'partner_vat': key[0], 'invoice_no': key[1],
                    'partner_id': partner or False, 'ref': (p or b)['ref'], 'date': (p or b)['date'],
                    'portal_base': p and p['base'], 'portal_tax': p and p['tax'], 'portal_status': p and p['status'],
                    'book_base': b and b['base'], 'book_tax': b and b['tax'],
                    'source_model': b and b['source_model'], 'source_id': b and b['source_id']})
            self.env['lfood.einvoice.check.line'].create(vals)
            counts = {k: len([v for v in vals if v['result'] == k]) for k, _l in RESULTS}
            rec.write({'checked_on': fields.Datetime.now(), 'summary': ', '.join(
                '%s: %s' % (label, counts[k]) for k, label in RESULTS if counts[k]) or _('Không có hóa đơn')})
        return True


class LfoodEinvoiceCheckLine(models.Model):
    _name = 'lfood.einvoice.check.line'
    _description = 'Kết quả đối chiếu hóa đơn'
    _order = 'result desc, partner_vat, invoice_no'

    check_id = fields.Many2one('lfood.einvoice.check', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='check_id.company_id', store=True)
    result = fields.Selection(RESULTS, 'Kết quả', required=True)
    partner_vat = fields.Char('Mã số thuế')
    partner_id = fields.Many2one('res.partner', 'Đối tác')
    invoice_no = fields.Integer('Số hóa đơn')
    ref = fields.Char('Ký hiệu, số')
    date = fields.Date('Ngày lập')
    portal_base = fields.Float('Cổng thuế: chưa thuế', digits=(16, 0))
    portal_tax = fields.Float('Cổng thuế: thuế', digits=(16, 0))
    portal_status = fields.Char('Trạng thái trên cổng')
    book_base = fields.Float('Sổ: chưa thuế', digits=(16, 0))
    book_tax = fields.Float('Sổ: thuế', digits=(16, 0))
    source_model = fields.Char()
    source_id = fields.Integer()

    def action_open_source(self):
        self.ensure_one()
        if not self.source_model:
            return False
        return {'type': 'ir.actions.act_window', 'res_model': self.source_model, 'res_id': self.source_id, 'view_mode': 'form'}
