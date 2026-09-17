"""Giao dịch liên kết (THUE11) theo Nghị định 255/2026/NĐ-CP (thay Nghị định 132/2020 và 20/2025, áp dụng từ kỳ
tính thuế 2026).

- Đánh dấu bên có quan hệ liên kết trên danh mục đối tượng, ghi căn cứ, tình trạng thuế TNDN của bên đó.
- Bảng tổng hợp giao dịch với bên liên kết trong năm để kê khai phụ lục thông tin giao dịch liên kết.
- Khống chế chi phí lãi vay 30% theo khoản 3 Điều 16; phần vượt chuyển kỳ sau tối đa 5 năm. Lãi tiền gửi, lãi cho vay
  lấy từ phiếu thu được đánh dấu là lãi (không lẫn chênh lệch tỷ giá ghi vào 515).
- Khoản vay ngoài tổ chức tín dụng có lãi vượt mức Bộ luật Dân sự: đưa phần lãi không được trừ vào điều chỉnh tăng.
- Đánh giá miễn kê khai, miễn lập hồ sơ xác định giá; bản nháp số liệu cho hồ sơ xác định giá.
"""
from markupsafe import escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd
from .related_calc import interest_cap, carry_pool, tp_exemption

DEPRECIATION_ACCOUNTS = ('6234', '6274', '6414', '6424')
TP_STATES = [('none', 'Không có giao dịch liên kết'), ('full', 'Miễn kê khai và miễn lập hồ sơ'),
             ('doc', 'Phải kê khai, được miễn lập hồ sơ xác định giá'),
             ('required', 'Phải kê khai và lập hồ sơ xác định giá')]
SECTORS = [('distribution', 'Phân phối'), ('manufacturing', 'Sản xuất'), ('processing', 'Gia công')]
LIMIT_PARAMS = {'revenue_small': ('GDLK_MIEN_HS_DOANH_THU', 50e9), 'related_small': ('GDLK_MIEN_HS_GIA_TRI_GD', 30e9),
                'revenue_margin': ('GDLK_MIEN_HS_DOANH_THU_TSLN', 500e9),
                'margin_distribution': ('GDLK_TSLN_PHAN_PHOI', 5), 'margin_manufacturing': ('GDLK_TSLN_SAN_XUAT', 10),
                'margin_processing': ('GDLK_TSLN_GIA_CONG', 15)}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    lfood_related = fields.Boolean('Bên có quan hệ liên kết')
    lfood_related_basis = fields.Char('Căn cứ quan hệ liên kết',
                                      help='Ví dụ: cùng một chủ sở hữu nắm giữ từ 25% vốn góp của hai doanh nghiệp')
    lfood_related_domestic = fields.Boolean('Là đối tượng nộp thuế TNDN tại Việt Nam')
    lfood_related_rate = fields.Float('Thuế suất TNDN của bên liên kết (%)', digits=(5, 2))
    lfood_related_incentive = fields.Boolean('Bên liên kết đang được ưu đãi thuế TNDN')


class LfoodPayment(models.Model):
    _inherit = 'lfood.payment'

    lfood_interest_income = fields.Boolean('Là lãi tiền gửi, lãi cho vay', compute='_compute_interest_income',
                                           store=True, readonly=False,
                                           help='Dùng để trừ khỏi chi phí lãi vay khi xét khống chế lãi vay')

    @api.depends('kind', 'counterpart_account')
    def _compute_interest_income(self):
        for rec in self:
            rec.lfood_interest_income = rec.kind == 'in' and (rec.counterpart_account or '').startswith('515')


class LfoodCitAdjust(models.Model):
    _inherit = 'lfood.cit.adjust'

    source = fields.Selection(selection_add=[('interest_cap', 'Khống chế lãi vay 30%'),
                                             ('interest_carry', 'Lãi vay vượt mức năm trước được chuyển'),
                                             ('loan_rate', 'Lãi vay vượt mức Bộ luật Dân sự')],
                              ondelete={'interest_cap': 'cascade', 'interest_carry': 'cascade', 'loan_rate': 'cascade'})


