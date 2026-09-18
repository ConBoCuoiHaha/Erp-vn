"""Chữ ký số của chứng từ điện tử (HT13).

App không ký số thay người dùng: việc ký thực hiện bằng USB token hoặc chữ ký số từ xa trên phần mềm của nhà cung cấp
(hóa đơn điện tử ký trên hệ thống hóa đơn, tờ khai thuế ký trên phần mềm của cơ quan thuế, hồ sơ bảo hiểm ký trên phần
mềm kê khai bảo hiểm). App chịu trách nhiệm phần hồ sơ:
- danh sách chứng thư số đang dùng: nhà cung cấp, số sê-ri, thời hạn, người giữ token, dùng cho việc gì; nhắc trước khi
  hết hạn để gia hạn kịp, không gián đoạn xuất hóa đơn, nộp tờ khai;
- chứng từ đã ký: lưu tệp đã ký (.p7s, .xml, PDF có chữ ký), ghi chứng thư đã dùng, người ký, thời điểm ký; tệp lưu kèm
  mã kiểm tra SHA-256 nên phát hiện được nếu bị thay.
Muốn app tự ký thì cần nhà cung cấp chữ ký số có dịch vụ ký từ xa và thông tin kết nối; khi có thì bổ sung phần gọi
dịch vụ, phần hồ sơ ở đây giữ nguyên.
"""
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

PURPOSES = [('invoice', 'Hóa đơn điện tử'), ('tax', 'Tờ khai thuế'), ('insurance', 'Hồ sơ bảo hiểm xã hội'),
            ('contract', 'Hợp đồng điện tử'), ('other', 'Việc khác')]
FORMATS = [('p7s', 'Tệp chữ ký .p7s (PKCS#7)'), ('xml', 'XML có chữ ký'), ('pdf', 'PDF có chữ ký'), ('other', 'Khác')]


class LfoodDigitalCert(models.Model):
    _name = 'lfood.digital.cert'
    _description = 'Chứng thư số'
    _order = 'valid_to desc'

    name = fields.Char('Chủ thể chứng thư', required=True, help='Tên tổ chức hoặc cá nhân ghi trên chứng thư số')
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    serial = fields.Char('Số sê-ri', required=True)
    provider = fields.Char('Nhà cung cấp', required=True, help='Ví dụ Viettel-CA, VNPT-CA, FPT-CA, MISA eSign')
    valid_from = fields.Date('Hiệu lực từ', required=True)
    valid_to = fields.Date('Hiệu lực đến', required=True)
    holder = fields.Char('Người giữ token, tài khoản ký')
    purposes = fields.Char('Dùng cho', help='Ví dụ hóa đơn điện tử, tờ khai thuế')
    purpose = fields.Selection(PURPOSES, 'Việc chính', default='invoice', required=True)
    remote_signing = fields.Boolean('Ký từ xa (không cần token cắm máy)')
    note = fields.Text('Ghi chú')
    days_left = fields.Integer('Còn (ngày)', compute='_compute_days')
    expired = fields.Boolean('Đã hết hạn', compute='_compute_days')
    active = fields.Boolean(default=True)

    _serial_uniq = models.Constraint('unique(company_id, serial)', 'Số sê-ri chứng thư đã có.')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - %s' % (rec.provider or '', rec.serial or '')

    def _compute_days(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.days_left = (rec.valid_to - today).days if rec.valid_to else 0
            rec.expired = bool(rec.valid_to and rec.valid_to < today)

    @api.constrains('valid_from', 'valid_to')
    def _check_dates(self):
        for rec in self:
            if rec.valid_to <= rec.valid_from:
                raise ValidationError(_('Ngày hết hiệu lực phải sau ngày bắt đầu.'))


class LfoodDocument(models.Model):
    _inherit = 'lfood.document'

    signed = fields.Boolean('Đã ký số')
    cert_id = fields.Many2one('lfood.digital.cert', 'Chứng thư số đã dùng')
    signature_format = fields.Selection(FORMATS, 'Định dạng chữ ký')
    signer = fields.Char('Người ký')
    signed_at = fields.Datetime('Thời điểm ký')

    @api.constrains('signed', 'cert_id', 'signed_at', 'doc_date')
    def _check_signature(self):
        for rec in self.filtered('signed'):
            if not (rec.cert_id and rec.signed_at and rec.signer):
                raise ValidationError(_('Chứng từ đã ký số phải ghi chứng thư, người ký và thời điểm ký.'))
            day = rec.signed_at.date()
            if not (rec.cert_id.valid_from <= day <= rec.cert_id.valid_to):
                raise ValidationError(_('Thời điểm ký %s nằm ngoài hiệu lực chứng thư %s (%s - %s).') % (
                    day.strftime('%d/%m/%Y'), rec.cert_id.display_name,
                    rec.cert_id.valid_from.strftime('%d/%m/%Y'), rec.cert_id.valid_to.strftime('%d/%m/%Y')))


class LfoodReminder(models.Model):
    _inherit = 'lfood.reminder'

    def _collect_extra(self, company, today, horizon):
        out = super()._collect_extra(company, today, horizon)
        for cert in self.env['lfood.digital.cert'].sudo().search([
                ('company_id', '=', company.id), ('valid_to', '<=', horizon + timedelta(days=30))]):
            out.append({'key': 'cert-%s-%s' % (cert.id, cert.valid_to), 'category': 'legal',
                        'title': _('Chứng thư số %s của %s hết hạn, cần gia hạn để không gián đoạn ký hóa đơn, tờ khai')
                        % (cert.serial, cert.provider), 'due_date': cert.valid_to,
                        'res_model': cert._name, 'res_id': cert.id})
        return out
