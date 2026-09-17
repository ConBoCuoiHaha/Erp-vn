"""Chi trả thu nhập cho cá nhân không ký hợp đồng lao động hoặc hợp đồng dưới 03 tháng (THUE10).

Nghị định 253/2026/NĐ-CP (hiệu lực 01/7/2026), Điều 50 khoản 2: cá nhân cư trú, mức chi trả từ 05 triệu đồng/lần
trở lên thì khấu trừ 10% trên thu nhập trước khi trả; dưới 05 triệu đồng/lần khấu trừ 10% khi cá nhân yêu cầu; cá nhân
có cam kết (mẫu theo văn bản về quản lý thuế) thì tạm thời chưa khấu trừ, cuối năm vẫn tổng hợp danh sách nộp cơ quan
thuế. Trước 01/7/2026 ngưỡng là 02 triệu đồng (Thông tư 111/2013/TT-BTC). Cá nhân không cư trú: 20% (Điều 64).
Hạch toán: Nợ chi phí / Có 3335 (thuế khấu trừ), Có 111, 112 (số thực trả).
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import vnd


class LfoodPitFreelance(models.Model):
    _name = 'lfood.pit.freelance'
    _description = 'Chi trả thu nhập vãng lai'
    _order = 'date desc, id desc'

    name = fields.Char('Nội dung', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    partner_id = fields.Many2one('res.partner', 'Cá nhân nhận thu nhập', required=True, index=True)
    tax_code = fields.Char('Mã số thuế, số định danh', required=True)
    date = fields.Date('Ngày chi trả', required=True, default=fields.Date.context_today, index=True)
    gross = fields.Float('Thu nhập trước thuế', digits=(16, 0), required=True)
    resident = fields.Boolean('Cá nhân cư trú', default=True)
    requested = fields.Boolean('Cá nhân yêu cầu khấu trừ', help='Dưới ngưỡng vẫn khấu trừ 10% khi cá nhân yêu cầu')
    commitment = fields.Boolean('Có cam kết thu nhập chưa đến mức nộp thuế')
    commitment_file = fields.Binary('Bản cam kết', attachment=True)
    commitment_name = fields.Char()
    expense_account = fields.Char('TK chi phí', default='6428', required=True)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP')
    method = fields.Selection([('bank', 'Chuyển khoản'), ('cash', 'Tiền mặt')], 'Hình thức chi', default='bank', required=True)
    rate = fields.Float('Tỷ lệ khấu trừ (%)', compute='_compute_tax', store=True)
    tax = fields.Float('Thuế khấu trừ', digits=(16, 0), compute='_compute_tax', store=True)
    net = fields.Float('Thực trả', digits=(16, 0), compute='_compute_tax', store=True)
    tax_note = fields.Char('Căn cứ', compute='_compute_tax', store=True)
    state = fields.Selection([('draft', 'Nháp'), ('posted', 'Đã chi'), ('cancel', 'Đã hủy')], 'Trạng thái', default='draft',
                             required=True, readonly=True, copy=False, index=True)

    @api.depends('gross', 'resident', 'requested', 'commitment', 'date')
    def _compute_tax(self):
        P = self.env['lfood.legal.param']
        for rec in self:
            d = rec.date or fields.Date.context_today(rec)
            if not rec.resident:
                rate, note = P.get_value('TNCN_THUE_SUAT_KHONG_CU_TRU', d, default=20), _('Cá nhân không cư trú')
            elif rec.commitment:
                rate, note = 0, _('Có cam kết: tạm thời chưa khấu trừ, cuối năm vẫn kê khai danh sách')
            else:
                limit = P.get_value('TNCN_NGUONG_KHAU_TRU_VANG_LAI', d, default=5000000)
                if rec.gross >= limit or rec.requested:
                    rate = P.get_value('TNCN_TY_LE_VANG_LAI', d, default=10)
                    note = _('Từ %s đồng/lần') % vnd(limit) if rec.gross >= limit else _('Cá nhân yêu cầu khấu trừ')
                else:
                    rate, note = 0, _('Dưới %s đồng/lần') % vnd(limit)
            rec.rate = rate
            rec.tax = round(rec.gross * rate / 100)
            rec.net = rec.gross - rec.tax
            rec.tax_note = note

    @api.constrains('commitment', 'resident')
    def _check_commitment(self):
        for rec in self:
            if rec.commitment and not rec.resident:
                raise ValidationError(_('Cá nhân không cư trú không được làm cam kết để không khấu trừ.'))

    def action_post(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được chi trả.'))
        Move = self.env['lfood.move']
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if rec.gross <= 0:
                raise UserError(_('Thu nhập phải lớn hơn 0.'))
            if rec.commitment and not rec.commitment_file:
                raise UserError(_('Đính kèm bản cam kết của cá nhân.'))
            cash = '111' if rec.method == 'cash' else '112'
            lines = [(rec.expense_account, rec.gross, 0, None, rec.name, rec.cost_item_id),
                     (cash, 0, rec.net, None, rec.name, None)]
            if rec.tax:
                lines.append(('3335', 0, rec.tax, None, _('Thuế TNCN khấu trừ %s') % rec.partner_id.name, None))
            Move._create_from_source(rec, 'cash' if rec.method == 'cash' else 'bank', rec.date, lines,
                                     memo=rec.name, ref=rec.tax_code, company=rec.company_id)
            rec.state = 'posted'
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Chi thu nhập %s cho %s, khấu trừ %s') % (vnd(rec.gross), rec.partner_id.name, vnd(rec.tax)))
        return True

    def action_cancel(self):
        for rec in self.filtered(lambda r: r.state == 'posted'):
            for move in self.env['lfood.move']._active_for(rec):
                move._reverse(memo=_('Hủy chi trả %s') % rec.name)
        self.filtered(lambda r: r.state != 'cancel').write({'state': 'cancel'})
        return True
