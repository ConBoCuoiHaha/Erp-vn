"""Sổ cái, bảng cân đối số phát sinh, sổ chi tiết công nợ, báo cáo kết quả kinh doanh B02-DN (Thông tư 99/2025/TT-BTC).
Chỉ đọc bút toán đã ghi sổ; in bằng nút In của trình duyệt (Ctrl+P)."""
from datetime import date, timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models, _

from odoo.addons.lfood_voucher.models.tools import vnd
from . import b01, b03


B02_LINES = [
    ('01', '1. Doanh thu bán hàng và cung cấp dịch vụ'), ('02', '2. Các khoản giảm trừ doanh thu'),
    ('10', '3. Doanh thu thuần về bán hàng và cung cấp dịch vụ (10 = 01 - 02)'), ('11', '4. Giá vốn hàng bán'),
    ('20', '5. Lợi nhuận gộp về bán hàng và cung cấp dịch vụ (20 = 10 - 11)'),
    ('21', '6. Lãi/lỗ của hoạt động bán, thanh lý bất động sản đầu tư'),
    ('22', '7. Doanh thu hoạt động tài chính'), ('23', '8. Chi phí tài chính'),
    ('24', '   Trong đó: Chi phí đi vay'), ('25', '9. Chi phí bán hàng'), ('26', '10. Chi phí quản lý doanh nghiệp'),
    ('30', '11. Lợi nhuận thuần từ hoạt động kinh doanh (30 = 20 + 21 + 22 - (23 + 25 + 26))'),
    ('31', '12. Thu nhập khác'), ('32', '13. Chi phí khác'), ('40', '14. Lợi nhuận khác (40 = 31 - 32)'),
    ('50', '15. Tổng lợi nhuận kế toán trước thuế (50 = 30 + 40)'),
    ('51', '16. Chi phí thuế TNDN hiện hành'), ('52', '17. Chi phí thuế TNDN hoãn lại'),
    ('60', '18. Lợi nhuận sau thuế thu nhập doanh nghiệp (60 = 50 - 51 - 52)'), ('70', '19. Lãi cơ bản trên cổ phiếu'),
]


def money(v):
    v = round(v or 0)
    if not v:
        return ''
    return '(%s)' % vnd(-v) if v < 0 else vnd(v)


def table(head, rows, foot=None):
    h = Markup('').join(Markup('<th>%s</th>') % c for c in head)
    body = Markup('').join(
        Markup('<tr%s>%s</tr>') % (Markup(' style="font-weight:600"') if bold else '',
                                   Markup('').join(Markup('<td%s>%s</td>') % (Markup(' style="text-align:right"') if i >= num_from else '', c)
                                                   for i, c in enumerate(cells)))
        for cells, bold, num_from in rows)
    f = Markup('')
    if foot:
        f = Markup('<tr style="font-weight:700">%s</tr>') % Markup('').join(Markup('<td style="text-align:right">%s</td>') % c for c in foot)
    return Markup('<div class="o_lfood_changes"><table><tr>%s</tr>%s%s</table></div>') % (h, body, f)


