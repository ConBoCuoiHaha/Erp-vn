"""Nhập dữ liệu ban đầu từ Excel, CSV (HT09).

Dùng khi chuyển từ phần mềm cũ (MISA hoặc phần mềm khác) sang: xuất dữ liệu ra Excel, CSV rồi nhập vào đây. App không
phụ thuộc mẫu cột của phần mềm nào: đọc dòng tiêu đề, tự đoán cột theo tên, kế toán sửa lại ánh xạ nếu cần, bấm Kiểm tra
để xem lỗi trước, rồi mới Nhập. Nhập xong ghi nhật ký; chạy lại lần hai không tạo trùng (đối tác, mặt hàng, tài sản so
theo mã; số dư đầu kỳ, tồn kho đầu kỳ chỉ nhập một lần cho mỗi đợt).

Loại dữ liệu nhập được:
- Đối tác: mã số thuế, tên, địa chỉ, điện thoại, email;
- Mặt hàng: mã, tên, đơn vị tính, loại, mã vạch;
- Số dư đầu kỳ tài khoản: tài khoản, dư Nợ, dư Có, đối tượng (nếu tài khoản theo dõi công nợ) - tạo một bút toán số dư
  đầu kỳ, bắt buộc cân;
- Tồn kho đầu kỳ: kho, mã hàng, số lô, hạn dùng, số lượng, đơn giá - tạo phiếu nhập kho "Tồn đầu kỳ" (không ghi sổ lại
  vì số dư 156, 152 đã có trong số dư đầu kỳ tài khoản);
- Tài sản cố định: tên, loại, nguyên giá, thời gian sử dụng, ngày bắt đầu khấu hao - tạo thẻ tài sản ở trạng thái Nháp
  để kế toán kiểm tra rồi Ghi tăng; hao mòn lũy kế đã có trong số dư đầu kỳ tài khoản 214 nên không nhập lại ở đây.
"""
import base64
import csv
import io
import re
import unicodedata

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd

# mã trường: (nhãn, bắt buộc, kiểu, từ khóa đoán cột)
SPECS = {
    'partner': {
        'name': ('Tên đối tác', True, 'char', ['ten', 'name', 'doi tac', 'khach', 'nha cung cap']),
        'vat': ('Mã số thuế', False, 'char', ['mst', 'ma so thue', 'tax']),
        'street': ('Địa chỉ', False, 'char', ['dia chi', 'address']),
        'phone': ('Điện thoại', False, 'char', ['dien thoai', 'phone', 'sdt']),
        'email': ('Email', False, 'char', ['email']),
    },
    'product': {
        'code': ('Mã hàng', True, 'char', ['ma hang', 'ma vat tu', 'ma san pham', 'sku', 'code']),
        'name': ('Tên hàng', True, 'char', ['ten hang', 'ten vat tu', 'ten san pham', 'name']),
        'uom': ('Đơn vị tính', True, 'char', ['dvt', 'don vi', 'uom']),
        'kind': ('Loại (goods, finished, material, tool)', False, 'char', ['loai', 'nhom', 'kind']),
        'barcode': ('Mã vạch', False, 'char', ['ma vach', 'barcode', 'ean']),
    },
    'balance': {
        'account': ('Số hiệu tài khoản', True, 'char', ['tai khoan', 'so hieu', 'account', 'tk']),
        'debit': ('Dư Nợ', False, 'number', ['du no', 'no dau ky', 'debit']),
        'credit': ('Dư Có', False, 'number', ['du co', 'co dau ky', 'credit']),
        'partner': ('Đối tượng (mã số thuế hoặc tên)', False, 'char', ['doi tuong', 'khach', 'nha cung cap', 'mst', 'partner']),
    },
    'stock': {
        'warehouse': ('Mã kho', True, 'char', ['kho', 'warehouse']),
        'product': ('Mã hàng', True, 'char', ['ma hang', 'ma vat tu', 'sku', 'code']),
        'lot': ('Số lô', False, 'char', ['lo', 'lot', 'batch']),
        'expiry': ('Hạn dùng', False, 'date', ['han dung', 'hsd', 'expiry']),
        'quantity': ('Số lượng', True, 'number', ['so luong', 'ton', 'qty', 'quantity']),
        'price_unit': ('Đơn giá', True, 'number', ['don gia', 'gia von', 'price', 'unit']),
    },
    'asset': {
        'name': ('Tên tài sản', True, 'char', ['ten tai san', 'ten', 'name']),
        'category': ('Mã loại tài sản', True, 'char', ['loai', 'nhom', 'category']),
        'original_value': ('Nguyên giá', True, 'number', ['nguyen gia', 'original', 'value']),
        'life_months': ('Thời gian sử dụng (tháng)', True, 'number', ['thoi gian', 'so thang', 'life']),
        'date_start': ('Ngày bắt đầu khấu hao', True, 'date', ['ngay bat dau', 'ngay tinh khau hao', 'date']),
        'serial': ('Số hiệu, biển số', False, 'char', ['so hieu', 'bien so', 'serial']),
    },
}
KINDS = [('partner', 'Đối tác'), ('product', 'Mặt hàng'), ('balance', 'Số dư đầu kỳ tài khoản'),
         ('stock', 'Tồn kho đầu kỳ'), ('asset', 'Tài sản cố định')]


