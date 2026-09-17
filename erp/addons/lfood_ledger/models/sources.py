"""Tự sinh bút toán từ các chứng từ nghiệp vụ.

Nguyên tắc: mỗi chứng từ nguồn có tối đa một bút toán "đang hiệu lực". Khi số liệu ghi sổ của chứng từ đổi
(đưa phiên bản mới vào báo cáo) hoặc chứng từ bị hủy, bút toán cũ được ĐẢO chứ không sửa, rồi lập bút toán mới."""
from odoo import fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import allocate

ASSET_PREFIXES = ('211', '212', '213', '217', '241')


class LfoodServiceVoucher(models.Model):
    _inherit = 'lfood.service.voucher'

    move_ids = fields.One2many('lfood.move', compute='_compute_move_ids', string='Bút toán')
    move_count = fields.Integer('Số bút toán', compute='_compute_move_ids')

    def _compute_move_ids(self):
        Move = self.env['lfood.move'].sudo()
        for rec in self:
            moves = Move.search([('source_model', '=', rec._name), ('source_id', '=', rec.id)])
            rec.move_ids = moves
            rec.move_count = len(moves)

    def _ledger_lines(self, version):
        """Nợ TK chi phí / TSCĐ, Nợ 1331 hoặc 1332 thuế, Có TK công nợ theo nhà cung cấp."""
        partner = version.partner_id or self.partner_id
        lines, payable = [], {}
        for l in version.line_ids:
            lines.append((l.acc_expense, l.amount, 0, None, l.name, l.cost_item_id))
            if l.vat_amount:
                vat_acc = '1332' if (l.acc_expense or '').startswith(ASSET_PREFIXES) else '1331'
                lines.append((vat_acc, l.vat_amount, 0, None, _('Thuế GTGT %s') % l.name, None))
            payable[l.acc_payable] = payable.get(l.acc_payable, 0) + l.amount + l.vat_amount
        for acc, amount in payable.items():
            lines.append((acc, 0, amount, partner, version.memo or self.name, None))
        return lines

    def _ledger_sync(self):
        Move = self.env['lfood.move']
        for rec in self:
            active = Move._active_for(rec)
            want = rec.report_version_id if rec.state in ('posted', 'editing') else False
            key = want and 'version:%s' % want.id
            if active and active.source_key == key:
                continue
            if active:
                active._reverse(date=want.accounting_date if want else None,
                                memo=_('Đảo bút toán %s của chứng từ %s') % (active.name, rec.name))
            if want:
                Move._create_from_source(rec, 'purchase', want.accounting_date, rec._ledger_lines(want),
                                         memo=want.memo or _('Mua dịch vụ %s') % rec.name, key=key, ref=rec.name)

    def action_post(self):
        res = super().action_post()
        self._ledger_sync()
        return res

    def action_approve(self):
        res = super().action_approve()
        self._ledger_sync()
        return res

    def action_apply_to_report(self):
        res = super().action_apply_to_report()
        self._ledger_sync()
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self._ledger_sync()
        return res

    def unlink(self):
        if self.env['lfood.move'].sudo().search_count([('source_model', '=', self._name), ('source_id', 'in', self.ids)]):
            raise UserError(_('Chứng từ đã từng ghi sổ phải lưu trữ theo Luật Kế toán, không xóa được kể cả khi đã hủy.'))
        return super().unlink()

    def action_view_moves(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Bút toán của %s') % self.name, 'res_model': 'lfood.move',
                'view_mode': 'list,form', 'domain': [('source_model', '=', self._name), ('source_id', '=', self.id)]}


class LfoodAssetDepreciation(models.Model):
    _inherit = 'lfood.asset.depreciation'

    def _ledger_sync(self):
        Move = self.env['lfood.move']
        for rec in self:
            active = Move._active_for(rec)
            if rec.state == 'posted' and not active:
                lines = []
                for l in rec.line_ids:
                    label = _('Khấu hao %s %s') % (l.asset_id.code, l.asset_id.name)
                    lines.append((l.account_expense, l.amount, 0, None, label, l.cost_item_id))
                    lines.append((l.account_depreciation, 0, l.amount, None, label, None))
                Move._create_from_source(rec, 'depreciation', rec.date, lines, memo=rec.memo, ref=rec.name)
            elif rec.state != 'posted' and active:
                active._reverse(memo=_('Hủy chứng từ khấu hao %s') % rec.name)

    def action_post(self):
        res = super().action_post()
        self._ledger_sync()
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self._ledger_sync()
        return res


