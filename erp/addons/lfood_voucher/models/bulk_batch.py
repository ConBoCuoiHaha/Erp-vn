from odoo import fields, models, _
from odoo.exceptions import UserError

from .tools import vnd


class LfoodVoucherBulkBatch(models.Model):
    _name = 'lfood.voucher.bulk.batch'
    _description = 'Lô điều chỉnh hàng loạt'
    _order = 'id desc'

    name = fields.Char('Số lô', readonly=True, default='/')
    user_id = fields.Many2one('res.users', 'Người thực hiện', readonly=True, default=lambda s: s.env.user)
    date = fields.Datetime('Thời điểm', readonly=True, default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', 'Công ty', readonly=True, default=lambda s: s.env.company)
    operation = fields.Char('Thao tác', readonly=True)
    reason = fields.Text('Lý do', readonly=True)
    version_ids = fields.One2many('lfood.service.voucher.version', 'bulk_batch_id', 'Phiên bản tạo ra', readonly=True)
    voucher_count = fields.Integer('Số chứng từ', readonly=True)
    line_count = fields.Integer('Số dòng thay đổi', readonly=True)
    amount_before = fields.Float('Tổng trước', digits=(16, 0), readonly=True)
    amount_after = fields.Float('Tổng sau', digits=(16, 0), readonly=True)
    skipped = fields.Text('Chứng từ bỏ qua', readonly=True)
    state = fields.Selection([('done', 'Đã áp dụng'), ('undone', 'Đã hoàn tác')], 'Trạng thái', default='done', readonly=True)

    def action_undo(self):
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được hoàn tác lô điều chỉnh.'))
        for batch in self.filtered(lambda b: b.state == 'done'):
            restored, blocked = 0, []
            for version in batch.version_ids:
                voucher = version.voucher_id
                if voucher.current_version_id != version or voucher.state != 'posted':
                    blocked.append(voucher.name)
                    continue
                if version.state != 'saved':
                    continue
                source = version.source_version_id
                new = voucher._new_version('restore', source=source)
                voucher.with_context(lfood_voucher_system=True).write(dict(
                    source._header_values(), current_version_id=new.id, state='editing'))
                voucher._save_edit(_('Hoàn tác lô điều chỉnh %s') % batch.name)
                restored += 1
            batch.write({'state': 'undone'})
            self.env['lfood.audit.log']._record_event(
                'bulk', model=batch._name, res_id=batch.id, res_name=batch.name,
                summary=_('Hoàn tác lô %s: khôi phục %s chứng từ%s') % (
                    batch.name, restored, (_('; không hoàn tác được vì đã sửa tiếp: %s') % ', '.join(blocked)) if blocked else ''))
        return True

    def action_view_vouchers(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Chứng từ trong lô %s') % self.name,
                'res_model': 'lfood.service.voucher', 'view_mode': 'list,form',
                'domain': [('id', 'in', self.version_ids.mapped('voucher_id').ids)]}

    def _summary_text(self):
        return _('%s chứng từ, %s dòng; tổng %s → %s') % (self.voucher_count, self.line_count, vnd(self.amount_before), vnd(self.amount_after))
