from odoo import api, models


class IapAutocompleteApi(models.AbstractModel):
    """partner_autocomplete tự cài theo mail và gửi tên, mã số thuế đối tác lên máy chủ Odoo khi gõ.
    Chặn tại cửa duy nhất gọi ra ngoài; ValueError được module gốc hiểu là "chưa có tài khoản" nên giao diện không lỗi."""
    _inherit = 'iap.autocomplete.api'

    @api.model
    def _contact_iap(self, local_endpoint, action, params, timeout=15):
        raise ValueError('Tra cứu đối tác qua máy chủ Odoo đã tắt')
