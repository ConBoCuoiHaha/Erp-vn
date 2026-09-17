"""Nối đơn mua với phiếu nhập kho: đối chiếu 3 bên trước khi ghi phiếu (MH05)."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd


class LfoodStockPicking(models.Model):
    _inherit = 'lfood.stock.picking'

    purchase_order_id = fields.Many2one('lfood.purchase.order', 'Đơn mua', index=True, copy=False)

    def _check_three_way(self):
        """So số lượng và đơn giá của phiếu nhận với đơn mua.

        Chênh lệch trong dung sai của công ty thì cho qua, vượt thì chặn ghi phiếu
        để kế toán đối chiếu lại với nhà cung cấp.
        """
        for rec in self.filtered('purchase_order_id'):
            order = rec.purchase_order_id
            if order.state == 'cancel':
                raise UserError(_('Đơn mua %s đã hủy.') % order.name)
            tol = rec.company_id.lfood_purchase_tolerance / 100.0
            if rec.kind == 'out':
                # trả lại hàng mua: không trả nhiều hơn số đã nhận theo đơn
                for line in rec.line_ids:
                    ol = order.line_ids.filtered(lambda l: l.product_id == line.product_id)[:1]
                    if not ol:
                        raise UserError(_('Mặt hàng %s không có trong đơn mua %s.')
                                        % (line.product_id.display_name, order.name))
                    if line.quantity > ol.qty_received + 1e-6:
                        raise UserError(_('Mặt hàng %s: đã nhận %s theo đơn %s, không trả lại %s.')
                                        % (line.product_id.display_name, ol.qty_received, order.name, line.quantity))
                continue
            for line in rec.line_ids:
                ol = order.line_ids.filtered(lambda l: l.product_id == line.product_id)[:1]
                if not ol:
                    raise UserError(_('Mặt hàng %s không có trong đơn mua %s.')
                                    % (line.product_id.display_name, order.name))
                remain = ol.quantity - ol.qty_received
                if line.quantity > remain * (1 + tol) + 1e-6:
                    raise UserError(_('Mặt hàng %s: đơn mua %s còn %s, phiếu nhận %s, vượt dung sai %s%%.')
                                    % (line.product_id.display_name, order.name, remain, line.quantity,
                                       rec.company_id.lfood_purchase_tolerance))
                if ol.price_unit and abs(line.price_unit - ol.price_unit) > ol.price_unit * tol + 1e-6:
                    raise UserError(_('Mặt hàng %s: đơn giá đơn mua %s, hóa đơn %s, lệch quá dung sai %s%%.')
                                    % (line.product_id.display_name, vnd(ol.price_unit), vnd(line.price_unit),
                                       rec.company_id.lfood_purchase_tolerance))

    def action_done(self):
        self._check_three_way()
        res = super().action_done()
        self.mapped('purchase_order_id')._update_state()
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self.env.flush_all()
        self.mapped('purchase_order_id').invalidate_recordset()
        return res


class LfoodCompany(models.Model):
    _inherit = 'res.company'

    lfood_purchase_tolerance = fields.Float(
        'Dung sai đối chiếu 3 bên (%)', digits=(16, 2), default=0.0,
        help='Chênh lệch số lượng và đơn giá cho phép giữa đơn mua, phiếu nhận và hóa đơn. '
             'Vượt mức này thì không ghi được phiếu nhập kho.')
    lfood_quote_threshold = fields.Float(
        'Mức tiền phải có báo giá', digits=(16, 0), default=100_000_000,
        help='Yêu cầu mua có giá trị dự kiến từ mức này phải có đủ số báo giá tối thiểu trước khi lập đơn mua.')
    lfood_min_quotes = fields.Integer(
        'Số báo giá tối thiểu', default=3,
        help='Để 0 nếu công ty không bắt buộc lấy báo giá.')