class LfoodCitFinalization(models.Model):
    _inherit = 'lfood.cit.finalization'

    has_related = fields.Boolean('Có giao dịch liên kết', readonly=True, copy=False)
    ic_op_profit = fields.Float('Lợi nhuận thuần từ hoạt động kinh doanh', digits=(16, 0), copy=False)
    ic_interest = fields.Float('Chi phí lãi vay', digits=(16, 0), copy=False)
    ic_interest_income = fields.Float('Lãi tiền gửi, lãi cho vay', digits=(16, 0), copy=False)
    ic_depreciation = fields.Float('Chi phí khấu hao', digits=(16, 0), copy=False)
    ic_cap = fields.Float('Mức khống chế 30%', digits=(16, 0), copy=False, readonly=True)
    ic_excess = fields.Float('Lãi vay vượt mức năm nay', digits=(16, 0), copy=False, readonly=True)
    ic_carry_used = fields.Float('Phần vượt năm trước được trừ năm nay', digits=(16, 0), copy=False, readonly=True)
    tp_sector = fields.Selection(SECTORS, 'Lĩnh vực xét tỷ suất lợi nhuận', default='manufacturing')
    tp_apa = fields.Boolean('Đã có thỏa thuận trước về phương pháp xác định giá (APA)')
    tp_own_incentive = fields.Boolean('Doanh nghiệp đang được ưu đãi thuế TNDN')
    tp_revenue = fields.Float('Tổng doanh thu', digits=(16, 0), copy=False, readonly=True)
    tp_net_revenue = fields.Float('Doanh thu thuần', digits=(16, 0), copy=False, readonly=True)
    tp_margin_profit = fields.Float('Lợi nhuận thuần trước lãi vay và thuế', digits=(16, 0), copy=False, readonly=True)
    tp_related_total = fields.Float('Tổng giá trị giao dịch liên kết', digits=(16, 0), copy=False, readonly=True)
    tp_status = fields.Selection(TP_STATES, 'Nghĩa vụ giao dịch liên kết', copy=False, readonly=True)
    tp_reason = fields.Text('Căn cứ đánh giá', copy=False, readonly=True)
    related_html = fields.Html('Giao dịch với bên liên kết', compute='_compute_related_html', sanitize=False)
    tp_doc_html = fields.Html('Bản nháp số liệu hồ sơ xác định giá', compute='_compute_related_html', sanitize=False)

    # ------------------------------------------------------------ số liệu
    def _ledger_net(self, prefix):
        report = self.env['lfood.ledger.report'].sudo().new({'company_id': self.company_id.id, 'report': 'b02',
                                                              'date_from': self.date_from, 'date_to': self.date_to})
        return report._net(prefix, self.date_from, self.date_to)

    def _purchases_untaxed(self, partner):
        """Phát sinh Có 331 với đối tượng, trừ phần thuế GTGT đầu vào của cùng bút toán."""
        ML = self.env['lfood.move.line'].sudo()
        lines = ML.search([('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
                           ('partner_id', '=', partner.id), ('account_code', '=like', '331%'),
                           ('date', '>=', self.date_from), ('date', '<=', self.date_to)])
        total = 0
        for move in lines.mapped('move_id'):
            credit = sum(lines.filtered(lambda l: l.move_id == move).mapped('credit'))
            move_payable = sum(move.line_ids.filtered(lambda l: l.account_code.startswith('331')).mapped('credit'))
            tax = sum(move.line_ids.filtered(lambda l: l.account_code.startswith('133')).mapped('debit'))
            total += credit - (tax * credit / move_payable if move_payable else 0)
        return round(total)

    def _related_rows(self):
        """[(đối tượng, bán ra, mua vào, vay nhận)] chưa có thuế GTGT, trong năm, với từng bên liên kết."""
        self.ensure_one()
        partners = self.env['res.partner'].sudo().search([('lfood_related', '=', True)])
        ML = self.env['lfood.move.line'].sudo()
        rows = []
        for partner in partners:
            sales = sum(self.env['lfood.sale.invoice'].sudo().search([
                ('company_id', '=', self.company_id.id), ('state', '=', 'posted'), ('partner_id', '=', partner.id),
                ('kind', '=', 'invoice'), ('date', '>=', self.date_from), ('date', '<=', self.date_to)]).mapped('amount_untaxed'))
            purchases = self._purchases_untaxed(partner)
            loans = sum(ML.search([('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
                                   ('partner_id', '=', partner.id), ('account_code', '=like', '3411%'),
                                   ('date', '>=', self.date_from), ('date', '<=', self.date_to)]).mapped('credit'))
            if sales or purchases or loans:
                rows.append((partner, sales, purchases, loans))
        return rows

    def _interest_income(self):
        payments = self.env['lfood.payment'].sudo().search([
            ('company_id', '=', self.company_id.id), ('state', '=', 'posted'), ('kind', '=', 'in'),
            ('lfood_interest_income', '=', True), ('date', '>=', self.date_from), ('date', '<=', self.date_to)])
        return round(sum(payments.mapped('amount')))

    # ------------------------------------------------------------ hiển thị
    @api.depends('year', 'company_id', 'state', 'tp_status', 'ic_cap', 'tp_reason')
    def _compute_related_html(self):
        for rec in self:
            rows = rec._related_rows() if rec.id else []
            body = ''.join('<tr><td>%s</td><td>%s</td><td>%s</td><td class="text-end">%s</td><td class="text-end">%s</td>'
                           '<td class="text-end">%s</td></tr>' % (
                               escape(p.name), escape(p.vat or ''), escape(p.lfood_related_basis or ''),
                               vnd(s), vnd(b), vnd(l))
                           for p, s, b, l in rows)
            table = (
                '<table class="table table-sm"><thead><tr><th>Bên liên kết</th><th>Mã số thuế</th><th>Căn cứ</th>'
                '<th>Bán ra</th><th>Mua vào</th><th>Nhận tiền vay</th></tr></thead><tbody>%s</tbody></table>') % (
                body or '<tr><td colspan="6">Không có giao dịch với bên liên kết</td></tr>')
            rec.related_html = table + (
                '<p class="text-muted">Số liệu chưa có thuế GTGT, gợi ý để kê khai phụ lục thông tin về giao dịch liên kết '
                'theo Nghị định 255/2026/NĐ-CP.</p>')
            company = rec.company_id
            reason = ''.join('<li>%s</li>' % escape(r) for r in (rec.tp_reason or '').splitlines())
            margin = '%.2f%%' % (rec.tp_margin_profit / rec.tp_net_revenue * 100) if rec.tp_net_revenue else ''
            rec.tp_doc_html = (
                '<h3>HỒ SƠ XÁC ĐỊNH GIÁ GIAO DỊCH LIÊN KẾT NĂM %s (BẢN NHÁP SỐ LIỆU)</h3>'
                '<p><b>Kết quả đánh giá:</b> %s</p><ul>%s</ul>'
                '<h4>1. Thông tin người nộp thuế</h4><p>%s, mã số thuế %s, địa chỉ %s.</p>'
                '<p><i>Kế toán bổ sung: cơ cấu tổ chức, quản lý; hoạt động kinh doanh chính; chiến lược kinh doanh; '
                'các thay đổi quan trọng trong năm.</i></p>'
                '<h4>2. Các bên liên kết và giao dịch liên kết</h4>%s'
                '<p><i>Kế toán bổ sung: mô tả từng giao dịch, điều khoản hợp đồng, phân tích chức năng, tài sản, rủi ro '
                'của các bên.</i></p>'
                '<h4>3. Phương pháp xác định giá</h4><p><i>Kế toán hoặc đơn vị tư vấn chọn phương pháp, đối tượng so sánh '
                'độc lập và khoảng giá trị giao dịch độc lập chuẩn.</i></p>'
                '<h4>4. Thông tin tài chính</h4><table class="table table-sm"><tbody>'
                '<tr><td>Tổng doanh thu</td><td class="text-end">%s</td></tr>'
                '<tr><td>Doanh thu thuần</td><td class="text-end">%s</td></tr>'
                '<tr><td>Lợi nhuận thuần trước lãi vay và thuế</td><td class="text-end">%s</td></tr>'
                '<tr><td>Tỷ suất lợi nhuận thuần trước lãi vay và thuế trên doanh thu thuần</td><td class="text-end">%s</td></tr>'
                '<tr><td>Tổng giá trị giao dịch liên kết</td><td class="text-end">%s</td></tr>'
                '<tr><td>Chi phí lãi vay thuần / mức khống chế 30%%</td><td class="text-end">%s / %s</td></tr>'
                '</tbody></table>'
                '<p class="text-muted">Nội dung hồ sơ theo Nghị định 255/2026/NĐ-CP; app chỉ điền phần số liệu có trên sổ, '
                'phần phân tích do kế toán hoặc đơn vị tư vấn hoàn thiện.</p>') % (
                rec.year, dict(TP_STATES).get(rec.tp_status, 'Chưa đánh giá, bấm Lấy số gợi ý'), reason,
                escape(company.name or ''), escape(company.vat or ''), escape(company.street or ''), table,
                vnd(rec.tp_revenue), vnd(rec.tp_net_revenue), vnd(rec.tp_margin_profit), margin,
                vnd(rec.tp_related_total), vnd(rec.ic_interest - rec.ic_interest_income), vnd(rec.ic_cap))

    # ------------------------------------------------------------ tính toán
    def _load_adjustments(self):
        super()._load_adjustments()
        loan_excess = sum(self.env['lfood.loan.accrual'].sudo().search([
            ('company_id', '=', self.company_id.id), ('date_to', '>=', self.date_from),
            ('date_to', '<=', self.date_to)]).mapped('nondeductible'))
        if loan_excess:
            self.env['lfood.cit.adjust'].create({
                'finalization_id': self.id, 'kind': 'increase', 'source': 'loan_rate', 'amount': loan_excess,
                'name': _('Lãi vay của tổ chức, cá nhân không phải tổ chức tín dụng vượt mức Bộ luật Dân sự')})
        accruals = self.env['lfood.loan.accrual'].sudo().search([
            ('company_id', '=', self.company_id.id), ('date_to', '>=', self.date_from), ('date_to', '<=', self.date_to)])
        rows = self._related_rows()
        self.with_context(lfood_cit_system=True).write({
            'has_related': bool(rows),
            'ic_op_profit': round(self._b02()['30']),
            # phần lãi vượt mức Bộ luật Dân sự đã loại riêng, không tính lại vào chi phí lãi vay được xét khống chế
            'ic_interest': round(sum(accruals.mapped('amount'))) - loan_excess,
            'ic_interest_income': self._interest_income(),
            'ic_depreciation': round(sum(self._ledger_net(code) for code in DEPRECIATION_ACCOUNTS)),
        })
        self._apply_interest_cap()
        self._evaluate_tp(rows)

    def _b02(self):
        report = self.env['lfood.ledger.report'].sudo().new({'company_id': self.company_id.id, 'report': 'b02',
                                                              'date_from': self.date_from, 'date_to': self.date_to})
        return report._b02_values(self.date_from, self.date_to)

    def action_recompute_interest_cap(self):
        """Tính lại sau khi kế toán sửa số liệu hoặc thông tin miễn hồ sơ."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ tính lại khi bản quyết toán còn là Nháp.'))
            rec.adjust_line_ids.filtered(lambda l: l.source in ('interest_cap', 'interest_carry')).unlink()
            rec._apply_interest_cap()
            rec._evaluate_tp(rec._related_rows())
        return True

    def _apply_interest_cap(self):
        Param = self.env['lfood.legal.param']
        rate = Param.get_value('KHONG_CHE_LAI_VAY_TY_LE', self.date_to, default=30)
        years = int(Param.get_value('KHONG_CHE_LAI_VAY_SO_NAM', self.date_to, default=5))
        prior = self.search([('company_id', '=', self.company_id.id), ('year', '<', self.year), ('state', '=', 'posted')])
        pool = carry_pool([(p.year, p.ic_excess, p.ic_carry_used) for p in prior], self.year, years)
        if not (self.has_related or pool):
            self.with_context(lfood_cit_system=True).write({'ic_cap': 0, 'ic_excess': 0, 'ic_carry_used': 0})
            return
        net_interest = self.ic_interest - self.ic_interest_income
        cap, excess, room = interest_cap(self.ic_op_profit, net_interest, self.ic_depreciation, rate)
        # ponytail: năm không có giao dịch liên kết thì không phát sinh phần vượt mới, chỉ xét trừ phần chuyển từ năm trước
        excess = excess if self.has_related else 0
        carry_used = min(room, sum(amt for _y, amt in pool))
        self.with_context(lfood_cit_system=True).write({'ic_cap': cap, 'ic_excess': excess, 'ic_carry_used': carry_used})
        Adjust = self.env['lfood.cit.adjust']
        if excess:
            Adjust.create({'finalization_id': self.id, 'kind': 'increase', 'source': 'interest_cap', 'amount': excess,
                           'name': _('Chi phí lãi vay thuần vượt %s%% EBITDA (Nghị định 255/2026/NĐ-CP)') % ('%g' % rate)})
        if carry_used:
            Adjust.create({'finalization_id': self.id, 'kind': 'decrease', 'source': 'interest_carry', 'amount': carry_used,
                           'name': _('Chi phí lãi vay vượt mức các năm trước được trừ năm nay')})

    def _evaluate_tp(self, rows):
        """Doanh thu = 511 - 521 + 515 + 711 trong năm (không tính kết chuyển); tỷ suất = (B02 mã 30 + lãi vay thuần)
        trên doanh thu thuần (B02 mã 10)."""
        Param = self.env['lfood.legal.param']
        limits = {k: Param.get_value(code, self.date_to, default=d) for k, (code, d) in LIMIT_PARAMS.items()}
        b02 = self._b02()
        revenue = round(-self._ledger_net('511') + self._ledger_net('521') - self._ledger_net('515') - self._ledger_net('711'))
        margin_profit = round(b02['30'] + self.ic_interest - self.ic_interest_income)
        related_total = round(sum(s + b + l for _p, s, b, l in rows))
        parties = [(p.name, p.lfood_related_domestic, p.lfood_related_rate, p.lfood_related_incentive) for p, *_x in rows]
        status, reasons = tp_exemption(parties, self.rate, self.tp_own_incentive, revenue, related_total, self.tp_apa,
                                       b02['10'], margin_profit, self.tp_sector, limits)
        self.with_context(lfood_cit_system=True).write({
            'tp_revenue': revenue, 'tp_net_revenue': round(b02['10']), 'tp_margin_profit': margin_profit,
            'tp_related_total': related_total, 'tp_status': status, 'tp_reason': '\n'.join(reasons)})
