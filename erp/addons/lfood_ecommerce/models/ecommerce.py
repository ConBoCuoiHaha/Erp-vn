"""Đơn sàn thương mại điện tử (BH13).

Mỗi gian hàng (Shopee, Lazada, TikTok Shop...) gắn một kho và một đối tượng "khách mua trên sàn". Đơn nhập từ tệp CSV
theo mẫu cột: ma_don; ngay; trang_thai; sku; so_luong; don_gia (chuyển từ tệp xuất của sàn; tệp gốc từng sàn khác nhau
nên cần bước chuyển đổi khi có tệp thật). SKU so với mã vạch hoặc mã hàng. Đơn hoàn thành chưa lập hóa đơn thì app lập
hóa đơn bán ra nháp (kế toán nhập ký hiệu, số hóa đơn điện tử rồi ghi sổ, kho tự xuất theo hạn dùng).
Tồn khả dụng = tồn kho gian hàng - lô đang cách ly - hàng của đơn đã nhận chưa lập hóa đơn; xuất tệp để cập nhật lên sàn.
Đối soát tiền về: tệp đối soát của sàn (ma_don; tien_hang; phi_san; thuc_nhan); ghi Nợ 112 số thực nhận, Nợ 6417 phí sàn,
Có 1311 tiền hàng của các đơn; đơn trong tệp không có trong app hoặc lệch tiền thì báo.
"""
import base64
import csv
import io
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_vat.models.einvoice_check import to_number as num
from odoo.addons.lfood_voucher.models.tools import vnd

PLATFORMS = [('shopee', 'Shopee'), ('lazada', 'Lazada'), ('tiktok', 'TikTok Shop'), ('other', 'Sàn khác')]
STATUS = [('new', 'Chờ giao'), ('done', 'Hoàn thành'), ('cancel', 'Đã hủy'), ('return', 'Trả hàng')]
# từ khóa trong trạng thái sàn, xét theo thứ tự
STATUS_WORDS = [('trả hàng', 'return'), ('return', 'return'), ('hủy', 'cancel'), ('huỷ', 'cancel'), ('cancel', 'cancel'),
                ('hoàn thành', 'done'), ('completed', 'done'), ('đã giao', 'done'), ('delivered', 'done')]


def map_status(text):
    text = (text or '').lower()
    return next((code for word, code in STATUS_WORDS if word in text), 'new')


def read_csv(data):
    text = base64.b64decode(data).decode('utf-8-sig')
    delimiter = max(';,\t', key=text[:4096].count)
    rows = list(csv.DictReader(io.StringIO(text), delimiter=delimiter))
    return [{(k or '').strip().lower(): (v or '').strip() for k, v in r.items()} for r in rows]