def unaccent(text):
    text = unicodedata.normalize('NFD', (text or '').lower())
    return ''.join(c for c in text if unicodedata.category(c) != 'Mn').replace('đ', 'd')


def to_number(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or '').strip().replace(' ', '')
    if not s:
        return 0.0
    if re.fullmatch(r'-?[\d.]+,\d{1,3}', s) or re.fullmatch(r'-?\d{1,3}(\.\d{3})+', s):
        s = s.replace('.', '').replace(',', '.')
    else:
        s = s.replace(',', '')
    try:
        return float(s)
    except ValueError:
        return 0.0


def to_date(v):
    if hasattr(v, 'year'):
        return v.date() if hasattr(v, 'hour') else v
    s = str(v or '').strip()[:10]
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return fields.Date.to_date(__import__('datetime').datetime.strptime(s, fmt))
        except ValueError:
            continue
    return False


class LfoodImportJob(models.Model):
    _name = 'lfood.import.job'
    _description = 'Đợt nhập dữ liệu'
    _order = 'id desc'

    name = fields.Char('Tên đợt nhập', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    kind = fields.Selection(KINDS, 'Loại dữ liệu', required=True, default='partner')
    file = fields.Binary('Tệp Excel hoặc CSV', required=True)
    file_name = fields.Char()
    opening_date = fields.Date('Ngày số dư, tồn đầu kỳ', default=lambda s: fields.Date.context_today(s))
    mapping_ids = fields.One2many('lfood.import.mapping', 'job_id', 'Ánh xạ cột')
    columns = fields.Char('Các cột trong tệp', readonly=True)
    preview_html = fields.Html('Kiểm tra', readonly=True, sanitize=False)
    result = fields.Char('Kết quả nhập', readonly=True)
    state = fields.Selection([('draft', 'Nháp'), ('mapped', 'Đã đọc tệp'), ('done', 'Đã nhập')], 'Trạng thái',
                             default='draft', required=True, readonly=True)

    # ------------------------------------------------------------ đọc tệp
    def _rows(self):
        raw = base64.b64decode(self.file)
        if raw[:2] == b'PK':
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            rows = [list(r) for r in wb.active.iter_rows(values_only=True)]
        else:
            text = raw.decode('utf-8-sig')
            rows = list(csv.reader(io.StringIO(text), delimiter=max(';,\t', key=text[:4096].count)))
        rows = [r for r in rows if any(str(c or '').strip() for c in r)]
        if not rows:
            raise UserError(_('Tệp không có dòng nào.'))
        return rows

    def action_read(self):
        """Đọc tiêu đề, đoán ánh xạ cột."""
        for rec in self:
            rows = rec._rows()
            header = [str(c or '').strip() for c in rows[0]]
            rec.mapping_ids.unlink()
            spec = SPECS[rec.kind]
            vals = []
            for key, (label, required, ftype, words) in spec.items():
                guess = False
                for i, col in enumerate(header):
                    c = unaccent(col)
                    if any(w in c for w in words):
                        guess = i
                        break
                vals.append({'job_id': rec.id, 'field_key': key, 'label': label, 'required': required,
                             'column_index': guess if guess is not False else -1})
            self.env['lfood.import.mapping'].create(vals)
            rec.write({'columns': ' | '.join('%s: %s' % (i, h) for i, h in enumerate(header)), 'state': 'mapped'})
        return True

    def _records(self):
        """[(số dòng, {mã trường: giá trị})] theo ánh xạ."""
        self.ensure_one()
        rows = self._rows()
        spec = SPECS[self.kind]
        mapping = {m.field_key: m.column_index for m in self.mapping_ids if m.column_index >= 0}
        missing = [spec[k][0] for k, (label, req, t, w) in spec.items() if req and k not in mapping]
        if missing:
            raise UserError(_('Chưa chọn cột cho: %s') % ', '.join(missing))
        out = []
        for n, row in enumerate(rows[1:], start=2):
            data = {}
            for key, idx in mapping.items():
                raw = row[idx] if idx < len(row) else None
                ftype = spec[key][2]
                data[key] = to_number(raw) if ftype == 'number' else to_date(raw) if ftype == 'date' else \
                    (str(raw).strip() if raw not in (None, '') else '')
            if any(v not in (None, '', 0, False) for v in data.values()):
                out.append((n, data))
        return out

    # ------------------------------------------------------------ kiểm tra và nhập
    def _check(self, records):
        self.ensure_one()
        problems = []
        spec = SPECS[self.kind]
        for n, d in records:
            for key, (label, required, ftype, words) in spec.items():
                if required and not d.get(key):
                    problems.append(_('Dòng %s: thiếu %s') % (n, label))
            if self.kind == 'balance':
                account = self.env['lfood.account'].sudo().search([('code', '=', d['account'])], limit=1)
                if not account:
                    problems.append(_('Dòng %s: không có tài khoản %s') % (n, d['account']))
                elif not account.allow_posting:
                    problems.append(_('Dòng %s: tài khoản %s có tài khoản con, ghi số dư vào tài khoản chi tiết')
                                    % (n, d['account']))
            if self.kind == 'stock':
                if not self.env['lfood.warehouse'].sudo().search_count([('code', '=', d['warehouse']),
                                                                        ('company_id', '=', self.company_id.id)]):
                    problems.append(_('Dòng %s: không có kho %s') % (n, d['warehouse']))
                if not self.env['lfood.product'].sudo().search_count([('code', '=', d['product'])]):
                    problems.append(_('Dòng %s: không có mặt hàng %s') % (n, d['product']))
            if self.kind == 'asset' and not self.env['lfood.asset.category'].sudo().search_count([('code', '=', d['category'])]):
                problems.append(_('Dòng %s: không có loại tài sản %s') % (n, d['category']))
        if self.kind == 'balance':
            debit = sum(d.get('debit', 0) for _n, d in records)
            credit = sum(d.get('credit', 0) for _n, d in records)
            if round(debit - credit):
                problems.append(_('Tổng dư Nợ %s khác tổng dư Có %s, lệch %s') % (vnd(debit), vnd(credit), vnd(debit - credit)))
        return problems

    def action_check(self):
        for rec in self:
            records = rec._records()
            problems = rec._check(records)
            head = Markup('<p>%s</p>') % (_('Đọc được %s dòng dữ liệu.') % len(records))
            if problems:
                rec.preview_html = head + Markup('<div class="alert alert-warning"><b>%s</b><ul>%s</ul></div>') % (
                    _('Cần sửa trước khi nhập:'),
                    Markup('').join(Markup('<li>%s</li>') % p for p in problems[:50]))
            else:
                sample = records[:5]
                rows = Markup('').join(
                    Markup('<tr><td>%s</td><td>%s</td></tr>') % (n, ', '.join('%s=%s' % (k, v) for k, v in d.items() if v))
                    for n, d in sample)
                rec.preview_html = head + Markup('<p>%s</p><table class="table table-sm">%s</table>') % (
                    _('Không thấy lỗi. Xem thử 5 dòng đầu:'), rows)
        return True

    def action_import(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được nhập dữ liệu ban đầu.'))
        for rec in self.filtered(lambda r: r.state != 'done'):
            records = rec._records()
            problems = rec._check(records)
            if problems:
                raise UserError(_('Còn lỗi, chưa nhập được:\n%s') % '\n'.join(problems[:20]))
            count = getattr(rec, '_import_%s' % rec.kind)(records)
            rec.write({'state': 'done', 'result': _('Đã nhập %s dòng') % count})
            self.env['lfood.audit.log']._record_event(
                'create', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Nhập dữ liệu %s từ tệp %s: %s dòng') % (
                    dict(KINDS)[rec.kind], rec.file_name or '', count))
        return True

    def _import_partner(self, records):
        Partner = self.env['res.partner']
        n = 0
        for _row, d in records:
            partner = Partner.search([('vat', '=', d['vat'])], limit=1) if d.get('vat') else Partner.browse()
            partner = partner or Partner.search([('name', '=', d['name'])], limit=1)
            vals = {'name': d['name'], 'vat': d.get('vat') or False, 'street': d.get('street') or False,
                    'phone': d.get('phone') or False, 'email': d.get('email') or False, 'is_company': True}
            if partner:
                partner.write({k: v for k, v in vals.items() if v})
            else:
                Partner.create(vals)
                n += 1
        return n

    def _import_product(self, records):
        Product = self.env['lfood.product']
        kinds = {'goods', 'finished', 'material', 'tool'}
        n = 0
        for _row, d in records:
            product = Product.search([('code', '=', d['code'])], limit=1)
            vals = {'code': d['code'], 'name': d['name'], 'uom': d['uom'] or 'cái',
                    'kind': d['kind'] if d.get('kind') in kinds else 'goods'}
            if d.get('barcode'):
                vals['barcode'] = d['barcode']
            if product:
                product.write(vals)
            else:
                Product.create(vals)
                n += 1
        return n

    def _import_balance(self, records):
        Partner = self.env['res.partner']
        lines = []
        for _row, d in records:
            partner = None
            if d.get('partner'):
                partner = Partner.search(['|', ('vat', '=', d['partner']), ('name', '=', d['partner'])], limit=1) or None
            label = _('Số dư đầu kỳ %s') % d['account']
            if round(d.get('debit', 0)):
                lines.append((d['account'], d['debit'], 0, partner, label, None))
            if round(d.get('credit', 0)):
                lines.append((d['account'], 0, d['credit'], partner, label, None))
        self.env['lfood.move']._create_from_source(
            self, 'general', self.opening_date, lines, memo=_('Số dư đầu kỳ theo %s') % self.name, ref=self.name,
            key='opening')
        return len(records)

    def _import_stock(self, records):
        Warehouse = self.env['lfood.warehouse']
        Product = self.env['lfood.product']
        by_wh = {}
        for _row, d in records:
            wh = Warehouse.search([('code', '=', d['warehouse']), ('company_id', '=', self.company_id.id)], limit=1)
            product = Product.search([('code', '=', d['product'])], limit=1)
            by_wh.setdefault(wh, []).append((0, 0, {
                'product_id': product.id, 'quantity': d['quantity'], 'price_unit': d['price_unit'],
                'lot_name': d.get('lot') or False, 'expiry_date': d.get('expiry') or False}))
        Picking = self.env['lfood.stock.picking']
        for wh, lines in by_wh.items():
            Picking.create({'company_id': self.company_id.id, 'kind': 'in', 'purpose': 'opening',
                            'date': self.opening_date, 'warehouse_id': wh.id,
                            'memo': _('Tồn đầu kỳ theo %s') % self.name, 'line_ids': lines}).action_done()
        return len(records)

    def _import_asset(self, records):
        Category = self.env['lfood.asset.category']
        Asset = self.env['lfood.asset']
        n = 0
        for _row, d in records:
            category = Category.search([('code', '=', d['category'])], limit=1)
            Asset.create({'name': d['name'], 'category_id': category.id, 'company_id': self.company_id.id,
                          'original_value': d['original_value'], 'life_months': int(d['life_months']),
                          'date_start': d['date_start'], 'serial': d.get('serial') or False})
            n += 1
        return n


class LfoodImportMapping(models.Model):
    _name = 'lfood.import.mapping'
    _description = 'Ánh xạ cột khi nhập dữ liệu'
    _order = 'id'

    job_id = fields.Many2one('lfood.import.job', required=True, ondelete='cascade', index=True)
    field_key = fields.Char('Mã trường', readonly=True)
    label = fields.Char('Trường trong app', readonly=True)
    required = fields.Boolean('Bắt buộc', readonly=True)
    column_index = fields.Integer('Cột số mấy trong tệp', default=-1,
                                  help='Đếm từ 0 theo danh sách cột ở trên; -1 là không lấy cột nào')
