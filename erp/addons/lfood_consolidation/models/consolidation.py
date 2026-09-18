"""Giao dịch nội bộ và báo cáo hợp nhất hai pháp nhân (KT18, BC09).

Văn phòng và Nhà máy là hai pháp nhân, mỗi bên lập báo cáo tài chính riêng. Báo cáo này là báo cáo quản trị cộng hai bên
rồi loại trừ phần nội bộ, cho ban giám đốc thấy số liệu như một doanh nghiệp:
- công nợ nội bộ: phải thu của bên bán với đối tượng là bên kia và phải trả của bên mua với đối tượng là bên kia;
  hai số phải khớp, lệch thì cảnh báo và chỉ loại trừ phần khớp;
- doanh thu bán nội bộ trong kỳ (hóa đơn bên bán ghi cho bên kia, trừ giảm trừ) loại khỏi doanh thu và giá vốn;
- lãi chưa thực hiện: hàng mua nội bộ bên mua còn tồn, tính theo lô bằng số lượng tồn x (giá chuyển - giá vốn
  bên bán); số cuối kỳ giảm hàng tồn kho và lợi nhuận chưa phân phối, phần tăng trong kỳ ghi tăng giá vốn.
Không phải báo cáo tài chính hợp nhất theo chuẩn mực (hai công ty không có quan hệ công ty mẹ, con trong hệ thống).
"""
from datetime import timedelta

from markupsafe import Markup

from odoo import fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_ledger.wizards import b01
from odoo.addons.lfood_ledger.wizards.reports import money, table
from odoo.addons.lfood_voucher.models.tools import vnd

B02_LINES = [('01', 'Doanh thu bán hàng và cung cấp dịch vụ'), ('02', 'Các khoản giảm trừ doanh thu'),
             ('10', 'Doanh thu thuần'), ('11', 'Giá vốn hàng bán'), ('20', 'Lợi nhuận gộp'),
             ('22', 'Doanh thu hoạt động tài chính'), ('23', 'Chi phí tài chính'), ('25', 'Chi phí bán hàng'),
             ('26', 'Chi phí quản lý doanh nghiệp'), ('30', 'Lợi nhuận thuần từ hoạt động kinh doanh'),
             ('40', 'Lợi nhuận khác'), ('50', 'Tổng lợi nhuận kế toán trước thuế')]
B01_KEYS = [('131', 'Phải thu ngắn hạn của khách hàng'), ('141', 'Hàng tồn kho'), ('100', 'Tài sản ngắn hạn'),
            ('280', 'Tổng cộng tài sản'), ('311', 'Phải trả người bán ngắn hạn'), ('300', 'Nợ phải trả'),
            ('400', 'Vốn chủ sở hữu'), ('440', 'Tổng cộng nguồn vốn')]