class LfoodEcomShop(models.Model):
    _name = 'lfood.ecom.shop'
    _description = 'Gian hàng trên sàn thương mại điện tử'

    name = fields.Char('Gian hàng', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    platform = fields.Selection(PLATFORMS, 'Sàn', required=True, default='shopee')
    warehouse_id = fields.Many2one('lfood.warehouse', 'Kho giao hàng', required=True)
    customer_id = fields.Many2one('res.partner', 'Đối tượng khách mua trên sàn', required=True,
                                  help='Hóa đơn và công nợ của đơn sàn ghi cho đối tượng này')
    platform_partner_id = fields.Many2one('res.partner', 'Đơn vị vận hành sàn', help='Người lập hóa đơn phí sàn')
    fee_account = fields.Char('TK phí sàn', default='6417', required=True)
    vat_rate_id = fields.Many2one('lfood.vat.rate', 'Thuế suất mặc định', required=True)
    order_ids = fields.One2many('lfood.ecom.order', 'shop_id', 'Đơn')
    import_file = fields.Binary('Tệp đơn (CSV)')
    import_name = fields.Char()
    stock_file = fields.Binary('Tệp tồn khả dụng', readonly=True)
    stock_name = fields.Char()
    active = fields.Boolean(default=True)

    def _find_product(self, sku):
        P = self.env['lfood.product']
        return P.search([('barcode', '=', sku)], limit=1) or P.search([('code', '=', sku)], limit=1)

    def action_import_orders(self):
        self.ensure_one()
        if not self.import_file:
            raise UserError(_('Chọn tệp đơn.'))
        Order = self.env['lfood.ecom.order']
        created = updated = 0
        missing = set()
        orders = {}
        for r in read_csv(self.import_file):
            ref = r.get('ma_don')
            if not ref:
                continue
            product = self._find_product(r.get('sku'))
            if not product:
                missing.add(r.get('sku'))
                continue
            status = map_status(r.get('trang_thai'))
            date = datetime.strptime(r['ngay'][:10], '%d/%m/%Y').date() if '/' in r.get('ngay', '') \
                else fields.Date.to_date(r.get('ngay')[:10])
            o = orders.setdefault(ref, {'status': status, 'date': date, 'lines': []})
            o['lines'].append((product, num(r.get('so_luong')), num(r.get('don_gia'))))
        if missing:
            raise UserError(_('Không tìm thấy mặt hàng có SKU: %s. Gán mã vạch hoặc mã hàng trùng SKU rồi nhập lại.')
                            % ', '.join(sorted(s or '(trống)' for s in missing)))
        for ref, o in orders.items():
            order = Order.search([('shop_id', '=', self.id), ('name', '=', ref)], limit=1)
            if order:
                if order.status != o['status'] and not order.invoice_id:
                    order.status = o['status']
                    updated += 1
                continue
            Order.create({'shop_id': self.id, 'name': ref, 'date': o['date'], 'status': o['status'],
                          'line_ids': [(0, 0, {'product_id': p.id, 'quantity': q, 'price_unit': pr}) for p, q, pr in o['lines']]})
            created += 1
        self.write({'import_file': False})
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'message': _('Đã thêm %s đơn, cập nhật trạng thái %s đơn.') % (created, updated),
                           'type': 'success'}}

    def _available(self):
        """{mặt hàng: tồn khả dụng}"""
        self.ensure_one()
        Val = self.env['lfood.stock.valuation'].sudo()
        out = {}
        for v in Val.search([('warehouse_id', '=', self.warehouse_id.id)]):
            if v.lot_id and v.lot_id.hold:
                continue
            out[v.product_id] = out.get(v.product_id, 0) + v.qty
        for line in self.order_ids.filtered(lambda o: o.status == 'new' and not o.invoice_id).line_ids:
            out[line.product_id] = out.get(line.product_id, 0) - line.quantity
        return {p: max(q, 0) for p, q in out.items()}

    def action_export_stock(self):
        self.ensure_one()
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=';')
        w.writerow(['sku', 'ten_hang', 'ton_kha_dung'])
        for p, q in sorted(self._available().items(), key=lambda i: i[0].code):
            w.writerow([p.barcode or p.code, p.name, '%g' % q])
        self.write({'stock_file': base64.b64encode(buf.getvalue().encode('utf-8-sig')),
                    'stock_name': 'ton-kha-dung-%s-%s.csv' % (self.platform, fields.Date.context_today(self))})
        return True

    def action_invoice_orders(self):
        """Lập hóa đơn nháp cho đơn hoàn thành chưa có hóa đơn."""
        self.ensure_one()
        Inv = self.env['lfood.sale.invoice']
        count = 0
        for o in self.order_ids.filtered(lambda x: x.status == 'done' and not x.invoice_id):
            o.invoice_id = Inv.create({
                'company_id': self.company_id.id, 'partner_id': self.customer_id.id, 'date': o.date,
                'invoice_date': o.date, 'warehouse_id': self.warehouse_id.id,
                'memo': _('Đơn %s trên %s') % (o.name, self.name),
                'line_ids': [(0, 0, {'name': l.product_id.name, 'product_id': l.product_id.id, 'uom': l.product_id.uom,
                                     'quantity': l.quantity, 'price_unit': l.price_unit,
                                     'vat_rate_id': (l.product_id.vat_rate_id or self.vat_rate_id).id})
                             for l in o.line_ids]})
            count += 1
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'message': _('Đã lập %s hóa đơn nháp.') % count, 'type': 'success'}}