class LfoodLedgerReport(models.TransientModel):
    _name = 'lfood.ledger.report'
    _description = 'Báo cáo sổ kế toán'

    report = fields.Selection([('trial', 'Bảng cân đối số phát sinh'), ('ledger', 'Sổ cái'),
                               ('partner', 'Sổ chi tiết công nợ'), ('b01', 'Báo cáo tình hình tài chính (B01-DN)'), ('b03', 'Báo cáo lưu chuyển tiền tệ (B03-DN, trực tiếp)'), ('b02', 'Báo cáo kết quả hoạt động kinh doanh (B02-DN)'),
                               ('dashboard', 'Bảng điều hành ban giám đốc')],
                              'Báo cáo', required=True, default='trial')
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company)
    date_from = fields.Date('Từ ngày', required=True, default=lambda s: date(fields.Date.context_today(s).year, 1, 1))
    date_to = fields.Date('Đến ngày', required=True, default=fields.Date.context_today)
    account_id = fields.Many2one('lfood.account', 'Tài khoản')
    html = fields.Html('Nội dung báo cáo', compute='_compute_html', sanitize=False)

    @api.depends('report', 'company_id', 'date_from', 'date_to', 'account_id')
    def _compute_html(self):
        for rec in self:
            if not (rec.date_from and rec.date_to and rec.company_id):
                rec.html = False
                continue
            self.env['lfood.move.line'].flush_model()
            head = Markup('<h3>%s</h3><p>%s · Từ %s đến %s · Đơn vị tính: đồng</p>') % (
                dict(self._fields['report'].selection)[rec.report], rec.company_id.name,
                rec.date_from.strftime('%d/%m/%Y'), rec.date_to.strftime('%d/%m/%Y'))
            body = getattr(rec, '_render_%s' % rec.report)()
            rec.html = head + body

    # ------------------------------------------------------------ truy vấn
    def _query(self, sql, params):
        self.env.cr.execute(sql, params)
        return self.env.cr.fetchall()

    def _account_prefix(self):
        return (self.account_id.code or '') + '%'

    # ------------------------------------------------------------ bảng cân đối số phát sinh
    def _render_trial(self):
        rows = self._query("""
            WITH x AS (
                SELECT a.code AS code, l.partner_id,
                       SUM(CASE WHEN l.date < %(f)s THEN COALESCE(l.balance, 0) ELSE 0 END) AS opening,
                       SUM(CASE WHEN l.date >= %(f)s THEN COALESCE(l.debit, 0) ELSE 0 END) AS debit,
                       SUM(CASE WHEN l.date >= %(f)s THEN COALESCE(l.credit, 0) ELSE 0 END) AS credit
                FROM lfood_move_line l JOIN lfood_account a ON a.id = l.account_id
                WHERE l.company_id = %(c)s AND l.state = 'posted' AND l.date <= %(t)s
                GROUP BY a.code, l.partner_id)
            SELECT LEFT(code, 3) AS acc1, code,
                   SUM(GREATEST(opening, 0)), SUM(GREATEST(-opening, 0)), SUM(debit), SUM(credit),
                   SUM(GREATEST(opening + debit - credit, 0)), SUM(GREATEST(-(opening + debit - credit), 0)),
                   SUM(opening), SUM(opening + debit - credit)
            FROM x GROUP BY code ORDER BY code
        """, {'f': self.date_from, 't': self.date_to, 'c': self.company_id.id})
        Account = self.env['lfood.account']
        names = {a.code: a.name for a in Account.search([])}
        natures = {a.code: a.nature for a in Account.search([])}

        def split(code, per_partner_dr, per_partner_cr, net):
            # tài khoản lưỡng tính trình bày cả hai bên theo từng đối tượng; tài khoản khác trình bày số dư ròng
            if natures.get(code[:3]) == 'both' or natures.get(code) == 'both':
                return per_partner_dr, per_partner_cr
            return max(net, 0), max(-net, 0)

        by1, out = {}, []
        for acc1, code, odr, ocr, dr, cr, cdr, ccr, onet, cnet in rows:
            o = split(code, odr, ocr, onet)
            c = split(code, cdr, ccr, cnet)
            vals = [o[0], o[1], dr, cr, c[0], c[1]]
            if not any(round(v) for v in vals):
                continue
            total = by1.setdefault(acc1, [0] * 6)
            for i, v in enumerate(vals):
                total[i] += v
            out.append((acc1, code, vals))
        rendered, totals = [], [0] * 6
        for acc1 in sorted(by1):
            detail = [r for r in out if r[0] == acc1]
            rendered.append(([acc1, names.get(acc1, '')] + [money(v) for v in by1[acc1]], True, 2))
            for i, v in enumerate(by1[acc1]):
                totals[i] += v
            for _a, code, vals in detail:
                if code != acc1:
                    rendered.append(([code, names.get(code, '')] + [money(v) for v in vals], False, 2))
        balanced = all(round(totals[i]) == round(totals[i + 1]) for i in (0, 2, 4))
        note = Markup('<p>%s</p>') % (_('Tổng Nợ bằng tổng Có ở cả ba cặp cột: sổ cân.') if balanced
                                      else _('CẢNH BÁO: tổng Nợ khác tổng Có, cần kiểm tra.'))
        return table([_('Số hiệu TK'), _('Tên tài khoản'), _('Dư Nợ đầu kỳ'), _('Dư Có đầu kỳ'), _('Phát sinh Nợ'),
                      _('Phát sinh Có'), _('Dư Nợ cuối kỳ'), _('Dư Có cuối kỳ')], rendered,
                     foot=['', _('Cộng')] + [money(v) for v in totals]) + note

    # ------------------------------------------------------------ sổ cái
    def _render_ledger(self):
        if not self.account_id:
            return Markup('<p>%s</p>') % _('Chọn tài khoản để xem sổ cái.')
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
        rows = [(['', '', '', _('Số dư đầu kỳ'), '', money(max(opening, 0)), money(max(-opening, 0))], True, 5)]
        dr_total = cr_total = 0
        for d, name, ref, label, dr, cr, counter in lines:
            rows.append(([d.strftime('%d/%m/%Y'), escape(name), escape(ref or ''), escape(label or ''), counter or '',
                          money(dr), money(cr)], False, 5))
            dr_total += dr
            cr_total += cr
        closing = opening + dr_total - cr_total
        rows.append((['', '', '', _('Cộng phát sinh'), '', money(dr_total), money(cr_total)], True, 5))
        rows.append((['', '', '', _('Số dư cuối kỳ'), '', money(max(closing, 0)), money(max(-closing, 0))], True, 5))
        return Markup('<p>%s</p>') % ('%s %s' % (self.account_id.code, self.account_id.name)) + table(
            [_('Ngày ghi sổ'), _('Số bút toán'), _('Chứng từ'), _('Diễn giải'), _('TK đối ứng'), _('Nợ'), _('Có')], rows)

    # ------------------------------------------------------------ sổ chi tiết công nợ
    def _render_partner(self):
        prefix = self.account_id.code if self.account_id else '331'
        p = {'f': self.date_from, 't': self.date_to, 'c': self.company_id.id, 'a': prefix + '%'}
        data = self._query("""
            SELECT COALESCE(pt.name, '(không có đối tượng)'), pt.vat,
                   SUM(CASE WHEN l.date < %(f)s THEN COALESCE(l.balance, 0) ELSE 0 END),
                   SUM(CASE WHEN l.date >= %(f)s THEN COALESCE(l.debit, 0) ELSE 0 END),
                   SUM(CASE WHEN l.date >= %(f)s THEN COALESCE(l.credit, 0) ELSE 0 END)
            FROM lfood_move_line l JOIN lfood_account a ON a.id = l.account_id LEFT JOIN res_partner pt ON pt.id = l.partner_id
            WHERE l.company_id = %(c)s AND l.state = 'posted' AND l.date <= %(t)s AND a.code LIKE %(a)s
            GROUP BY pt.name, pt.vat ORDER BY 1""", p)
        rows, totals = [], [0] * 6
        for name, vat, opening, dr, cr in data:
            closing = opening + dr - cr
            vals = [max(opening, 0), max(-opening, 0), dr, cr, max(closing, 0), max(-closing, 0)]
            if not any(round(v) for v in vals):
                continue
            totals = [a + b for a, b in zip(totals, vals)]
            rows.append(([escape(name), vat or ''] + [money(v) for v in vals], False, 2))
        return Markup('<p>%s</p>') % (_('Tài khoản %s') % prefix) + table(
            [_('Đối tượng'), _('Mã số thuế'), _('Dư Nợ đầu kỳ'), _('Dư Có đầu kỳ'), _('Phát sinh Nợ'), _('Phát sinh Có'),
             _('Dư Nợ cuối kỳ'), _('Dư Có cuối kỳ')], rows, foot=['', _('Cộng')] + [money(v) for v in totals])

    # ------------------------------------------------------------ B01-DN
    def _b01_rows(self, before):
        """Số dư trước ngày `before` theo từng tài khoản chi tiết và đối tượng: [(mã TK, kỳ hạn, tính chất, số dư)].
        Phân hệ khác ghi đè để chuyển kỳ hạn theo từng khoản (ví dụ khoản vay đến hạn trả trong 12 tháng)."""
        self.env['lfood.move.line'].flush_model()
        return [tuple(r) for r in self._query("""
            SELECT a.code, a.bs_term, a.nature, SUM(COALESCE(l.balance, 0))
            FROM lfood_move_line l JOIN lfood_account a ON a.id = l.account_id
            WHERE l.company_id = %s AND l.state = 'posted' AND l.date < %s
            GROUP BY a.code, a.bs_term, a.nature, l.partner_id""", (self.company_id.id, before))]

    def _b01_values(self, before):
        rows = self._b01_rows(before)
        pl = sum(bal for code, _t, _n, bal in rows if code[0] in '56789')
        return b01.compute(rows), round(pl)

    def _abnormal_balances(self, before):
        """Tài khoản một tính chất có số dư ngược chiều: dấu hiệu hạch toán sai (chi quá tồn quỹ, xuất kho âm...)."""
        return self._query("""
            SELECT a.code, SUM(COALESCE(l.balance, 0))
            FROM lfood_move_line l JOIN lfood_account a ON a.id = l.account_id
            WHERE l.company_id = %s AND l.state = 'posted' AND l.date < %s AND a.nature <> 'both'
              AND LEFT(a.code, 1) IN ('1', '2', '3', '4')
            GROUP BY a.code, a.nature
            HAVING (a.nature = 'debit' AND ROUND(SUM(l.balance)) < 0) OR (a.nature = 'credit' AND ROUND(SUM(l.balance)) > 0)
            ORDER BY a.code""", (self.company_id.id, before))

    def _render_b01(self):
        from datetime import timedelta
        end, pl_end = self._b01_values(self.date_to + timedelta(days=1))
        start, _pl = self._b01_values(date(self.date_to.year, 1, 1))
        rows = []
        for code, label in b01.LINES:
            if not code:
                rows.append(([Markup('<b>%s</b>') % label, '', '', '', ''], True, 3))
                continue
            rows.append(([label, code, '', money(end.get(code)), money(start.get(code))], code in b01.BOLD, 3))
        warn = Markup('')
        if end['280'] != end['440']:
            warn = Markup('<div class="alert alert-warning">%s</div>') % (
                _('Tổng tài sản %s khác tổng nguồn vốn %s. Còn số dư tài khoản loại 5 đến 9 là %s: hãy Kết chuyển cuối kỳ đến ngày %s trước khi lập báo cáo.')
                % (vnd(end['280']), vnd(end['440']), money(pl_end), self.date_to.strftime('%d/%m/%Y')))
        else:
            warn = Markup('<p>%s</p>') % _('Tổng cộng tài sản bằng tổng cộng nguồn vốn.')
        abnormal = self._abnormal_balances(self.date_to + timedelta(days=1))
        if abnormal:
            warn += Markup('<div class="alert alert-warning">%s</div>') % (
                _('Tài khoản có số dư ngược chiều, cần kiểm tra hạch toán: %s')
                % ', '.join('%s (%s %s)' % (c, 'dư Có' if b < 0 else 'dư Nợ', vnd(abs(b))) for c, b in abnormal))
        note = Markup('<p class="text-muted">%s</p>') % _(
            'Theo mẫu B01-DN Phụ lục IV Thông tư 99/2025/TT-BTC. Ngắn hạn, dài hạn lấy theo thuộc tính Kỳ hạn của tài khoản chi tiết. '
            'Chỉ tiêu 124, 266 (dự phòng đầu tư nắm giữ đến ngày đáo hạn), 273, 274 và 341 cần sổ chi tiết riêng, hiện để trống. '
            'Chỉ tiêu có dấu (*) ghi số âm trong ngoặc đơn.')
        return warn + table([_('Chỉ tiêu'), _('Mã số'), _('Thuyết minh'), _('Số cuối kỳ'), _('Số đầu năm')], rows) + note

    # ------------------------------------------------------------ B03-DN
    def _cash_balance(self, before):
        return round(self._query("""
            SELECT COALESCE(SUM(l.balance), 0) FROM lfood_move_line l JOIN lfood_account a ON a.id = l.account_id
            WHERE l.company_id = %s AND l.state = 'posted' AND l.date < %s
              AND (a.code LIKE '111%%' OR a.code LIKE '112%%' OR a.code LIKE '113%%' OR a.bs_term = 'equivalent')""",
            (self.company_id.id, before))[0][0])

    def _b03_values(self, date_from, date_to):
        from datetime import timedelta
        rows = self._query("""
            SELECT m.id, m.source_model, m.source_id, m.source_key, a.code, SUM(COALESCE(l.balance, 0))
            FROM lfood_move m JOIN lfood_move_line l ON l.move_id = m.id JOIN lfood_account a ON a.id = l.account_id
            WHERE m.company_id = %s AND m.state = 'posted' AND m.journal <> 'closing' AND m.date BETWEEN %s AND %s
            GROUP BY m.id, m.source_model, m.source_id, m.source_key, a.code ORDER BY m.id""",
            (self.company_id.id, date_from, date_to))
        moves, current = {}, None
        for move_id, smodel, sid, skey, code, bal in rows:
            entry = moves.setdefault(move_id, {'lines': [], 'hint': None})
            entry['lines'].append((code, bal))
            if smodel == 'lfood.asset' and skey == 'dispose':
                entry['hint'] = '22'
            elif smodel == 'lfood.payment' and entry['hint'] is None:
                pay = self.env['lfood.payment'].sudo().browse(sid)
                lines = pay.voucher_id.report_version_id.line_ids
                if lines and all((l.acc_expense or '').startswith(('211', '212', '213', '217', '241')) for l in lines):
                    entry['hint'] = '21'
        return b03.compute([(e['lines'], e['hint']) for e in moves.values()], self._cash_balance(date_from)), \
            self._cash_balance(date_to + timedelta(days=1))

    def _render_b03(self):
        cur, actual = self._b03_values(self.date_from, self.date_to)
        prev, _a = self._b03_values(self.date_from.replace(year=self.date_from.year - 1), self.date_to.replace(year=self.date_to.year - 1))
        rows = []
        for code, label in b03.LINES:
            if not code:
                rows.append(([Markup('<b>%s</b>') % label, '', '', '', ''], True, 3))
                continue
            rows.append(([label, code, '', money(cur[code]), money(prev[code])], code in b03.BOLD, 3))
        check = (Markup('<p>%s</p>') % _('Tiền cuối kỳ trên báo cáo khớp số dư tiền trên sổ.')) if cur['70'] == actual else \
            Markup('<div class="alert alert-warning">%s</div>') % (_('Tiền cuối kỳ trên báo cáo %s khác số dư tiền trên sổ %s.') % (money(cur['70']), money(actual)))
        note = Markup('<p class="text-muted">%s</p>') % _(
            'Theo mẫu B03-DN Phụ lục IV Thông tư 99/2025/TT-BTC, phương pháp trực tiếp: mỗi khoản thu, chi tiền được phân loại theo '
            'tài khoản đối ứng trong cùng bút toán. Chuyển tiền giữa quỹ và ngân hàng không tính là luồng tiền. Trả nợ nhà thầu xây dựng '
            'hoặc trả tiền mua tài sản qua 331 chỉ vào chỉ tiêu 21 khi phiếu chi gắn chứng từ mua tài sản; kế toán rà lại trước khi nộp. '
            'Chỉ tiêu 61 (tỷ giá) để trống vì app chưa theo dõi ngoại tệ.')
        return check + table([_('Chỉ tiêu'), _('Mã số'), _('Thuyết minh'), _('Năm nay'), _('Năm trước')], rows) + note

    # ------------------------------------------------------------ B02-DN
    def _net(self, prefix, date_from, date_to):
        """Nợ trừ Có của tài khoản trong kỳ, không tính bút toán kết chuyển (để lập được trước và sau khi kết chuyển)."""
        return self._query("""
            SELECT COALESCE(SUM(l.balance), 0) FROM lfood_move_line l JOIN lfood_account a ON a.id = l.account_id
            WHERE l.company_id = %s AND l.state = 'posted' AND l.journal <> 'closing'
              AND l.date BETWEEN %s AND %s AND a.code LIKE %s""", (self.company_id.id, date_from, date_to, prefix + '%'))[0][0]

    def _b02_values(self, date_from, date_to):
        n = lambda p: self._net(p, date_from, date_to)
        v = {}
        v['01'] = -n('511')
        v['02'] = n('521')
        v['10'] = v['01'] - v['02']
        v['11'] = n('632')
        v['20'] = v['10'] - v['11']
        v['21'] = 0
        v['22'] = -n('515')
        v['23'] = n('635')
        v['24'] = None
        v['25'] = n('641')
        v['26'] = n('642')
        v['30'] = v['20'] + v['21'] + v['22'] - (v['23'] + v['25'] + v['26'])
        v['31'] = -n('711')
        v['32'] = n('811')
        v['40'] = v['31'] - v['32']
        v['50'] = v['30'] + v['40']
        v['51'] = n('8211')
        v['52'] = n('8212')
        v['60'] = v['50'] - (v['51'] + v['52'])
        v['70'] = None
        return v

    # ------------------------------------------------------------ bảng điều hành ban giám đốc
    def _balance_at(self, prefix, upto):
        """Số dư Nợ trừ Có của nhóm tài khoản tại một ngày."""
        return self._query("""
            SELECT COALESCE(SUM(l.balance), 0) FROM lfood_move_line l JOIN lfood_account a ON a.id = l.account_id
            WHERE l.company_id = %s AND l.state = 'posted' AND l.date <= %s AND a.code LIKE %s""",
                           (self.company_id.id, upto, prefix + '%'))[0][0]

    def _render_dashboard(self):
        """Doanh thu, chi phí, tiền, tồn kho, công nợ trên một màn hình; so với kỳ trước liền kề."""
        span = (self.date_to - self.date_from).days + 1
        prev_to = self.date_from + timedelta(days=-1)
        prev_from = prev_to + timedelta(days=-span + 1)
        cur, prev = self._b02_values(self.date_from, self.date_to), self._b02_values(prev_from, prev_to)

        def compare(label, code, invert=False):
            now, before = cur[code] or 0, prev[code] or 0
            delta = now - before
            pct = '%+.1f%%' % (delta * 100.0 / abs(before)) if before else ''
            good = delta < 0 if invert else delta > 0
            arrow = '' if not delta else (Markup('<span style="color:#15803D">▲</span>') if good
                                          else Markup('<span style="color:#B91C1C">▼</span>'))
            return ([label, money(now), money(before), Markup('%s %s %s') % (arrow, money(delta), pct)], code in ('10', '20', '50'), 1)

        kq = [compare(_('Doanh thu thuần'), '10'), compare(_('Giá vốn hàng bán'), '11', invert=True),
              compare(_('Lợi nhuận gộp'), '20'), compare(_('Chi phí bán hàng'), '25', invert=True),
              compare(_('Chi phí quản lý'), '26', invert=True), compare(_('Lợi nhuận trước thuế'), '50')]
        gross_margin = cur['20'] * 100.0 / cur['10'] if cur['10'] else 0

        positions = [(_('Tiền mặt'), '111'), (_('Tiền gửi ngân hàng'), '112'), (_('Phải thu khách hàng'), '131'),
                     (_('Hàng tồn kho'), '15'), (_('Tài sản cố định (nguyên giá)'), '211'),
                     (_('Phải trả người bán'), '331'), (_('Thuế và các khoản phải nộp'), '333'),
                     (_('Phải trả người lao động'), '334'), (_('Vay và nợ thuê tài chính'), '341')]
        pos_rows = []
        for label, prefix in positions:
            now, before = self._balance_at(prefix, self.date_to), self._balance_at(prefix, prev_to)
            sign = -1 if prefix in ('331', '333', '334', '341') else 1
            pos_rows.append(([label, money(sign * now), money(sign * before), money(sign * (now - before))], False, 1))

        items = self._query("""
            SELECT ci.code, ci.name, COALESCE(SUM(l.balance), 0) AS amount
            FROM lfood_move_line l JOIN lfood_cost_item ci ON ci.id = l.cost_item_id
            WHERE l.company_id = %s AND l.state = 'posted' AND l.journal <> 'closing' AND l.date BETWEEN %s AND %s
            GROUP BY ci.code, ci.name HAVING COALESCE(SUM(l.balance), 0) <> 0
            ORDER BY amount DESC LIMIT 5""", (self.company_id.id, self.date_from, self.date_to))
        item_rows = [([escape('%s %s' % (code, name)), money(amount)], False, 1) for code, name, amount in items]

        debts = self._query("""
            SELECT p.name, COALESCE(SUM(l.balance), 0) AS amount
            FROM lfood_move_line l JOIN lfood_account a ON a.id = l.account_id JOIN res_partner p ON p.id = l.partner_id
            WHERE l.company_id = %s AND l.state = 'posted' AND l.date <= %s AND a.code LIKE '131%%'
            GROUP BY p.name HAVING COALESCE(SUM(l.balance), 0) > 0
            ORDER BY amount DESC LIMIT 5""", (self.company_id.id, self.date_to))
        debt_rows = [([escape(name), money(amount)], False, 1) for name, amount in debts]

        payables = self._query("""
            SELECT p.name, COALESCE(SUM(-l.balance), 0) AS amount
            FROM lfood_move_line l JOIN lfood_account a ON a.id = l.account_id JOIN res_partner p ON p.id = l.partner_id
            WHERE l.company_id = %s AND l.state = 'posted' AND l.date <= %s AND a.code LIKE '331%%'
            GROUP BY p.name HAVING COALESCE(SUM(-l.balance), 0) > 0
            ORDER BY amount DESC LIMIT 5""", (self.company_id.id, self.date_to))
        pay_rows = [([escape(name), money(amount)], False, 1) for name, amount in payables]

        cash = self._balance_at('111', self.date_to) + self._balance_at('112', self.date_to)
        head = Markup('<p>%s</p>') % (_('So với kỳ liền trước từ %s đến %s. Tiền hiện có %s, tỷ lệ lãi gộp %.1f%%.')
                                      % (prev_from.strftime('%d/%m/%Y'), prev_to.strftime('%d/%m/%Y'), vnd(cash), gross_margin))
        parts = [head,
                 Markup('<h4>%s</h4>') % _('Kết quả kinh doanh'),
                 table([_('Chỉ tiêu'), _('Kỳ này'), _('Kỳ trước'), _('Tăng giảm')], kq),
                 Markup('<h4>%s</h4>') % _('Tình hình tài chính tại ngày cuối kỳ'),
                 table([_('Chỉ tiêu'), _('Cuối kỳ này'), _('Cuối kỳ trước'), _('Tăng giảm')], pos_rows),
                 Markup('<h4>%s</h4>') % _('5 khoản mục chi phí lớn nhất kỳ này'),
                 table([_('Khoản mục'), _('Số tiền')], item_rows or [([_('Chưa có số liệu'), ''], False, 1)]),
                 Markup('<h4>%s</h4>') % _('5 khách hàng còn nợ nhiều nhất'),
                 table([_('Khách hàng'), _('Còn phải thu')], debt_rows or [([_('Không có'), ''], False, 1)]),
                 Markup('<h4>%s</h4>') % _('5 nhà cung cấp còn phải trả nhiều nhất'),
                 table([_('Nhà cung cấp'), _('Còn phải trả')], pay_rows or [([_('Không có'), ''], False, 1)]),
                 Markup('<p class="text-muted">%s</p>') % _(
                     'Số liệu lấy từ bút toán đã ghi sổ, không tính bút toán kết chuyển. Mũi tên xanh là chiều tốt: '
                     'doanh thu, lợi nhuận tăng hoặc chi phí, giá vốn giảm.')]
        return Markup('').join(parts)

    def _render_b02(self):
        lines = B02_LINES
        cur = self._b02_values(self.date_from, self.date_to)
        prev = self._b02_values(self.date_from.replace(year=self.date_from.year - 1), self.date_to.replace(year=self.date_to.year - 1))
        rows = [([label, code, '', money(cur[code]) if cur[code] is not None else '',
                  money(prev[code]) if prev[code] is not None else ''], code in ('10', '20', '30', '50', '60'), 3)
                for code, label in lines]
        note = Markup('<p class="text-muted">%s</p>') % _(
            'Theo mẫu B02-DN Phụ lục IV Thông tư 99/2025/TT-BTC. Chỉ tiêu 21 (bất động sản đầu tư), 24 (chi phí đi vay) và 70 '
            '(lãi cơ bản trên cổ phiếu) cần sổ chi tiết riêng, hiện để trống. Chi phí 621, 622, 627 chỉ lên báo cáo sau khi '
            'kết chuyển sang 154 và tính giá vốn 632.')
        return table([_('Chỉ tiêu'), _('Mã số'), _('Thuyết minh'), _('Năm nay'), _('Năm trước')], rows) + note
