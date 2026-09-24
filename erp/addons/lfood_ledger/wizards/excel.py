"""Xuất báo cáo sổ kế toán và báo cáo tài chính ra Excel, giữ công thức cộng và ô tự kiểm tra.

Tệp xuất ra không phải ảnh chụp số: các chỉ tiêu tổng hợp là công thức cộng đúng theo mẫu của Thông tư
(100 = 110 + 120 + …, 20 = 10 - 11, 50 = 20 + 30 + 40), dòng Cộng dùng SUM, và có ô Kiểm tra báo ngay
tài sản có bằng nguồn vốn hay không. Sửa một số trong Excel là các số cộng đổi theo, người nhận đối chiếu được.
"""
import base64
import io
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from . import b01, b03
from .reports import B02_LINES

MONEY = '#,##0;(#,##0);"-"'
TITLES = {
    'trial': ('BẢNG CÂN ĐỐI SỐ PHÁT SINH', ''),
    'ledger': ('SỔ CÁI', 'Mẫu số S03b-DN'),
    'partner': ('SỔ CHI TIẾT CÔNG NỢ', 'Mẫu số S31-DN'),
    'b01': ('BÁO CÁO TÌNH HÌNH TÀI CHÍNH', 'Mẫu số B01-DN'),
    'b02': ('BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH', 'Mẫu số B02-DN'),
    'b03': ('BÁO CÁO LƯU CHUYỂN TIỀN TỆ (Phương pháp trực tiếp)', 'Mẫu số B03-DN'),
}
B02_TOTALS = {
    '10': [('+', '01'), ('-', '02')],
    '20': [('+', '10'), ('-', '11')],
    '30': [('+', '20'), ('+', '21'), ('+', '22'), ('-', '23'), ('-', '25'), ('-', '26')],
    '40': [('+', '31'), ('-', '32')],
    '50': [('+', '30'), ('+', '40')],
    '60': [('+', '50'), ('-', '51'), ('-', '52')],
}
B03_TOTALS = {
    '20': [('+', c) for c in ('01', '02', '03', '04', '05', '06', '07')],
    '30': [('+', c) for c in ('21', '22', '23', '24', '25', '26', '27')],
    '40': [('+', c) for c in ('31', '32', '33', '34', '35', '36')],
    '50': [('+', '20'), ('+', '30'), ('+', '40')],
    '70': [('+', '50'), ('+', '60'), ('+', '61')],
}


