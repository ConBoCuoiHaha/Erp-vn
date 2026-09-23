"""Ràng buộc nhập liệu: kế toán trưởng tự đặt luật cho từng nhóm tài khoản, không phải sửa mã nguồn."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd

SIDES = [('both', 'Cả hai bên'), ('debit', 'Bên Nợ'), ('credit', 'Bên Có')]


class LfoodEntryRule(models.Model):
    _name = 'lfood.entry.rule'
    _description = 'Ràng buộc nhập liệu'
    _order = 'sequence, account_prefix'

    name = fields.Char('Tên ràng buộc', required=True)
    sequence = fields.Integer('Thứ tự', default=10)
    active = fields.Boolean('Đang áp dụng', default=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    account_prefix = fields.Char('Tài khoản bắt đầu bằng',
                                 help='Ví dụ 331 áp cho 3311, 3312…; để trống thì áp cho mọi tài khoản')
    side = fields.Selection(SIDES, 'Áp dụng cho', required=True, default='both')
    require_partner = fields.Boolean('Bắt buộc ghi đối tượng')
    require_cost_item = fields.Boolean('Bắt buộc khoản mục chi phí')
    require_memo = fields.Boolean('Bắt buộc diễn giải')
    require_ref = fields.Boolean('Bắt buộc số chứng từ')
    max_amount = fields.Float('Số tiền tối đa mỗi dòng', digits=(16, 0),
                              help='Để 0 nghĩa là không giới hạn; vượt mức thì báo lỗi, không cho ghi sổ')
    forbid = fields.Boolean('Cấm hạch toán tay',
                            help='Tài khoản chỉ được ghi từ phân hệ khác, ví dụ 154, 632 do phân hệ giá thành ghi')
    message = fields.Char('Lời nhắc riêng', help='Hiện kèm lỗi để người nhập biết phải làm gì')

    @api.constrains('account_prefix')
    def _check_prefix(self):
        for rec in self:
            if rec.account_prefix and not rec.account_prefix.strip().isdigit():
                raise ValidationError(_('Tài khoản bắt đầu bằng chỉ gồm chữ số, ví dụ 331.'))

    @api.model
    def _for_company(self, company):
        return self.search([('company_id', '=', company.id)])

    def _errors(self, account, side, amount, partner, cost_item, memo, ref):
        """Trả về danh sách lỗi của một vế định khoản theo mọi ràng buộc đang áp dụng."""
        out = []
        for rule in self:
            if not account.code.startswith((rule.account_prefix or '').strip()):
                continue
            if rule.side != 'both' and rule.side != side:
                continue
            tag = _('TK %s') % account.code
            if rule.forbid:
                out.append(_('%s: không được hạch toán tay') % tag)
            if rule.require_partner and not partner:
                out.append(_('%s: thiếu đối tượng') % tag)
            if rule.require_cost_item and not cost_item:
                out.append(_('%s: thiếu khoản mục chi phí') % tag)
            if rule.require_memo and not memo:
                out.append(_('%s: thiếu diễn giải') % tag)
            if rule.require_ref and not ref:
                out.append(_('%s: thiếu số chứng từ') % tag)
            if rule.max_amount and amount > rule.max_amount:
                out.append(_('%s: vượt mức %s') % (tag, vnd(rule.max_amount)))
            if out and rule.message and rule.message not in out:
                out.append(rule.message)
        return out
