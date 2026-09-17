"""Lưu trữ chứng từ điện tử (HT08).

Luật Kế toán 2015 (Điều 41) và Nghị định 174/2016/NĐ-CP: chứng từ dùng trực tiếp ghi sổ, lập báo cáo tài chính lưu
tối thiểu 10 năm (Điều 13); tài liệu không dùng trực tiếp ghi sổ lưu tối thiểu 5 năm (Điều 12); thời hạn tính từ
ngày kết thúc kỳ kế toán năm; được lưu trên phương tiện điện tử nếu bảo đảm an toàn, toàn vẹn, truy cập được.
App lưu tệp kèm mã SHA-256 lúc tải lên để kiểm tra toàn vẹn; không sửa tệp, không xóa trước hạn.
"""
import base64
import hashlib
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

DOC_TYPES = [('invoice', 'Hóa đơn'), ('contract', 'Hợp đồng'), ('minutes', 'Biên bản'), ('bank', 'Chứng từ ngân hàng'),
             ('decision', 'Quyết định, tờ trình'), ('tax', 'Hồ sơ thuế'), ('other', 'Khác')]


class LfoodArchivePolicy(models.Model):
    _name = 'lfood.archive.policy'
    _description = 'Thời hạn lưu trữ'
    _order = 'years desc, name'

    name = fields.Char('Nhóm tài liệu', required=True)
    years = fields.Integer('Số năm lưu tối thiểu', required=True)
    legal_ref = fields.Char('Căn cứ')

    @api.constrains('years')
    def _check_years(self):
        for rec in self:
            if rec.years < 5:
                raise ValidationError(_('Thời hạn lưu trữ tài liệu kế toán tối thiểu 5 năm.'))


class LfoodDocument(models.Model):
    _name = 'lfood.document'
    _description = 'Hồ sơ lưu trữ'
    _order = 'doc_date desc, id desc'

    name = fields.Char('Tên tài liệu', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    doc_type = fields.Selection(DOC_TYPES, 'Loại', required=True, default='invoice')
    doc_date = fields.Date('Ngày tài liệu', required=True, default=fields.Date.context_today)
    ref = fields.Char('Số hiệu')
    res_ref = fields.Reference(selection='_ref_models', string='Chứng từ trên app')
    policy_id = fields.Many2one('lfood.archive.policy', 'Nhóm lưu trữ', required=True,
                                default=lambda s: s.env.ref('lfood_archive.policy_accounting', raise_if_not_found=False))
    file = fields.Binary('Tệp', required=True, attachment=True)
    file_name = fields.Char('Tên tệp')
    checksum = fields.Char('Mã kiểm tra SHA-256', readonly=True, copy=False)
    retain_until = fields.Date('Lưu đến hết ngày', compute='_compute_retain', store=True)
    intact = fields.Boolean('Tệp còn nguyên vẹn', compute='_compute_intact')
    note = fields.Char('Ghi chú')

    @api.model
    def _ref_models(self):
        models_ = self.env['ir.model'].sudo().search([('model', '=like', 'lfood.%'), ('transient', '=', False)])
        return [(m.model, m.name) for m in models_]

    @api.depends('doc_date', 'policy_id.years')
    def _compute_retain(self):
        for rec in self:
            # tính từ ngày kết thúc kỳ kế toán năm (năm dương lịch)
            rec.retain_until = date(rec.doc_date.year + rec.policy_id.years, 12, 31) if rec.doc_date and rec.policy_id else False

    @staticmethod
    def _digest(data):
        return hashlib.sha256(base64.b64decode(data)).hexdigest() if data else False

    def _compute_intact(self):
        for rec in self:
            rec.intact = bool(rec.checksum) and self._digest(rec.with_context(bin_size=False).file) == rec.checksum

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['checksum'] = self._digest(vals.get('file'))
        recs = super().create(vals_list)
        for rec in recs:
            self.env['lfood.audit.log']._record_event(
                'create', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Lưu trữ %s (%s), lưu đến %s') % (rec.name, rec.file_name or '', rec.retain_until))
        return recs

    def write(self, vals):
        if 'file' in vals or 'checksum' in vals:
            raise UserError(_('Không thay tệp đã lưu trữ. Tải lên bản mới thành hồ sơ khác và ghi chú lý do.'))
        if {'doc_date', 'policy_id'} & set(vals):
            shorter = self.filtered(lambda r: r.policy_id.years > self.env['lfood.archive.policy'].browse(
                vals.get('policy_id', r.policy_id.id)).years or (vals.get('doc_date') and str(vals['doc_date']) < str(r.doc_date)))
            if shorter:
                raise UserError(_('Không được rút ngắn thời hạn lưu trữ.'))
        return super().write(vals)

    def unlink(self):
        today = fields.Date.context_today(self)
        locked = self.filtered(lambda r: r.retain_until and r.retain_until >= today)
        if locked:
            raise UserError(_('Hồ sơ còn trong thời hạn lưu trữ (đến %s), không xóa được.') % locked[0].retain_until.strftime('%d/%m/%Y'))
        for rec in self:
            self.env['lfood.audit.log']._record_event(
                'unlink', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Hủy hồ sơ hết hạn lưu trữ %s') % rec.name)
        return super().unlink()


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.ondelete(at_uninstall=False)
    def _unlink_except_archived(self):
        docs = self.filtered(lambda a: a.res_model == 'lfood.document' and a.res_id)
        if docs and self.env['lfood.document'].sudo().search_count([
                ('id', 'in', docs.mapped('res_id')), ('retain_until', '>=', fields.Date.context_today(self))]):
            raise UserError(_('Tệp thuộc hồ sơ còn trong thời hạn lưu trữ, không xóa được.'))
