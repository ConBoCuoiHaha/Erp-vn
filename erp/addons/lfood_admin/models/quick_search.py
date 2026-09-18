"""Tìm kiếm nhanh toàn hệ thống (HT07).

Gõ một chuỗi: số chứng từ, số hóa đơn, mã số thuế, mã hàng, mã vạch, số lô, tên nhân viên, tên đối tác; app tìm trên
các bảng chính mà người dùng có quyền đọc và liệt kê kết quả kèm đường dẫn mở thẳng chứng từ. Bảng nào chưa cài hoặc
người dùng không có quyền thì bỏ qua.
"""
from markupsafe import Markup

from odoo import api, fields, models, _

# (model, nhãn, các trường tìm theo chuỗi)
TARGETS = [
    ('lfood.service.voucher', 'Chứng từ mua dịch vụ', ['name']),
    ('lfood.sale.invoice', 'Hóa đơn bán ra', ['name', 'invoice_number', 'memo']),
    ('lfood.stock.picking', 'Phiếu kho', ['name', 'invoice_number', 'memo']),
    ('lfood.purchase.order', 'Đơn mua hàng', ['name', 'memo']),
    ('lfood.sale.order', 'Đơn bán hàng', ['name', 'memo']),
    ('lfood.payment', 'Phiếu thu, chi', ['name', 'memo']),
    ('lfood.move', 'Bút toán', ['ref', 'memo']),
    ('res.partner', 'Đối tác', ['name', 'vat', 'phone']),
    ('lfood.product', 'Mặt hàng', ['code', 'name', 'barcode']),
    ('lfood.stock.lot', 'Lô hàng', ['name']),
    ('lfood.employee', 'Nhân viên', ['code', 'name', 'tax_code']),
    ('lfood.asset', 'Tài sản cố định', ['code', 'name', 'serial']),
]


class LfoodQuickSearch(models.TransientModel):
    _name = 'lfood.quick.search'
    _description = 'Tìm kiếm nhanh toàn hệ thống'

    query = fields.Char('Tìm', required=True, help='Số chứng từ, số hóa đơn, mã số thuế, mã hàng, mã vạch, số lô, tên')
    limit = fields.Integer('Số kết quả mỗi bảng', default=5)
    result_html = fields.Html('Kết quả', compute='_compute_result', sanitize=False)

    @api.depends('query', 'limit')
    def _compute_result(self):
        for rec in self:
            rec.result_html = rec._search_html() if rec.query else False

    def _search_html(self):
        self.ensure_one()
        text = (self.query or '').strip()
        blocks = []
        for model, label, fields_ in TARGETS:
            Model = self.env.get(model)
            if Model is None or not Model.has_access('read'):
                continue
            domain = ['|'] * (len(fields_) - 1) + [(f, 'ilike', text) for f in fields_]
            try:
                records = Model.search(domain, limit=self.limit or 5)
            except Exception:
                continue
            if not records:
                continue
            items = Markup('').join(
                Markup('<li><a href="/odoo/m-%s/%s">%s</a></li>') % (model, r.id, r.display_name) for r in records)
            blocks.append(Markup('<h5>%s</h5><ul>%s</ul>') % (label, items))
        if not blocks:
            return Markup('<p>%s</p>') % _('Không tìm thấy "%s".') % text
        return Markup('').join(blocks)
