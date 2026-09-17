import calendar
from datetime import date

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd
from . import form01

GROUPS = [('none', 'Không chịu thuế'), ('0', 'Thuế suất 0%'), ('5', 'Thuế suất 5%'), ('10', 'Thuế suất 10% (gồm giảm còn 8%)'),
          ('32a', 'Không phải kê khai, tính nộp thuế'), ('32b', 'Không tính vào giá tính thuế'),
          ('34a', 'Không thuộc phạm vi thuế GTGT')]


def money(v):
    v = round(v or 0)
    return vnd(v) if v >= 0 else '(%s)' % vnd(-v)


class ResCompany(models.Model):
    _inherit = 'res.company'

    lfood_vat_period = fields.Selection([('month', 'Theo tháng'), ('quarter', 'Theo quý')], 'Kỳ khai thuế GTGT',
                                        default='month', required=True,
                                        help='Khai theo quý nếu tổng doanh thu năm trước từ 50 tỷ đồng trở xuống, theo quy định quản lý thuế')


class LfoodVatReturn(models.Model):
    _name = 'lfood.vat.return'
    _description = 'Tờ khai thuế GTGT 01/GTGT'
    _order = 'date_from desc, id desc'

    name = fields.Char('Tờ khai', compute='_compute_period', store=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    period_type = fields.Selection([('month', 'Tháng'), ('quarter', 'Quý')], 'Kỳ', required=True,
                                   default=lambda s: s.env.company.lfood_vat_period)
    year = fields.Integer('Năm', required=True, default=lambda s: fields.Date.context_today(s).year)
    month = fields.Integer('Tháng', default=lambda s: fields.Date.context_today(s).month)
    quarter = fields.Integer('Quý', default=lambda s: (fields.Date.context_today(s).month - 1) // 3 + 1)
    date_from = fields.Date('Từ ngày', compute='_compute_period', store=True)
    date_to = fields.Date('Đến ngày', compute='_compute_period', store=True)
    due_date = fields.Date('Hạn nộp', compute='_compute_period', store=True)
    state = fields.Selection([('draft', 'Nháp'), ('confirmed', 'Đã xác nhận')], 'Trạng thái', default='draft',
                             readonly=True, copy=False, index=True)
    line_ids = fields.One2many('lfood.vat.return.line', 'return_id', 'Bảng kê')
    purchase_line_ids = fields.One2many('lfood.vat.return.line', 'return_id', 'Bảng kê mua vào', domain=[('kind', '=', 'in')])
    sale_line_ids = fields.One2many('lfood.vat.return.line', 'return_id', 'Bảng kê bán ra', domain=[('kind', '=', 'out')])
    adj_37 = fields.Float('[37] Điều chỉnh giảm', digits=(16, 0))
    adj_38 = fields.Float('[38] Điều chỉnh tăng', digits=(16, 0))
    adj_39a = fields.Float('[39a] Thuế nhận bàn giao được khấu trừ', digits=(16, 0))
    adj_40b = fields.Float('[40b] Thuế dự án đầu tư bù trừ', digits=(16, 0))
    adj_42 = fields.Float('[42] Đề nghị hoàn', digits=(16, 0))
    carry_in = fields.Float('[22] Kỳ trước chuyển sang', digits=(16, 0), readonly=True)
    values = fields.Json('Số liệu đã xác nhận', readonly=True, copy=False)
    tax_payable = fields.Float('[40] Còn phải nộp', digits=(16, 0), compute='_compute_summary')
    carry_out = fields.Float('[43] Chuyển kỳ sau', digits=(16, 0), compute='_compute_summary')
    form_html = fields.Html('Nội dung tờ khai', compute='_compute_html', sanitize=False)
    reduction_html = fields.Html('Phụ lục giảm thuế', compute='_compute_html', sanitize=False)
    confirmed_by = fields.Many2one('res.users', 'Người xác nhận', readonly=True, copy=False)
    confirmed_on = fields.Datetime('Thời điểm xác nhận', readonly=True, copy=False)

    @api.depends('period_type', 'year', 'month', 'quarter')
    def _compute_period(self):
        for rec in self:
            if rec.period_type == 'quarter':
                q = min(max(rec.quarter or 1, 1), 4)
                m1, m2 = 3 * q - 2, 3 * q
                rec.name = _('01/GTGT quý %s/%s') % (q, rec.year)
                nm = m2 % 12 + 1
                ny = rec.year + (1 if m2 == 12 else 0)
                due = date(ny, nm, calendar.monthrange(ny, nm)[1])
            else:
                m1 = m2 = min(max(rec.month or 1, 1), 12)
                rec.name = _('01/GTGT tháng %02d/%s') % (m1, rec.year)
                ny, nm = (rec.year + 1, 1) if m1 == 12 else (rec.year, m1 + 1)
                due = date(ny, nm, 20)
            rec.date_from = date(rec.year, m1, 1)
            rec.date_to = date(rec.year, m2, calendar.monthrange(rec.year, m2)[1])
            rec.due_date = due

    def _figures(self):
        self.ensure_one()
        if self.state == 'confirmed' and self.values:
            return self.values
        purchases = [(l.base, l.tax, l.deductible, l.imported) for l in self.purchase_line_ids]
        sales = [(l.base, l.tax, l.group) for l in self.sale_line_ids]
        return form01.compute(purchases, sales, carry=self.carry_in, adjust={
            '37': self.adj_37, '38': self.adj_38, '39a': self.adj_39a, '40b': self.adj_40b, '42': self.adj_42})

    @api.depends('line_ids.base', 'line_ids.tax', 'line_ids.deductible', 'line_ids.group', 'carry_in',
                 'adj_37', 'adj_38', 'adj_39a', 'adj_40b', 'adj_42', 'values')
    def _compute_summary(self):
        for rec in self:
            v = rec._figures()
            rec.tax_payable = v['40']
            rec.carry_out = v['43']

    @api.depends('line_ids.base', 'line_ids.tax', 'line_ids.deductible', 'line_ids.group', 'carry_in',
                 'adj_37', 'adj_38', 'adj_39a', 'adj_40b', 'adj_42', 'values')
    def _compute_html(self):
        for rec in self:
            v = rec._figures()
            rows = Markup('').join(
                Markup('<tr><td>[%s]</td><td>%s</td><td style="text-align:right">%s</td></tr>') % (code, label, money(v.get(code)))
                for code, label in form01.LABELS if code != '21')
            head = Markup('<p>Mẫu 01/GTGT theo Thông tư 89/2026/TT-BTC · %s · từ %s đến %s · hạn nộp %s</p>') % (
                rec.company_id.name, rec.date_from.strftime('%d/%m/%Y') if rec.date_from else '',
                rec.date_to.strftime('%d/%m/%Y') if rec.date_to else '', rec.due_date.strftime('%d/%m/%Y') if rec.due_date else '')
            empty = Markup('<p><b>[21] Không phát sinh hoạt động mua, bán trong kỳ</b></p>') if v.get('21') else Markup('')
            rec.form_html = head + empty + Markup('<div class="o_lfood_changes"><table><tr><th>Mã</th><th>Chỉ tiêu</th><th>Số tiền</th></tr>%s</table></div>') % rows
            reduced = rec.sale_line_ids.filtered('reduced')
            if reduced:
                body = Markup('').join(
                    Markup('<tr><td>%s</td><td>%s</td><td style="text-align:right">%s</td><td>10%%</td><td>80%%</td>'
                           '<td style="text-align:right">%s</td></tr>') % (escape(l.ref or ''), escape(l.name or ''), money(l.base),
                                                                           money(round(l.base * 0.02)))
                    for l in reduced)
                total = sum(round(l.base * 0.02) for l in reduced)
                rec.reduction_html = Markup(
                    '<p>Phụ lục giảm thuế GTGT theo Nghị định 174/2025/NĐ-CP (Nghị quyết 204/2025/QH15)</p>'
                    '<div class="o_lfood_changes"><table><tr><th>Hóa đơn</th><th>Tên hàng hóa, dịch vụ</th><th>Giá trị chưa thuế</th>'
                    '<th>Thuế suất quy định</th><th>Tỷ lệ áp dụng</th><th>Thuế GTGT được giảm</th></tr>%s'
                    '<tr><td></td><td><b>Cộng</b></td><td></td><td></td><td></td><td style="text-align:right"><b>%s</b></td></tr></table></div>') % (body, money(total))
            else:
                rec.reduction_html = Markup('<p>Kỳ này không có hàng hóa, dịch vụ bán ra được giảm thuế GTGT.</p>')

    # ------------------------------------------------------------ lấy dữ liệu
    def _check_threshold(self, voucher):
        limit = self.env['lfood.legal.param'].get_value('NGUONG_TT_KHONG_TIEN_MAT', voucher.accounting_date, default=5000000)
        if voucher.report_amount_total < limit:
            return True, ''
        Payment = self.env['lfood.payment'].sudo()
        cash = Payment.search_count([('voucher_id', '=', voucher.id), ('state', '=', 'posted'), ('method', '=', 'cash')])
        if cash or (voucher.payment_state == 'paid_now' and voucher.payment_method == 'cash'):
            return False, _('Hóa đơn từ %s đồng thanh toán bằng tiền mặt: không đủ điều kiện khấu trừ') % vnd(limit)
        if voucher.payment_state == 'unpaid':
            return True, _('Chưa thanh toán: được khấu trừ; nếu sau đó trả tiền mặt thì điều chỉnh giảm vào [37]')
        return True, ''

    def _purchase_lines(self):
        vouchers = self.env['lfood.service.voucher'].sudo().search([
            ('company_id', '=', self.company_id.id), ('state', 'in', ('posted', 'editing')),
            ('report_version_id.accounting_date', '>=', self.date_from), ('report_version_id.accounting_date', '<=', self.date_to)])
        vals = []
        for v in vouchers:
            version = v.report_version_id
            by_rate = {}
            for l in version.line_ids:
                key = l.vat_rate_id
                base, tax = by_rate.get(key, (0, 0))
                by_rate[key] = (base + l.amount, tax + l.vat_amount)
            ok, reason = self._check_threshold(v)
            if v.invoice_mode != 'with':
                ok, reason = False, _('Chưa có hóa đơn GTGT hợp pháp')
            for rate, (base, tax) in by_rate.items():
                vals.append({'kind': 'in', 'date': version.document_date or version.accounting_date, 'ref': version.invoice_ref or v.name,
                             'partner_id': version.partner_id.id, 'name': version.memo or v.name, 'base': base, 'tax': tax,
                             'rate': rate.rate, 'rate_name': rate.name or _('Không có thuế'),
                             'deductible': ok and tax > 0, 'reason': reason if tax else _('Không có thuế GTGT'),
                             'source_model': v._name, 'source_id': v.id})
        return vals

    def _sale_lines(self):
        """Doanh thu lấy từ sổ: bút toán ghi Có 511, 711 kèm thuế Có 33311 trong cùng bút toán.
        Khi có phân hệ Bán hàng, hóa đơn bán ra sẽ thay nguồn này."""
        self.env['lfood.move.line'].flush_model()
        self.env.cr.execute("""
            SELECT m.id, m.ref, m.memo, m.date,
                   SUM(CASE WHEN l.account_code LIKE '511%%' OR l.account_code LIKE '711%%' THEN COALESCE(l.credit, 0) - COALESCE(l.debit, 0) ELSE 0 END),
                   SUM(CASE WHEN l.account_code LIKE '33311%%' THEN COALESCE(l.credit, 0) - COALESCE(l.debit, 0) ELSE 0 END),
                   MAX(CASE WHEN l.account_code LIKE '131%%' THEN l.partner_id END)
            FROM lfood_move m JOIN lfood_move_line l ON l.move_id = m.id
            WHERE m.company_id = %s AND m.state = 'posted' AND m.journal <> 'closing' AND m.date BETWEEN %s AND %s
            GROUP BY m.id, m.ref, m.memo, m.date
        """, (self.company_id.id, self.date_from, self.date_to))
        vals = []
        for move_id, ref, memo, d, base, tax, partner in self.env.cr.fetchall():
            if not round(base) and not round(tax):
                continue
            ratio = (tax / base * 100) if base else 0
            if not round(tax):
                group, reduced, rate = 'none', False, 0
            elif abs(ratio - 5) < 0.6:
                group, reduced, rate = '5', False, 5
            elif abs(ratio - 8) < 0.6:
                group, reduced, rate = '10', True, 8
            else:
                group, reduced, rate = '10', False, 10
            vals.append({'kind': 'out', 'date': d, 'ref': ref, 'name': memo, 'partner_id': partner, 'base': base, 'tax': tax,
                         'rate': rate, 'rate_name': '%s%%' % rate if round(tax) else _('Không chịu thuế'),
                         'group': group, 'reduced': reduced, 'source_model': 'lfood.move', 'source_id': move_id,
                         'reason': _('Không có thuế: kiểm tra là không chịu thuế hay thuế suất 0% rồi sửa cột Nhóm') if group == 'none' else ''})
        return vals

    def _previous(self):
        return self.search([('company_id', '=', self.company_id.id), ('state', '=', 'confirmed'),
                            ('date_to', '<', self.date_from)], order='date_to desc', limit=1)

    def action_fetch(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được lập tờ khai thuế.'))
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Tờ khai đã xác nhận, hủy xác nhận trước khi lấy lại dữ liệu.'))
            dup = self.search([('company_id', '=', rec.company_id.id), ('date_from', '=', rec.date_from), ('id', '!=', rec.id)], limit=1)
            if dup:
                raise UserError(_('Đã có %s cho kỳ này.') % dup.name)
            rec.line_ids.unlink()
            rec.carry_in = rec._previous().values.get('43', 0) if rec._previous() else 0
            self.env['lfood.vat.return.line'].create([dict(v, return_id=rec.id) for v in rec._purchase_lines() + rec._sale_lines()])
        return True

    def action_confirm(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được xác nhận tờ khai thuế.'))
        Move, Acc = self.env['lfood.move'], self.env['lfood.account']
        for rec in self.filtered(lambda r: r.state == 'draft'):
            earlier = self.search([('company_id', '=', rec.company_id.id), ('state', '=', 'draft'), ('date_to', '<', rec.date_from)], limit=1)
            if earlier:
                raise UserError(_('Còn %s chưa xác nhận. Xác nhận các kỳ trước trước.') % earlier.name)
            v = rec._figures()
            rec.write({'values': v, 'state': 'confirmed', 'confirmed_by': self.env.uid, 'confirmed_on': fields.Datetime.now()})
            # bù trừ thuế GTGT đầu vào được khấu trừ với thuế đầu ra: Nợ 33311 / Có 1331, 1332
            offset = v['35'] - v['40a']
            if offset > 0:
                self.env['lfood.move.line'].flush_model()
                bal = {}
                for code in ('1331', '1332'):
                    self.env.cr.execute("""SELECT COALESCE(SUM(balance), 0) FROM lfood_move_line
                                           WHERE company_id = %s AND state = 'posted' AND account_code = %s AND date <= %s""",
                                        (rec.company_id.id, code, rec.date_to))
                    bal[code] = max(round(self.env.cr.fetchone()[0]), 0)
                c1331 = min(offset, bal['1331'])
                c1332 = min(offset - c1331, bal['1332'])
                label = _('Khấu trừ thuế GTGT %s') % rec.name
                lines = [('33311', c1331 + c1332, 0, None, label, None), ('1331', 0, c1331, None, label, None),
                         ('1332', 0, c1332, None, label, None)]
                if c1331 + c1332:
                    Move._create_from_source(rec, 'general', rec.date_to, lines, memo=label, key='offset', ref=rec.name)
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Xác nhận %s: thuế đầu ra %s, được khấu trừ %s, còn phải nộp %s, chuyển kỳ sau %s')
                % (rec.name, vnd(v['35']), vnd(v['25']), vnd(v['40']), vnd(v['43'])))
        return True

    def action_reset(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được hủy xác nhận tờ khai thuế.'))
        for rec in self.filtered(lambda r: r.state == 'confirmed'):
            later = self.search([('company_id', '=', rec.company_id.id), ('state', '=', 'confirmed'), ('date_from', '>', rec.date_to)], limit=1)
            if later:
                raise UserError(_('%s đã xác nhận và dùng số chuyển kỳ của tờ khai này. Hủy từ kỳ mới nhất trở về.') % later.name)
            self.env['lfood.move']._active_for(rec)._reverse(memo=_('Hủy xác nhận %s') % rec.name)
            rec.write({'state': 'draft', 'values': False})
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=rec.name,
                                                      company_id=rec.company_id.id, summary=_('Hủy xác nhận %s') % rec.name)
        return True

    def write(self, vals):
        if self.filtered(lambda r: r.state == 'confirmed') and set(vals) - {'state', 'values', 'confirmed_by', 'confirmed_on'}:
            raise UserError(_('Tờ khai đã xác nhận không sửa được.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda r: r.state == 'confirmed'):
            raise UserError(_('Tờ khai đã xác nhận không xóa được.'))
        return super().unlink()


class LfoodVatReturnLine(models.Model):
    _name = 'lfood.vat.return.line'
    _description = 'Dòng bảng kê hóa đơn'
    _order = 'kind, date, id'

    return_id = fields.Many2one('lfood.vat.return', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='return_id.company_id', store=True)
    kind = fields.Selection([('in', 'Mua vào'), ('out', 'Bán ra')], required=True)
    date = fields.Date('Ngày hóa đơn')
    ref = fields.Char('Số hóa đơn')
    partner_id = fields.Many2one('res.partner', 'Người bán / người mua')
    partner_vat = fields.Char(related='partner_id.vat', string='Mã số thuế')
    name = fields.Char('Nội dung')
    base = fields.Float('Giá trị chưa thuế', digits=(16, 0))
    rate = fields.Float('Thuế suất', digits=(5, 2))
    rate_name = fields.Char('Thuế suất hiển thị')
    tax = fields.Float('Thuế GTGT', digits=(16, 0))
    deductible = fields.Boolean('Được khấu trừ')
    imported = fields.Boolean('Hàng nhập khẩu')
    group = fields.Selection(GROUPS, 'Nhóm trên tờ khai')
    reduced = fields.Boolean('Được giảm thuế (8%)')
    reason = fields.Char('Ghi chú kiểm tra')
    source_model = fields.Char('Nguồn')
    source_id = fields.Integer('Mã nguồn')

    def write(self, vals):
        if self.filtered(lambda l: l.return_id.state == 'confirmed'):
            raise UserError(_('Tờ khai đã xác nhận không sửa được bảng kê.'))
        return super().write(vals)
