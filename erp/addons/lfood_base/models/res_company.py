from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    lfood_code = fields.Char('Mã pháp nhân', help='VP: Văn phòng, NM: Nhà máy')
    lfood_voucher_approval_limit = fields.Float(
        'Hạn mức duyệt chứng từ', digits=(16, 0), default=50_000_000,
        help='Chứng từ có tổng thanh toán lớn hơn mức này phải được Kế toán trưởng '
             'hoặc Giám đốc duyệt khi Cất.')
    lfood_edit_after_post_days = fields.Integer(
        'Số ngày được Sửa sau khi Cất', default=0,
        help='0 là không giới hạn. Quá số ngày thì không bấm Sửa được.')