class LfoodLedgerReport(models.TransientModel):
    _inherit = 'lfood.ledger.report'

    file = fields.Binary('Tệp Excel', readonly=True, attachment=True)
    file_name = fields.Char(readonly=True)

    # ------------------------------------------------------------------ khung tệp
    def _formats(self, book):
        f = lambda **kw: book.add_format(kw)
        return {
            'company': f(bold=True, font_size=11),
            'sub': f(font_size=10, italic=True),
            'form': f(font_size=10, italic=True, align='right'),
            'title': f(bold=True, font_size=14, align='center'),
            'period': f(font_size=11, align='center'),
            'unit': f(font_size=10, italic=True, align='right'),
            'head': f(bold=True, border=1, align='center', valign='vcenter', text_wrap=True, bg_color='#EEEEEE'),
            'text': f(border=1),
            'text_b': f(border=1, bold=True),
            'code': f(border=1, align='center'),
            'code_b': f(border=1, align='center', bold=True),
            'note': f(border=1, locked=False),
            'money': f(border=1, num_format=MONEY),
            'money_b': f(border=1, num_format=MONEY, bold=True, bg_color='#F5F5F5'),
            'total': f(border=1, num_format=MONEY, bold=True, bg_color='#EEEEEE'),
            'check': f(bold=True, font_size=11),
            'sign': f(align='center', font_size=10),
            'sign_b': f(align='center', bold=True, font_size=10),
            'muted': f(font_size=9, italic=True, text_wrap=True, valign='top'),
            'date': f(border=1, num_format='dd/mm/yyyy'),
        }

    def _header(self, sheet, f, width, form_code):
        title, form = TITLES[self.report]
        sheet.write(0, 0, self.company_id.name, f['company'])
        sheet.write(1, 0, self.company_id.street or '', f['sub'])
        if form:
            sheet.merge_range(0, max(width - 2, 1), 0, width - 1, form, f['form'])
            sheet.merge_range(1, max(width - 2, 1), 1, width - 1,
                              _('(Ban hành theo Thông tư 99/2025/TT-BTC)'), f['form'])
        sheet.merge_range(3, 0, 3, width - 1, title, f['title'])
        sheet.merge_range(4, 0, 4, width - 1, _('Từ ngày %s đến ngày %s')
                          % (self.date_from.strftime('%d/%m/%Y'), self.date_to.strftime('%d/%m/%Y')), f['period'])
        sheet.merge_range(5, 0, 5, width - 1, _('Đơn vị tính: đồng'), f['unit'])
        # chừa dòng 6 cho tên tài khoản, dòng 7 cho ô Kiểm tra, dòng 8 cho cảnh báo
        return 9

    def _signatures(self, sheet, f, row, width):
        row += 2
        sheet.merge_range(row, max(width - 3, 0), row, width - 1,
                          _('Ngày ... tháng ... năm ...'), f['sign'])
        row += 1
        span = max(width // 3, 1)
        for i, who in enumerate((_('Người lập biểu'), _('Kế toán trưởng'), _('Giám đốc'))):
            col = min(i * span, width - 1)
            end = min(col + span - 1, width - 1)
            if end > col:
                sheet.merge_range(row, col, row, end, who, f['sign_b'])
                sheet.merge_range(row + 1, col, row + 1, end, _('(Ký, họ tên)'), f['sign'])
            else:
                sheet.write(row, col, who, f['sign_b'])
        return row + 5

    def _note(self, sheet, f, row, width, text):
        sheet.merge_range(row, 0, row + 2, width - 1, text, f['muted'])
        return row + 4

    # ------------------------------------------------------------------ các mẫu báo cáo
    def _write_statement(self, sheet, f, lines, values_now, values_prev, totals, bold, note):
        """Mẫu chung cho B01, B02, B03: cột Chỉ tiêu, Mã số, Thuyết minh, Số kỳ này, Số kỳ trước."""
        width = 5
        row = self._header(sheet, f, width, True)
        for col, (label, size) in enumerate(((_('CHỈ TIÊU'), 60), (_('Mã số'), 8), (_('Thuyết minh'), 11),
                                             (_('Số cuối kỳ'), 20), (_('Số đầu năm'), 20))):
            sheet.write(row, col, label, f['head'])
            sheet.set_column(col, col, size)
        if self.report != 'b01':
            sheet.write(row, 3, _('Năm nay'), f['head'])
            sheet.write(row, 4, _('Năm trước'), f['head'])
        sheet.freeze_panes(row + 1, 0)
        head_row, row = row, row + 1
        at = {}
        for code, label in lines:
            if not code:
                sheet.write(row, 0, label, f['text_b'])
                for col in range(1, width):
                    sheet.write_blank(row, col, None, f['text_b'])
                row += 1
                continue
            at[code] = row
            strong = code in bold
            sheet.write(row, 0, label, f['text_b'] if strong else f['text'])
            sheet.write(row, 1, code, f['code_b'] if strong else f['code'])
            sheet.write_blank(row, 2, None, f['note'])
            for col, values in ((3, values_now), (4, values_prev)):
                value = values.get(code)
                fmt = f['money_b'] if strong else f['money']
                if value is None:
                    sheet.write_blank(row, col, None, fmt)
                else:
                    sheet.write_number(row, col, value, fmt)
            row += 1
        # chỉ tiêu tổng hợp thành công thức cộng đúng như mẫu
        letter = {3: 'D', 4: 'E'}
        for code, parts in totals.items():
            if code not in at:
                continue
            for col in (3, 4):
                terms = [(sign, at[part]) for sign, part in parts if part in at]
                if len(terms) != len(parts):
                    continue
                formula = ''.join('%s%s%s' % (sign, letter[col], r + 1) for sign, r in terms).lstrip('+')
                value = (values_now if col == 3 else values_prev).get(code)
                sheet.write_formula(row=at[code], col=col, formula='=' + formula,
                                    cell_format=f['money_b'] if code in bold else f['money'],
                                    value=value if value is not None else 0)
        row = self._note(sheet, f, row + 1, width, note)
        row = self._signatures(sheet, f, row, width)
        return at, head_row

    def _sheet_b01(self, book, f):
        sheet = book.add_worksheet('B01-DN')
        end, pl_end = self._b01_values(self.date_to + timedelta(days=1))
        start, _pl = self._b01_values(fields.Date.to_date('%s-01-01' % self.date_to.year))
        totals = {code: [('+', p) for p in parts] for code, parts in b01.TOTALS}
        at, head = self._write_statement(
            sheet, f, b01.LINES, end, start, totals, b01.BOLD,
            _('Theo mẫu B01-DN Phụ lục IV Thông tư 99/2025/TT-BTC. Chỉ tiêu 124, 266, 273, 274 và 341 cần sổ chi tiết '
              'riêng nên để trống. Chỉ tiêu có dấu (*) ghi số âm. Ô Thuyết minh để trống cho kế toán tự ghi.'))
        sheet.write(head - 2, 0, _('Kiểm tra'), f['check'])
        sheet.write_formula(head - 2, 1,
                            '=IF(D{a}=D{b},"Tài sản bằng nguồn vốn","Lệch "&TEXT(D{a}-D{b},"#,##0"))'.format(
                                a=at['280'] + 1, b=at['440'] + 1),
                            f['check'], _('Tài sản bằng nguồn vốn') if end['280'] == end['440'] else _('Lệch'))
        if pl_end:
            sheet.write(head - 1, 0, _('Còn số dư tài khoản loại 5 đến 9: hãy Kết chuyển cuối kỳ trước khi nộp báo cáo.'),
                        f['check'])

    def _sheet_b02(self, book, f):
        sheet = book.add_worksheet('B02-DN')
        cur = self._b02_values(self.date_from, self.date_to)
        prev = self._b02_values(self.date_from.replace(year=self.date_from.year - 1),
                                self.date_to.replace(year=self.date_to.year - 1))
        self._write_statement(
            sheet, f, B02_LINES, cur, prev, B02_TOTALS, {'10', '20', '30', '50', '60'},
            _('Theo mẫu B02-DN Phụ lục IV Thông tư 99/2025/TT-BTC. Chỉ tiêu 21, 24 và 70 cần sổ chi tiết riêng nên để '
              'trống. Chi phí 621, 622, 627 chỉ lên báo cáo sau khi kết chuyển sang 154 và tính giá vốn 632.'))

    def _sheet_b03(self, book, f):
        sheet = book.add_worksheet('B03-DN')
        cur, actual = self._b03_values(self.date_from, self.date_to)
        prev, _a = self._b03_values(self.date_from.replace(year=self.date_from.year - 1),
                                    self.date_to.replace(year=self.date_to.year - 1))
        at, head = self._write_statement(
            sheet, f, b03.LINES, cur, prev, B03_TOTALS, b03.BOLD,
            _('Theo mẫu B03-DN Phụ lục IV Thông tư 99/2025/TT-BTC, phương pháp trực tiếp. Chỉ tiêu 61 để trống vì app '
              'chưa theo dõi ngoại tệ. Số âm là tiền chi ra.'))
        sheet.write(head - 2, 0, _('Kiểm tra'), f['check'])
        sheet.write_formula(head - 2, 1,
                            '=IF(D{r}={v},"Khớp số dư tiền trên sổ","Lệch "&TEXT(D{r}-{v},"#,##0"))'.format(
                                r=at['70'] + 1, v=round(actual)),
                            f['check'], _('Khớp số dư tiền trên sổ') if cur['70'] == actual else _('Lệch'))

    def _sheet_trial(self, book, f):
        sheet = book.add_worksheet('CanDoiPhatSinh')
        width = 8
        row = self._header(sheet, f, width, False)
        heads = [(_('Số hiệu TK'), 12), (_('Tên tài khoản'), 42), (_('Dư Nợ đầu kỳ'), 18), (_('Dư Có đầu kỳ'), 18),
                 (_('Phát sinh Nợ'), 18), (_('Phát sinh Có'), 18), (_('Dư Nợ cuối kỳ'), 18), (_('Dư Có cuối kỳ'), 18)]
        for col, (label, size) in enumerate(heads):
            sheet.write(row, col, label, f['head'])
            sheet.set_column(col, col, size)
        sheet.freeze_panes(row + 1, 0)
        head_row, row = row, row + 1
        first = row
        names = {a.code: a.name for a in self.env['lfood.account'].search([])}
        for code, vals in self._trial_rows():
            sheet.write(row, 0, code, f['code'])
            sheet.write(row, 1, names.get(code, ''), f['text'])
            for i, value in enumerate(vals):
                sheet.write_number(row, 2 + i, round(value), f['money'])
            row += 1
        last = row - 1
        sheet.write(row, 0, '', f['total'])
        sheet.write(row, 1, _('Cộng'), f['text_b'])
        for col in range(2, width):
            letter = chr(ord('A') + col)
            sheet.write_formula(row, col, '=SUM(%s%s:%s%s)' % (letter, first + 1, letter, last + 1), f['total'])
        total_row = row + 1
        sheet.write(head_row - 2, 0, _('Kiểm tra'), f['check'])
        sheet.write_formula(head_row - 2, 1,
                            '=IF(AND(C{r}=D{r},E{r}=F{r},G{r}=H{r}),"Nợ bằng Có ở cả ba cặp cột","Lệch, phải kiểm tra")'
                            .format(r=total_row), f['check'], _('Nợ bằng Có ở cả ba cặp cột'))
        row = self._note(sheet, f, row + 2, width,
                         _('Mỗi dòng là một tài khoản chi tiết. Tài khoản lưỡng tính tách dư Nợ, dư Có theo từng đối '
                           'tượng nên tổng hai cột không bù trừ nhau.'))
        self._signatures(sheet, f, row, width)

    def _sheet_ledger(self, book, f):
        if not self.account_id:
            raise UserError(_('Chọn tài khoản trước khi xuất Sổ cái.'))
        sheet = book.add_worksheet('SoCai')
        width = 8
        row = self._header(sheet, f, width, True)
        sheet.write(row - 3, 0, _('Tài khoản %s - %s') % (self.account_id.code, self.account_id.name), f['company'])
        heads = [(_('Ngày ghi sổ'), 13), (_('Số bút toán'), 16), (_('Chứng từ'), 18), (_('Diễn giải'), 48),
                 (_('TK đối ứng'), 14), (_('Nợ'), 18), (_('Có'), 18), (_('Số dư'), 20)]
        for col, (label, size) in enumerate(heads):
            sheet.write(row, col, label, f['head'])
            sheet.set_column(col, col, size)
        sheet.freeze_panes(row + 1, 0)
        row += 1
        opening, lines = self._ledger_rows()
        sheet.write(row, 3, _('Số dư đầu kỳ'), f['text_b'])
        for col in (0, 1, 2, 4):
            sheet.write_blank(row, col, None, f['text_b'])
        sheet.write_blank(row, 5, None, f['money_b'])
        sheet.write_blank(row, 6, None, f['money_b'])
        sheet.write_number(row, 7, round(opening), f['money_b'])
        row += 1
        first = row
        for d, name, ref, label, dr, cr, counter in lines:
            sheet.write_datetime(row, 0, d, f['date'])
            sheet.write(row, 1, name or '', f['text'])
            sheet.write(row, 2, ref or '', f['text'])
            sheet.write(row, 3, label or '', f['text'])
            sheet.write(row, 4, counter or '', f['code'])
            sheet.write_number(row, 5, round(dr), f['money'])
            sheet.write_number(row, 6, round(cr), f['money'])
            sheet.write_formula(row, 7, '=H%s+F%s-G%s' % (row, row + 1, row + 1), f['money'])
            row += 1
        last = row - 1
        sheet.write(row, 3, _('Cộng phát sinh'), f['text_b'])
        for col in (0, 1, 2, 4):
            sheet.write_blank(row, col, None, f['text_b'])
        for col in (5, 6):
            letter = chr(ord('A') + col)
            sheet.write_formula(row, col, '=SUM(%s%s:%s%s)' % (letter, first + 1, letter, last + 1) if lines else '=0',
                                f['total'])
        sheet.write_formula(row, 7, '=H%s' % (last + 1 if lines else first), f['total'])
        row = self._note(sheet, f, row + 2, width,
                         _('Cột Số dư là công thức cộng dồn từ số dư đầu kỳ, sửa một dòng thì các dòng sau tự đổi theo.'))
        self._signatures(sheet, f, row, width)

    def _sheet_partner(self, book, f):
        sheet = book.add_worksheet('CongNo')
        width = 8
        prefix = self.account_id.code if self.account_id else '331'
        row = self._header(sheet, f, width, True)
        sheet.write(row - 3, 0, _('Tài khoản %s') % prefix, f['company'])
        heads = [(_('Đối tượng'), 42), (_('Mã số thuế'), 16), (_('Dư Nợ đầu kỳ'), 18), (_('Dư Có đầu kỳ'), 18),
                 (_('Phát sinh Nợ'), 18), (_('Phát sinh Có'), 18), (_('Dư Nợ cuối kỳ'), 18), (_('Dư Có cuối kỳ'), 18)]
        for col, (label, size) in enumerate(heads):
            sheet.write(row, col, label, f['head'])
            sheet.set_column(col, col, size)
        sheet.freeze_panes(row + 1, 0)
        row += 1
        first = row
        for name, vat, vals in self._partner_rows(prefix):
            sheet.write(row, 0, name, f['text'])
            sheet.write(row, 1, vat or '', f['code'])
            for i, value in enumerate(vals):
                sheet.write_number(row, 2 + i, round(value), f['money'])
            row += 1
        last = row - 1
        sheet.write(row, 0, _('Cộng'), f['text_b'])
        sheet.write_blank(row, 1, None, f['text_b'])
        for col in range(2, width):
            letter = chr(ord('A') + col)
            sheet.write_formula(row, col, '=SUM(%s%s:%s%s)' % (letter, first + 1, letter, last + 1) if last >= first else '=0',
                                f['total'])
        row = self._note(sheet, f, row + 2, width,
                         _('Số dư cuối kỳ = số dư đầu kỳ cộng phát sinh Nợ trừ phát sinh Có của từng đối tượng.'))
        self._signatures(sheet, f, row, width)

    # ------------------------------------------------------------------ số liệu dùng chung với bản HTML
    def _trial_rows(self):
        rows = self._query("""
            WITH x AS (
                SELECT a.code AS code, l.partner_id,
                       SUM(CASE WHEN l.date < %(f)s THEN COALESCE(l.balance, 0) ELSE 0 END) AS opening,
                       SUM(CASE WHEN l.date >= %(f)s THEN COALESCE(l.debit, 0) ELSE 0 END) AS debit,
                       SUM(CASE WHEN l.date >= %(f)s THEN COALESCE(l.credit, 0) ELSE 0 END) AS credit
                FROM lfood_move_line l JOIN lfood_account a ON a.id = l.account_id
                WHERE l.company_id = %(c)s AND l.state = 'posted' AND l.date <= %(t)s
                GROUP BY a.code, l.partner_id)
            SELECT code, SUM(GREATEST(opening, 0)), SUM(GREATEST(-opening, 0)), SUM(debit), SUM(credit),
                   SUM(GREATEST(opening + debit - credit, 0)), SUM(GREATEST(-(opening + debit - credit), 0)),
                   SUM(opening), SUM(opening + debit - credit)
            FROM x GROUP BY code ORDER BY code
        """, {'f': self.date_from, 't': self.date_to, 'c': self.company_id.id})
        natures = {a.code: a.nature for a in self.env['lfood.account'].search([])}
        out = []
        for code, odr, ocr, dr, cr, cdr, ccr, onet, cnet in rows:
            both = natures.get(code[:3]) == 'both' or natures.get(code) == 'both'
            o = (odr, ocr) if both else (max(onet, 0), max(-onet, 0))
            c = (cdr, ccr) if both else (max(cnet, 0), max(-cnet, 0))
            vals = [o[0], o[1], dr, cr, c[0], c[1]]
            if any(round(v) for v in vals):
                out.append((code, vals))
        return out

    def _ledger_rows(self):
        p = {'f': self.date_from, 't': self.date_to, 'c': self.company_id.id, 'a': self._account_prefix()}
        opening = self._query("""
            SELECT COALESCE(SUM(l.balance), 0) FROM lfood_move_line l JOIN lfood_account a ON a.id = l.account_id
            WHERE l.company_id = %(c)s AND l.state = 'posted' AND l.date < %(f)s AND a.code LIKE %(a)s""", p)[0][0]
        lines = self._query("""
            SELECT l.date, m.name, m.ref, COALESCE(l.name, m.memo), COALESCE(l.debit, 0), COALESCE(l.credit, 0),
                   (SELECT string_agg(DISTINCT a2.code, ', ') FROM lfood_move_line o JOIN lfood_account a2 ON a2.id = o.account_id
                    WHERE o.move_id = l.move_id AND SIGN(o.balance) <> SIGN(l.balance) AND a2.code NOT LIKE %(a)s)
            FROM lfood_move_line l JOIN lfood_move m ON m.id = l.move_id JOIN lfood_account a ON a.id = l.account_id
            WHERE l.company_id = %(c)s AND l.state = 'posted' AND l.date BETWEEN %(f)s AND %(t)s AND a.code LIKE %(a)s
            ORDER BY l.date, m.id, l.id""", p)
        return opening, lines

    def _partner_rows(self, prefix):
        p = {'f': self.date_from, 't': self.date_to, 'c': self.company_id.id, 'a': prefix + '%'}
        data = self._query("""
            SELECT COALESCE(pt.name, '(không có đối tượng)'), pt.vat,
                   SUM(CASE WHEN l.date < %(f)s THEN COALESCE(l.balance, 0) ELSE 0 END),
                   SUM(CASE WHEN l.date >= %(f)s THEN COALESCE(l.debit, 0) ELSE 0 END),
                   SUM(CASE WHEN l.date >= %(f)s THEN COALESCE(l.credit, 0) ELSE 0 END)
            FROM lfood_move_line l JOIN lfood_account a ON a.id = l.account_id LEFT JOIN res_partner pt ON pt.id = l.partner_id
            WHERE l.company_id = %(c)s AND l.state = 'posted' AND l.date <= %(t)s AND a.code LIKE %(a)s
            GROUP BY pt.name, pt.vat ORDER BY 1""", p)
        out = []
        for name, vat, opening, dr, cr in data:
            closing = opening + dr - cr
            vals = [max(opening, 0), max(-opening, 0), dr, cr, max(closing, 0), max(-closing, 0)]
            if any(round(v) for v in vals):
                out.append((name, vat, vals))
        return out

    # ------------------------------------------------------------------ nút xuất
    def _build_workbook(self):
        self.ensure_one()
        import xlsxwriter
        out = io.BytesIO()
        book = xlsxwriter.Workbook(out, {'in_memory': True})
        f = self._formats(book)
        getattr(self, '_sheet_%s' % self.report)(book, f)
        for sheet in book.worksheets():
            sheet.set_landscape() if self.report in ('trial', 'ledger', 'partner') else sheet.set_portrait()
            sheet.set_paper(9)
            sheet.fit_to_pages(1, 0)
            sheet.protect('', {'select_locked_cells': True, 'select_unlocked_cells': True, 'sort': True,
                               'autofilter': True})
        book.close()
        return out.getvalue()

    def action_export_excel(self):
        self.ensure_one()
        if self.report == 'dashboard':
            raise UserError(_('Bảng điều hành chỉ xem trên màn hình, không có mẫu Excel.'))
        self.env['lfood.move.line'].flush_model()
        data = self._build_workbook()
        name = '%s-%s-%s.xlsx' % (self.report, self.company_id.lfood_code or self.company_id.id,
                                  self.date_to.strftime('%Y%m%d'))
        self.sudo().write({'file': base64.b64encode(data), 'file_name': name})
        self.env['lfood.audit.log']._record_event(
            'print', model=self._name, res_name=dict(self._fields['report'].selection)[self.report],
            company_id=self.company_id.id,
            summary=_('Xuất Excel %s từ %s đến %s')
            % (dict(self._fields['report'].selection)[self.report],
               self.date_from.strftime('%d/%m/%Y'), self.date_to.strftime('%d/%m/%Y')))
        return {'type': 'ir.actions.act_url', 'target': 'self',
                'url': '/web/content/%s/%s/file/%s?download=true' % (self._name, self.id, name)}



