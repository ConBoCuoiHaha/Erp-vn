from odoo import fields, models, _
from odoo.exceptions import UserError


class LfoodServiceVoucher(models.Model):
    _inherit = 'lfood.service.voucher'

    asset_ids = fields.One2many('lfood.asset', 'voucher_id', 'Tài sản ghi tăng')
    asset_count = fields.Integer('Số tài sản', compute='_compute_asset_count')

    def _compute_asset_count(self):
        for rec in self:
            rec.asset_count = len(rec.asset_ids)

    def action_create_asset(self):
        """Ghi tăng TSCĐ từ chứng từ mua đã cất: nguyên giá lấy tổng tiền chưa thuế của phiên bản báo cáo."""
        self.ensure_one()
        if self.state not in ('posted', 'editing'):
            raise UserError(_('Cất chứng từ mua trước khi ghi tăng tài sản.'))
        version = self.report_version_id
        return {
            'type': 'ir.actions.act_window', 'name': _('Ghi tăng TSCĐ'), 'res_model': 'lfood.asset',
            'view_mode': 'form', 'target': 'current',
            'context': {
                'default_voucher_id': self.id, 'default_company_id': self.company_id.id,
                'default_partner_id': version.partner_id.id or self.partner_id.id,
                'default_purchase_date': version.accounting_date or self.accounting_date,
                'default_date_start': version.accounting_date or self.accounting_date,
                'default_name': version.memo or self.memo,
                'default_original_value': version.amount_untaxed,
            },
        }

    def action_view_assets(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Tài sản ghi tăng'), 'res_model': 'lfood.asset',
                'view_mode': 'list,form', 'domain': [('voucher_id', '=', self.id)],
                'context': {'default_voucher_id': self.id}}