class LfoodEcomOrder(models.Model):
    _name = 'lfood.ecom.order'
    _description = 'Đơn sàn thương mại điện tử'
    _order = 'date desc, id desc'

    shop_id = fields.Many2one('lfood.ecom.shop', 'Gian hàng', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one(related='shop_id.company_id', store=True, index=True)
    name = fields.Char('Mã đơn trên sàn', required=True, index=True)
    date = fields.Date('Ngày đặt', required=True)
    status = fields.Selection(STATUS, 'Trạng thái', required=True, default='new')
    line_ids = fields.One2many('lfood.ecom.order.line', 'order_id', 'Hàng')
    amount = fields.Float('Tiền hàng chưa thuế', digits=(16, 0), compute='_compute_amount', store=True)
    invoice_id = fields.Many2one('lfood.sale.invoice', 'Hóa đơn', readonly=True, copy=False)
    settled_amount = fields.Float('Sàn đã chuyển', digits=(16, 0), readonly=True, copy=False)
    fee = fields.Float('Phí sàn', digits=(16, 0), readonly=True, copy=False)
    settlement_id = fields.Many2one('lfood.ecom.settlement', 'Đối soát', readonly=True, copy=False)

    _uniq = models.Constraint('unique(shop_id, name)', 'Mã đơn đã có trong gian hàng.')

    @api.depends('line_ids.quantity', 'line_ids.price_unit')
    def _compute_amount(self):
        for rec in self:
            rec.amount = round(sum(l.quantity * l.price_unit for l in rec.line_ids))


class LfoodEcomOrderLine(models.Model):
    _name = 'lfood.ecom.order.line'
    _description = 'Hàng trong đơn sàn'

    order_id = fields.Many2one('lfood.ecom.order', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('lfood.product', 'Mặt hàng', required=True)
    quantity = fields.Float('Số lượng', digits=(16, 3))
    price_unit = fields.Float('Đơn giá chưa thuế', digits=(16, 2))


class LfoodEcomSettlement(models.Model):
    _name = 'lfood.ecom.settlement'
    _description = 'Đối soát tiền sàn chuyển về'
    _order = 'date desc, id desc'

    shop_id = fields.Many2one('lfood.ecom.shop', 'Gian hàng', required=True, index=True)
    company_id = fields.Many2one(related='shop_id.company_id', store=True, index=True)
    name = fields.Char('Mã đợt chuyển tiền', required=True)
    date = fields.Date('Ngày nhận tiền', required=True)
    import_file = fields.Binary('Tệp đối soát (CSV)')
    line_ids = fields.One2many('lfood.ecom.settlement.line', 'settlement_id', 'Chi tiết')
    gross = fields.Float('Tiền hàng (gồm thuế)', digits=(16, 0), compute='_compute_totals', store=True)
    fee = fields.Float('Phí sàn', digits=(16, 0), compute='_compute_totals', store=True)
    net = fields.Float('Thực nhận', digits=(16, 0), compute='_compute_totals', store=True)
    issues = fields.Text('Chênh lệch cần xử lý', readonly=True)
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã ghi sổ')], 'Trạng thái', default='draft', required=True,
                             readonly=True)

    @api.depends('line_ids.gross', 'line_ids.fee', 'line_ids.net')
    def _compute_totals(self):
        for rec in self:
            rec.gross = sum(rec.line_ids.mapped('gross'))
            rec.fee = sum(rec.line_ids.mapped('fee'))
            rec.net = sum(rec.line_ids.mapped('net'))

    def action_load(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.import_file:
                raise UserError(_('Chọn tệp đối soát.'))
            Order = self.env['lfood.ecom.order']
            rec.line_ids.unlink()
            vals = []
            for r in read_csv(rec.import_file):
                ref = r.get('ma_don')
                if not ref:
                    continue
                order = Order.search([('shop_id', '=', rec.shop_id.id), ('name', '=', ref)], limit=1)
                vals.append({'settlement_id': rec.id, 'order_ref': ref, 'order_id': order.id,
                             'gross': num(r.get('tien_hang')), 'fee': num(r.get('phi_san')), 'net': num(r.get('thuc_nhan'))})
            self.env['lfood.ecom.settlement.line'].create(vals)
            problems = []
            for l in rec.line_ids:
                if not l.order_id:
                    problems.append(_('Đơn %s không có trong app') % l.order_ref)
                elif not l.order_id.invoice_id or l.order_id.invoice_id.state != 'posted':
                    problems.append(_('Đơn %s chưa ghi sổ hóa đơn') % l.order_ref)
                elif abs(l.order_id.invoice_id.amount_total - l.gross) >= 1:
                    problems.append(_('Đơn %s: sàn ghi %s, hóa đơn %s') % (
                        l.order_ref, vnd(l.gross), vnd(l.order_id.invoice_id.amount_total)))
                if abs(l.gross - l.fee - l.net) >= 1:
                    problems.append(_('Đơn %s: tiền hàng trừ phí khác thực nhận') % l.order_ref)
            rec.issues = '\n'.join(problems) or False
        return True

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được ghi sổ.'))
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if rec.import_file and not rec.line_ids:
                rec.action_load()
            if not rec.line_ids:
                raise UserError(_('Chưa có chi tiết đối soát.'))
            if rec.issues:
                raise UserError(_('Còn chênh lệch cần xử lý:\n%s') % rec.issues)
            shop = rec.shop_id
            label = _('Tiền %s chuyển về đợt %s') % (shop.name, rec.name)
            self.env['lfood.move']._create_from_source(rec, 'bank', rec.date, [
                ('112', rec.net, 0, None, label, None),
                (shop.fee_account, rec.fee, 0, None, _('Phí sàn %s') % label, None),
                ('1311', 0, rec.gross, shop.customer_id, label, None)], memo=label, ref=rec.name, company=shop.company_id)
            for l in rec.line_ids:
                l.order_id.write({'settled_amount': l.net, 'fee': l.fee, 'settlement_id': rec.id})
            rec.state = 'posted'
        return True


class LfoodSaleInvoice(models.Model):
    _inherit = 'lfood.sale.invoice'

    def _compute_paid(self):
        """Tiền sàn đã chuyển về theo đối soát được tính là đã thu của hóa đơn đơn sàn."""
        super()._compute_paid()
        lines = self.env['lfood.ecom.settlement.line'].sudo().search([
            ('order_id.invoice_id', 'in', self.ids), ('settlement_id.state', '=', 'posted')])
        for l in lines:
            inv = l.order_id.invoice_id
            inv.amount_paid += l.gross
            inv.amount_residual -= l.gross


class LfoodEcomSettlementLine(models.Model):
    _name = 'lfood.ecom.settlement.line'
    _description = 'Chi tiết đối soát sàn'

    settlement_id = fields.Many2one('lfood.ecom.settlement', required=True, ondelete='cascade', index=True)
    order_ref = fields.Char('Mã đơn', required=True)
    order_id = fields.Many2one('lfood.ecom.order', 'Đơn')
    gross = fields.Float('Tiền hàng', digits=(16, 0))
    fee = fields.Float('Phí sàn', digits=(16, 0))
    net = fields.Float('Thực nhận', digits=(16, 0))
