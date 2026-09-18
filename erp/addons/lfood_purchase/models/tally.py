"""Bảng kê thu mua hàng hóa, dịch vụ mua vào không có hóa đơn - Mẫu số 02/TNDN.

Căn cứ: Thông tư 20/2026/TT-BTC hướng dẫn Luật Thuế thu nhập doanh nghiệp 67/2025/QH15 và
Nghị định 320/2025/NĐ-CP. Mẫu 02/TNDN thay mẫu 01/TNDN ban hành kèm Thông tư 78/2014/TT-BTC.

Hai điểm bắt buộc app phải giữ:
- Chỉ lập bảng kê cho các trường hợp được phép (nông, lâm, thủy sản của người trực tiếp sản xuất,
  đánh bắt bán ra; hàng thủ công từ nguyên liệu tự nhiên; phế liệu của người trực tiếp thu nhặt;
  đồ dùng, tài sản của hộ gia đình, cá nhân; hàng hóa, dịch vụ của hộ, cá nhân kinh doanh dưới
  ngưỡng doanh thu chịu thuế GTGT).
- Tổng giá trị mua trong ngày của cùng một hộ, cá nhân từ mức quy định (5.000.000 đồng) trở lên
  thì phải thanh toán không dùng tiền mặt mới được tính vào chi phí được trừ. Mức này để trong
  Tham số pháp lý (BANG_KE_NGUONG_TIEN_MAT) để đổi được khi luật đổi.

Bảng kê là hồ sơ thuế, không tự ghi sổ: hàng nhập kho vẫn vào bằng phiếu nhập kho, chi phí dịch vụ
vẫn vào bằng chứng từ mua dịch vụ; bảng kê gắn kèm để chứng minh chi phí được trừ.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd

CASES = [
    ('farm', 'Nông, lâm, thủy sản của người sản xuất, đánh bắt trực tiếp bán ra'),
    ('handmade', 'Sản phẩm thủ công làm bằng nguyên liệu tự nhiên: đay, cói, tre, nứa, lá, song, mây'),
    ('scrap', 'Phế liệu của người trực tiếp thu nhặt'),
    ('household', 'Đồ dùng, tài sản của hộ gia đình, cá nhân trực tiếp bán ra'),
    ('small', 'Hàng hóa, dịch vụ của hộ, cá nhân kinh doanh dưới ngưỡng doanh thu chịu thuế GTGT'),
]
CASH_LIMIT_CODE = 'BANG_KE_NGUONG_TIEN_MAT'


class LfoodPurchaseTally(models.Model):
    _name = 'lfood.purchase.tally'
    _description = 'Bảng kê thu mua không có hóa đơn (02/TNDN)'
    _order = 'date desc, id desc'

    name = fields.Char('Số bảng kê', default='/', readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    date = fields.Date('Ngày lập', required=True, default=fields.Date.context_today, index=True)
    place = fields.Char('Địa chỉ nơi tổ chức thu mua', required=True)
    buyer_name = fields.Char('Người phụ trách thu mua', required=True, default=lambda s: s.env.user.name)
    memo = fields.Char('Diễn giải')
    picking_id = fields.Many2one('lfood.stock.picking', 'Phiếu nhập kho kèm theo', index=True,
                                 domain="[('kind', '=', 'in'), ('company_id', '=', company_id)]")
    line_ids = fields.One2many('lfood.purchase.tally.line', 'tally_id', 'Chi tiết thu mua', copy=True)
    amount = fields.Float('Tổng giá thanh toán', digits=(16, 0), compute='_compute_amount', store=True)
    amount_nondeductible = fields.Float('Trong đó không được trừ', digits=(16, 0), compute='_compute_amount', store=True)
    state = fields.Selection([('draft', 'Nháp'), ('confirmed', 'Đã ký'), ('cancel', 'Đã hủy')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False, index=True)
    confirmed_by = fields.Many2one('res.users', 'Người ký duyệt', readonly=True, copy=False)
    form_html = fields.Html('Mẫu 02/TNDN', compute='_compute_form_html', sanitize=False)

    @api.depends('line_ids.amount', 'line_ids.deductible')
    def _compute_amount(self):
        for rec in self:
            rec.amount = sum(rec.line_ids.mapped('amount'))
            rec.amount_nondeductible = sum(rec.line_ids.filtered(lambda l: not l.deductible).mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('lfood.purchase.tally') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('lfood_purchase_system'):
            if 'state' in vals:
                raise UserError(_('Trạng thái bảng kê chỉ đổi bằng nút Ký duyệt, Hủy.'))
            if self.filtered(lambda r: r.state != 'draft'):
                raise UserError(_('Bảng kê đã ký không sửa được. Hủy bảng kê rồi lập bảng kê mới.'))
        return super().write(vals)

    def cash_limit(self):
        """Ngưỡng tiền mặt trong ngày của một người bán, lấy từ Tham số pháp lý."""
        self.ensure_one()
        return self.env['lfood.legal.param'].get_value(CASH_LIMIT_CODE, self.date, default=5_000_000)

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ ký duyệt bảng kê đang ở trạng thái Nháp.'))
            if not rec.line_ids:
                raise UserError(_('Bảng kê chưa có dòng thu mua nào.'))
            rec.line_ids._check_seller()
            rec.with_context(lfood_purchase_system=True).write({'state': 'confirmed', 'confirmed_by': self.env.uid})
            summary = _('Ký bảng kê thu mua %s, tổng %s') % (rec.name, vnd(rec.amount))
            if rec.amount_nondeductible:
                summary += _('; %s không đủ điều kiện chi phí được trừ do trả tiền mặt từ %s trở lên trong ngày') \
                           % (vnd(rec.amount_nondeductible), vnd(rec.cash_limit()))
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id, res_name=rec.name,
                                                      company_id=rec.company_id.id, summary=summary)
        return True

    def action_cancel(self):
        self.filtered(lambda r: r.state == 'confirmed').with_context(lfood_purchase_system=True).write({'state': 'cancel'})
        return True

    @api.depends('line_ids', 'date', 'place', 'buyer_name', 'company_id')
    def _compute_form_html(self):
        """Dựng đúng thứ tự cột của mẫu 02/TNDN để in ra bằng Ctrl+P."""
        see_id = self.env.user.has_group('lfood_base.group_accountant')  # số định danh chỉ kế toán xem
        for rec in self:
            rows = []
            for i, line in enumerate(rec.line_ids, start=1):
                rows.append(
                    '<tr><td style="text-align:center">%s</td><td style="text-align:center">%s</td><td>%s</td>'
                    '<td>%s</td><td>%s</td><td>%s</td><td style="text-align:right">%s</td>'
                    '<td style="text-align:right">%s</td><td style="text-align:right">%s</td><td>%s</td></tr>' % (
                        i, line.date and line.date.strftime('%d/%m/%Y') or '', line.seller_name or '',
                        (line.seller_id_number or '') if see_id else '***', line.seller_address or '', line.name or '',
                        ('%g' % line.quantity), vnd(line.price_unit), vnd(line.amount),
                        line.note or ('Trả tiền mặt, không được trừ' if not line.deductible else '')))
            rec.form_html = """
