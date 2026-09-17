from odoo import fields, models, _
from odoo.exceptions import UserError


class LfoodVoucherReason(models.TransientModel):
    _name = 'lfood.voucher.reason'
    _description = 'Nhập lý do hoặc tổng mới cho chứng từ'

    voucher_id = fields.Many2one('lfood.service.voucher', required=True)
    mode = fields.Selection([('save_edit', 'Lưu sửa đổi'), ('restore', 'Khôi phục gốc'), ('total', 'Sửa tổng')], required=True)
    reason = fields.Text('Lý do')
    new_total = fields.Float('Tổng tiền dịch vụ mới', digits=(16, 0))
    current_total = fields.Float(related='voucher_id.amount_untaxed', string='Tổng hiện tại')

    def action_confirm(self):
        self.ensure_one()
        if self.mode == 'total':
            self.voucher_id._apply_total(self.new_total)
        elif self.mode == 'save_edit':
            self.voucher_id._save_edit(self.reason)
        elif self.mode == 'restore':
            if not (self.reason or '').strip():
                raise UserError(_('Phải nhập lý do khôi phục.'))
            self.voucher_id._restore_original(self.reason)
        return {'type': 'ir.actions.act_window_close'}
