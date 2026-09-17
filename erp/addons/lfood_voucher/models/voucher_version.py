from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .tools import vnd

LINE_DIFF_FIELDS = [
    ('name', 'Tên dịch vụ'), ('acc_expense', 'TK chi phí'), ('acc_payable', 'TK công nợ'),
    ('quantity', 'Số lượng'), ('price_unit', 'Đơn giá'), ('amount', 'Thành tiền'),
    ('vat_rate_id', 'Thuế suất'), ('vat_amount', 'Tiền thuế'), ('cost_item_id', 'Khoản mục CP'),
]
HEADER_DIFF_FIELDS = [
    ('partner_id', 'Nhà cung cấp'), ('accounting_date', 'Ngày hạch toán'), ('document_date', 'Ngày chứng từ'),
    ('memo', 'Diễn giải'), ('invoice_ref', 'Số hóa đơn'),
]


class LfoodServiceVoucherVersion(models.Model):
    _name = 'lfood.service.voucher.version'
    _description = 'Phiên bản chứng từ mua dịch vụ'
    _order = 'voucher_id, number desc'

    voucher_id = fields.Many2one('lfood.service.voucher', 'Chứng từ', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='voucher_id.company_id', store=True)
    number = fields.Integer('Phiên bản', required=True)
    kind = fields.Selection([('original', 'Gốc lúc mua vào'), ('edit', 'Sửa đổi'), ('bulk', 'Điều chỉnh hàng loạt'),
                             ('restore', 'Khôi phục')], 'Loại', required=True, default='edit')
    state = fields.Selection([('draft', 'Đang soạn'), ('saved', 'Đã lưu')], 'Trạng thái', default='draft', required=True)
    source_version_id = fields.Many2one('lfood.service.voucher.version', 'Sửa từ phiên bản')
    reason = fields.Text('Lý do')
    bulk_batch_id = fields.Many2one('lfood.voucher.bulk.batch', 'Lô điều chỉnh', index=True)
    saved_by = fields.Many2one('res.users', 'Người lưu', readonly=True)
    saved_on = fields.Datetime('Thời điểm lưu', readonly=True)

    partner_id = fields.Many2one('res.partner', 'Nhà cung cấp')
    accounting_date = fields.Date('Ngày hạch toán')
    document_date = fields.Date('Ngày chứng từ')
    memo = fields.Char('Diễn giải')
    invoice_ref = fields.Char('Số hóa đơn')

    line_ids = fields.One2many('lfood.service.voucher.line', 'version_id', 'Dòng hạch toán')
    diff_ids = fields.One2many('lfood.voucher.version.diff', 'version_id', 'Thay đổi so với phiên bản trước')
    amount_untaxed = fields.Float('Tổng tiền dịch vụ', digits=(16, 0), compute='_compute_amounts', store=True)
    amount_tax = fields.Float('Thuế GTGT', digits=(16, 0), compute='_compute_amounts', store=True)
    amount_total = fields.Float('Tổng thanh toán', digits=(16, 0), compute='_compute_amounts', store=True)
    is_current = fields.Boolean('Hiện hành', compute='_compute_flags')
    is_report = fields.Boolean('Dùng cho báo cáo', compute='_compute_flags')

    @api.depends('line_ids.amount', 'line_ids.vat_amount')
    def _compute_amounts(self):
        for rec in self:
            rec.amount_untaxed = sum(rec.line_ids.mapped('amount'))
            rec.amount_tax = sum(rec.line_ids.mapped('vat_amount'))
            rec.amount_total = rec.amount_untaxed + rec.amount_tax

    def _compute_flags(self):
        for rec in self:
            rec.is_current = rec.voucher_id.current_version_id == rec
            rec.is_report = rec.voucher_id.report_version_id == rec

    @api.depends('number', 'kind', 'voucher_id.name')
    def _compute_display_name(self):
        kinds = dict(self._fields['kind']._description_selection(self.env))
        for rec in self:
            rec.display_name = '%s · phiên bản %s · %s' % (rec.voucher_id.name or '', rec.number, kinds.get(rec.kind, ''))

    def _header_values(self):
        self.ensure_one()
        return {'partner_id': self.partner_id.id, 'accounting_date': self.accounting_date,
                'document_date': self.document_date, 'memo': self.memo, 'invoice_ref': self.invoice_ref}

    def write(self, vals):
        if not self.env.context.get('lfood_version_system'):
            if self.filtered(lambda v: v.state == 'saved'):
                raise UserError(_('Phiên bản đã lưu không sửa được.'))
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get('lfood_version_system'):
            raise UserError(_('Không xóa được phiên bản chứng từ.'))
        self.mapped('line_ids').with_context(lfood_version_system=True).unlink()
        return super().unlink()

    # ------------------------------------------------------------ so sánh
    @staticmethod
    def _val(rec, fname):
        v = rec[fname]
        if hasattr(v, '_name'):
            return v.display_name or None
        return v if v not in (False, '') else None

    def _compute_diff(self):
        """Ghi các thay đổi so với phiên bản nguồn; trả về danh sách thay đổi."""
        self.ensure_one()
        src = self.source_version_id
        Diff = self.env['lfood.voucher.version.diff']
        rows = []
        if src:
            for f, label in HEADER_DIFF_FIELDS:
                o, n = self._val(src, f), self._val(self, f)
                if o != n:
                    rows.append({'line_label': _('Đầu chứng từ'), 'field': f, 'label': label, 'old': o, 'new': n})
            old_by_origin = {(l.origin_line_id or l).id: l for l in src.line_ids}
            seen = set()
            for line in self.line_ids:
                key = (line.origin_line_id or line).id
                old = old_by_origin.get(key)
                seen.add(key)
                if not old:
                    rows.append({'line_label': line.name, 'field': 'line', 'label': _('Thêm dòng'), 'old': None, 'new': vnd(line.amount)})
                    continue
                for f, label in LINE_DIFF_FIELDS:
                    o, n = self._val(old, f), self._val(line, f)
                    if o != n:
                        rows.append({'line_label': line.name, 'field': f, 'label': label, 'old': o, 'new': n})
            for key, old in old_by_origin.items():
                if key not in seen:
                    rows.append({'line_label': old.name, 'field': 'line', 'label': _('Xóa dòng'), 'old': vnd(old.amount), 'new': None})
        Diff.create([{'version_id': self.id, 'line_label': r['line_label'], 'field': r['field'], 'label': r['label'],
                      'old_value': '' if r['old'] is None else str(r['old']),
                      'new_value': '' if r['new'] is None else str(r['new'])} for r in rows])
        return rows


class LfoodVoucherVersionDiff(models.Model):
    _name = 'lfood.voucher.version.diff'
    _description = 'Thay đổi giữa hai phiên bản'
    _order = 'id'

    version_id = fields.Many2one('lfood.service.voucher.version', 'Phiên bản', required=True, ondelete='cascade', index=True)
    line_label = fields.Char('Dòng')
    field = fields.Char('Trường (kỹ thuật)')
    label = fields.Char('Trường')
    old_value = fields.Char('Giá trị cũ')
    new_value = fields.Char('Giá trị mới')