<div style="font-family:Arial,sans-serif;font-size:13px">
  <div style="float:right;text-align:center"><b>Mẫu số 02/TNDN</b><br/>
    <i>(Ban hành kèm theo Thông tư số 20/2026/TT-BTC của Bộ Tài chính)</i></div>
  <div style="clear:both"></div>
  <p>Tên doanh nghiệp: <b>%s</b><br/>Mã số thuế: %s<br/>Địa chỉ: %s<br/>Địa chỉ nơi tổ chức thu mua: %s</p>
  <h3 style="text-align:center;margin:8px 0">BẢNG KÊ THU MUA HÀNG HÓA, DỊCH VỤ<br/>MUA VÀO KHÔNG CÓ HÓA ĐƠN</h3>
  <p style="text-align:center">Ngày %s</p>
  <table border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse;width:100%%">
    <thead><tr style="background:#f1f1f3">
      <th>STT</th><th>Ngày tháng mua</th><th>Tên người bán</th><th>Mã số định danh cá nhân</th>
      <th>Địa chỉ người bán</th><th>Tên hàng hóa, dịch vụ</th><th>Số lượng</th><th>Đơn giá</th>
      <th>Tổng giá thanh toán</th><th>Ghi chú</th>
    </tr></thead>
    <tbody>%s</tbody>
    <tfoot><tr><td colspan="8" style="text-align:right"><b>Tổng cộng</b></td>
      <td style="text-align:right"><b>%s</b></td><td></td></tr></tfoot>
  </table>
  <p>Người lập bảng kê: %s</p>
  <table style="width:100%%;margin-top:16px"><tr>
    <td style="text-align:center">Người lập bảng kê<br/><i>(Ký, ghi rõ họ tên)</i></td>
    <td style="text-align:center">Giám đốc doanh nghiệp<br/><i>(Ký, ghi rõ họ tên, đóng dấu)</i></td>
  </tr></table>
  <p style="font-size:12px;color:#555">Doanh nghiệp lập bảng kê theo thứ tự thời gian mua và chịu trách nhiệm
  về tính chính xác, trung thực của bảng kê. Trường hợp giá mua hàng hóa, dịch vụ trên bảng kê cao hơn giá
  thị trường tại thời điểm mua thì cơ quan thuế ấn định lại theo giá thị trường.</p>