class LfoodAsset(models.Model):
    _inherit = 'lfood.asset'

    counterpart_account = fields.Char('TK đối ứng khi ghi tăng', default='3311',
                                      help='Dùng khi ghi tăng không kèm chứng từ mua: ví dụ 3311 mua chịu, 111 trả tiền mặt, 411 nhận góp vốn')
    dispose_counterpart = fields.Char('TK nhận tiền thanh lý', default='1311', copy=False)
    dispose_partner_id = fields.Many2one('res.partner', 'Người mua thanh lý', copy=False)

    def _voucher_reclass_lines(self):
        """Chứng từ mua đã hạch toán vào TK chi phí (ví dụ 6277): chuyển sang TK nguyên giá và chuyển thuế 1331 sang 1332."""
        version = self.voucher_id.report_version_id
        src = [l for l in version.line_ids if not (l.acc_expense or '').startswith(ASSET_PREFIXES)]
        if not src:
            return []
        label = _('Ghi tăng %s từ %s') % (self.code, self.voucher_id.name)
        shares = allocate(self.original_value, [l.amount for l in src])
        lines = [(self.account_asset, self.original_value, 0, None, label, None)]
        lines += [(l.acc_expense, 0, s, None, label, l.cost_item_id) for l, s in zip(src, shares) if s]
        total_vat, total_amount = sum(l.vat_amount for l in src), sum(l.amount for l in src)
        # nhiều tài sản cùng một chứng từ: chia thuế theo nguyên giá, tài sản cuối nhận phần còn lại cho khớp tới đồng
        Move = self.env['lfood.move']
        siblings = self.search([('voucher_id', '=', self.voucher_id.id), ('id', '!=', self.id), ('state', '!=', 'draft')])
        increase = lambda a: Move._active_for(a).filtered(lambda m: m.source_key == 'increase')
        pending = siblings.filtered(lambda a: not increase(a))
        done_vat = sum(sum(increase(a).line_ids.filtered(lambda l: l.account_code == '1332').mapped('debit'))
                       for a in siblings - pending)
        drafts_left = self.search_count([('voucher_id', '=', self.voucher_id.id), ('state', '=', 'draft')])
        if pending or drafts_left:
            vat = round(total_vat * self.original_value / total_amount) if total_amount else 0
        else:
            vat = total_vat - done_vat
        if vat:
            lines += [('1332', vat, 0, None, label, None), ('1331', 0, vat, None, label, None)]
        return lines

    def action_confirm(self):
        self._require_accountant()
        drafts = self._split_quantity().filtered(lambda a: a.state == 'draft')
        res = super(LfoodAsset, drafts).action_confirm()
        Move = self.env['lfood.move']
        for rec in drafts.filtered(lambda a: a.state == 'running'):
            if rec.voucher_id:
                lines = rec._voucher_reclass_lines()
            else:
                label = _('Ghi tăng %s') % rec.code
                partner = rec.partner_id if self.env['lfood.account'].by_code(rec.counterpart_account).track_partner else None
                lines = [(rec.account_asset, rec.original_value, 0, None, label, None),
                         (rec.counterpart_account, 0, rec.original_value, partner, label, None)]
            if lines:
                Move._create_from_source(rec, 'asset', rec.purchase_date or rec.date_start, lines,
                                         memo=_('Ghi tăng TSCĐ %s %s') % (rec.code, rec.name), key='increase', ref=rec.code)
        return res

    def action_reset_draft(self):
        res = super().action_reset_draft()
        for rec in self:
            for move in self.env['lfood.move']._active_for(rec).filtered(lambda m: m.source_key == 'increase'):
                move._reverse(memo=_('Hủy ghi tăng %s') % move.ref)
        return res

    def _dispose(self, dispose_date, reason, proceeds):
        res = super()._dispose(dispose_date, reason, proceeds)
        accumulated = sum(self.schedule_ids.mapped('amount'))
        residual = self.original_value - accumulated
        label = _('Thanh lý %s') % self.code
        lines = [(self.account_depreciation, accumulated, 0, None, label, None),
                 ('811', residual, 0, None, label, None),
                 (self.account_asset, 0, self.original_value, None, label, None)]
        if proceeds:
            partner = self.dispose_partner_id if self.env['lfood.account'].by_code(self.dispose_counterpart).track_partner else None
            lines += [(self.dispose_counterpart, proceeds, 0, partner, _('Thu thanh lý %s') % self.code, None),
                      ('711', 0, proceeds, None, _('Thu thanh lý %s') % self.code, None)]
        self.env['lfood.move']._create_from_source(self, 'asset', dispose_date, lines,
                                                   memo=_('Thanh lý TSCĐ %s: %s') % (self.code, reason),
                                                   key='dispose', ref=self.code)
        return res


class LfoodAssetDispose(models.TransientModel):
    _inherit = 'lfood.asset.dispose'

    counterpart_account = fields.Char('TK nhận tiền', default='1311', help='1311 bán chịu, 111 thu tiền mặt, 112 chuyển khoản')
    partner_id = fields.Many2one('res.partner', 'Người mua')

    def action_apply(self):
        self.asset_id.with_context(lfood_asset_system=True).write({
            'dispose_counterpart': self.counterpart_account, 'dispose_partner_id': self.partner_id.id})
        return super().action_apply()