class LfoodConsolidationReport(models.TransientModel):
    _name = 'lfood.consolidation.report'
    _description = 'Báo cáo hợp nhất hai pháp nhân'

    company_a_id = fields.Many2one('res.company', 'Pháp nhân thứ nhất', required=True,
                                   default=lambda s: s.env.ref('base.main_company'))
    company_b_id = fields.Many2one('res.company', 'Pháp nhân thứ hai', required=True,
                                   default=lambda s: s.env.ref('lfood_base.company_factory', raise_if_not_found=False))
    date_from = fields.Date('Từ ngày', required=True)
    date_to = fields.Date('Đến ngày', required=True)
    report_html = fields.Html('Báo cáo', readonly=True, sanitize=False)

    # ------------------------------------------------------------ số liệu
    def _ledger(self, company):
        return self.env['lfood.ledger.report'].sudo().new({
            'company_id': company.id, 'report': 'b01', 'date_from': self.date_from, 'date_to': self.date_to})

    def _partner_rows(self, company, before):
        """[(mã TK, kỳ hạn, tính chất, đối tượng, số dư)] trước ngày `before`."""
        self.env['lfood.move.line'].flush_model()
        self.env.cr.execute("""
            SELECT a.code, a.bs_term, a.nature, l.partner_id, SUM(COALESCE(l.balance, 0))
            FROM lfood_move_line l JOIN lfood_account a ON a.id = l.account_id
            WHERE l.company_id = %s AND l.state = 'posted' AND l.date < %s
            GROUP BY a.code, a.bs_term, a.nature, l.partner_id""", (company.id, before))
        return self.env.cr.fetchall()

    def _ic_balance(self, rows, other, prefix):
        return round(sum(r[4] for r in rows if r[3] == other.partner_id.id and r[0].startswith(prefix)))

    def _ic_sales(self, seller, buyer):
        invs = self.env['lfood.sale.invoice'].sudo().search([
            ('company_id', '=', seller.id), ('partner_id', '=', buyer.partner_id.id), ('state', '=', 'posted'),
            ('date', '>=', self.date_from), ('date', '<=', self.date_to)])
        return round(sum(i.amount_untaxed * (1 if i.kind == 'invoice' else -1) for i in invs))

    def _unrealized(self, seller, buyer, upto):
        """Lãi chưa thực hiện trong hàng bên mua còn tồn cuối kỳ (theo lô của các lần bán nội bộ)."""
        Val = self.env['lfood.stock.valuation'].sudo()
        transfers = self.env['lfood.intercompany.transfer'].sudo().search([
            ('company_id', '=', seller.id), ('dest_company_id', '=', buyer.id), ('state', '=', 'done'),
            ('date', '<=', upto)])
        total, done = 0.0, set()
        for t in transfers:
            outs = Val.search([('picking_id', 'in', t.sale_invoice_id.picking_ids.filtered(lambda p: p.kind == 'out').ids)])
            for v in outs:
                key = (v.product_id.id, v.lot_id.id)
                if key in done or not v.qty:
                    continue
                done.add(key)
                seller_unit = v.value / v.qty
                price = t.line_ids.filtered(lambda l: l.product_id == v.product_id)[:1].price_unit
                self.env['lfood.stock.valuation'].flush_model()
                self.env.cr.execute("""
                    SELECT COALESCE(SUM(qty), 0) FROM lfood_stock_valuation
                    WHERE company_id = %s AND product_id = %s AND lot_id IS NOT DISTINCT FROM %s AND date <= %s""",
                                    (buyer.id, v.product_id.id, v.lot_id.id or None, upto))
                on_hand = self.env.cr.fetchone()[0]
                total += max(on_hand, 0) * (price - seller_unit)
        return round(total)

    def _compute_data(self):
        self.ensure_one()
        a, b = self.company_a_id, self.company_b_id
        if a == b:
            raise UserError(_('Chọn hai pháp nhân khác nhau.'))
        before = self.date_to + timedelta(days=1)
        rows = {a: self._partner_rows(a, before), b: self._partner_rows(b, before)}
        pairs = [(a, b), (b, a)]
        elim = {'recv': 0, 'warn': []}
        drop = {a: {}, b: {}}  # {(mã TK, đối tượng): số loại trừ}
        for x, y in pairs:
            recv = self._ic_balance(rows[x], y, '131')
            pay = -self._ic_balance(rows[y], x, '331')
            matched = min(recv, pay) if recv > 0 and pay > 0 else 0
            if recv != pay:
                elim['warn'].append(_('Phải thu của %s với %s là %s, phải trả của %s với %s là %s: lệch %s, chỉ loại trừ %s.') % (
                    x.name, y.name, vnd(recv), y.name, x.name, vnd(pay), vnd(recv - pay), vnd(matched)))
            elim['recv'] += matched
            drop[x][('131', y.partner_id.id)] = matched
            drop[y][('331', x.partner_id.id)] = -matched
        combined = []
        for comp in (a, b):
            left = dict(drop[comp])
            for code, term, nature, partner, bal in rows[comp]:
                for (prefix, pid), amt in list(left.items()):
                    if amt and pid == partner and code.startswith(prefix):
                        take = min(amt, bal) if amt > 0 else max(amt, bal)
                        bal -= take
                        left[(prefix, pid)] = amt - take
                combined.append((code, term, nature, bal))
        sales = self._ic_sales(a, b) + self._ic_sales(b, a)
        up = self._unrealized(a, b, self.date_to) + self._unrealized(b, a, self.date_to)
        opening = self.date_from - timedelta(days=1)
        up_change = up - self._unrealized(a, b, opening) - self._unrealized(b, a, opening)
        Acc = self.env['lfood.account']
        inv_acc, re_acc = Acc.by_code('156'), Acc.by_code('4212')
        combined += [('156', inv_acc.bs_term, inv_acc.nature, -up), ('4212', re_acc.bs_term, re_acc.nature, up)]
        la, lb = self._ledger(a), self._ledger(b)
        bs = {'a': la._b01_values(before)[0], 'b': lb._b01_values(before)[0], 'c': b01.compute(combined)}
        pl_a, pl_b = la._b02_values(self.date_from, self.date_to), lb._b02_values(self.date_from, self.date_to)
        pl = {k: (pl_a.get(k) or 0) + (pl_b.get(k) or 0) for k in pl_a}
        pl['01'] -= sales
        pl['11'] -= sales - up_change
        pl['10'] = pl['01'] - pl['02']
        pl['20'] = pl['10'] - pl['11']
        pl['30'] = pl['20'] + (pl['21'] or 0) + pl['22'] - (pl['23'] + pl['25'] + pl['26'])
        pl['50'] = pl['30'] + pl['40']
        return {'bs': bs, 'pl': {'a': pl_a, 'b': pl_b, 'c': pl}, 'sales': sales, 'up': up, 'up_change': up_change, 'recv': elim['recv'],
                'warn': elim['warn']}

    def _ic_list(self):
        """Đối chiếu từng lần bán nội bộ: hóa đơn bên bán và phiếu nhập bên mua."""
        out = []
        for t in self.env['lfood.intercompany.transfer'].sudo().search([
                ('company_id', 'in', (self.company_a_id | self.company_b_id).ids), ('state', '=', 'done'),
                ('date', '>=', self.date_from), ('date', '<=', self.date_to)], order='date'):
            inv, pk = t.sale_invoice_id, t.in_picking_id
            ok = round(inv.amount_untaxed) == round(pk.amount) and round(inv.amount_tax) == round(pk.amount_tax)
            out.append((t, inv, pk, ok))
        return out

    def action_compute(self):
        for rec in self:
            d = rec._compute_data()
            na, nb = rec.company_a_id.name, rec.company_b_id.name
            head = [_('Chỉ tiêu'), _('Mã số'), na, nb, _('Loại trừ'), _('Hợp nhất')]
            pl_rows = []
            for code, label in B02_LINES:
                a, b, c = (d['pl'][k].get(code) or 0 for k in ('a', 'b', 'c'))
                pl_rows.append(([label, code, money(a), money(b), money(c - a - b), money(c)], code in ('10', '20', '50'), 2))
            bs_rows = []
            for code, label in B01_KEYS:
                a, b, c = (d['bs'][k].get(code) or 0 for k in ('a', 'b', 'c'))
                bs_rows.append(([label, code, money(a), money(b), money(c - a - b), money(c)], code in ('280', '440'), 2))
            ic_rows = [([t.name, t.date.strftime('%d/%m/%Y'), t.company_id.name, t.dest_company_id.name,
                         inv.invoice_number or '', money(inv.amount_untaxed), money(pk.amount),
                         _('Khớp') if ok else _('Lệch')], False, 5) for t, inv, pk, ok in rec._ic_list()]
            warn = Markup('').join(Markup('<div class="alert alert-warning">%s</div>') % w for w in d['warn'])
            summary = Markup('<p>%s</p>') % (_('Loại trừ: công nợ nội bộ %s; doanh thu bán nội bộ %s; lãi chưa thực hiện trong tồn kho cuối kỳ %s (tăng trong kỳ %s).')
                                              % (vnd(d['recv']), vnd(d['sales']), vnd(d['up']), vnd(d['up_change'])))
            rec.report_html = (warn + summary
                               + Markup('<h4>%s</h4>') % _('Kết quả kinh doanh (B02)') + table(head, pl_rows)
                               + Markup('<h4>%s</h4>') % _('Tình hình tài chính (B01, chỉ tiêu chính)') + table(head, bs_rows)
                               + Markup('<h4>%s</h4>') % _('Đối chiếu mua bán nội bộ trong kỳ')
                               + table([_('Chứng từ'), _('Ngày'), _('Bên bán'), _('Bên mua'), _('Số hóa đơn'),
                                        _('Hóa đơn bên bán'), _('Phiếu nhập bên mua'), _('Kết quả')], ic_rows)
                               + Markup('<p class="text-muted">%s</p>') % _(
                                   'Báo cáo quản trị cộng hai pháp nhân sau loại trừ nội bộ, không thay thế báo cáo tài chính của '
                                   'từng pháp nhân. Chưa kết chuyển cuối kỳ thì tổng tài sản có thể khác tổng nguồn vốn.'))
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form',
                'target': 'new'}