</div>""" % (rec.company_id.name or '', rec.company_id.vat or '', rec.company_id.street or '', rec.place or '',
             rec.date and rec.date.strftime('%d/%m/%Y') or '', ''.join(rows) or
             '<tr><td colspan="10" style="text-align:center">Chưa có dòng nào</td></tr>',
             vnd(rec.amount), rec.buyer_name or '')


class LfoodPurchaseTallyLine(models.Model):
    _name = 'lfood.purchase.tally.line'
    _description = 'Dòng bảng kê thu mua'
    _order = 'date, id'

    tally_id = fields.Many2one('lfood.purchase.tally', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='tally_id.company_id', store=True)
    date = fields.Date('Ngày tháng mua', required=True, default=fields.Date.context_today)
    case = fields.Selection(CASES, 'Trường hợp được lập bảng kê', required=True, default='farm')
    seller_name = fields.Char('Tên người bán', required=True)
    seller_id_number = fields.Char('Mã số định danh cá nhân', required=True,
                                   groups='lfood_base.group_accountant')
    seller_address = fields.Char('Địa chỉ người bán', required=True)
    product_id = fields.Many2one('lfood.product', 'Mặt hàng')
    name = fields.Char('Tên hàng hóa, dịch vụ', required=True)
    quantity = fields.Float('Số lượng', digits=(16, 3), required=True, default=1)
    price_unit = fields.Float('Đơn giá', digits=(16, 2))
    amount = fields.Float('Tổng giá thanh toán', digits=(16, 0), compute='_compute_amount', store=True, readonly=False)
    payment_method = fields.Selection([('cash', 'Tiền mặt'), ('bank', 'Không dùng tiền mặt')], 'Hình thức thanh toán',
                                      required=True, default='cash')
    deductible = fields.Boolean('Được tính chi phí được trừ', compute='_compute_deductible', store=True)
    note = fields.Char('Ghi chú')

    @api.depends('quantity', 'price_unit')
    def _compute_amount(self):
        for rec in self:
            rec.amount = round(rec.quantity * rec.price_unit)

    @api.depends('amount', 'payment_method', 'date', 'seller_id_number', 'tally_id.line_ids.amount')
    def _compute_deductible(self):
        """Tiền mặt mà tổng mua trong ngày của cùng người bán từ ngưỡng trở lên thì không được trừ."""
        for rec in self:
            if rec.payment_method != 'cash':
                rec.deductible = True
                continue
            same_day = rec.tally_id.line_ids.filtered(
                lambda l: l.date == rec.date and l.payment_method == 'cash'
                and (l.seller_id_number or l.seller_name) == (rec.seller_id_number or rec.seller_name))
            rec.deductible = sum(same_day.mapped('amount')) < rec.tally_id.cash_limit()

    @api.onchange('product_id')
    def _onchange_product(self):
        if self.product_id and not self.name:
            self.name = self.product_id.name

    def _check_seller(self):
        for rec in self:
            if not (rec.seller_id_number or '').strip():
                raise UserError(_('Dòng %s thiếu mã số định danh cá nhân của người bán, mẫu 02/TNDN bắt buộc có.')
                                % rec.name)

    def write(self, vals):
        if not self.env.context.get('lfood_purchase_system') and self.filtered(lambda l: l.tally_id.state != 'draft'):
            raise UserError(_('Bảng kê đã ký không sửa được.'))
        return super().write(vals)
