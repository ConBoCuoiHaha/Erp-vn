from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..models.tools import allocate, vnd

OPERATIONS = [
    ('scale_percent', 'Tăng / giảm thành tiền theo %'),
    ('distribute_total', 'Đặt tổng mới, tự chia cho các dòng theo tỷ trọng'),
    ('set_price', 'Đặt đơn giá mới (thành tiền tự tính lại)'),
    ('set_cost_item', 'Đổi khoản mục chi phí'),
    ('set_acc_expense', 'Đổi tài khoản chi phí'),
    ('set_acc_payable', 'Đổi tài khoản công nợ'),
    ('set_vat_rate', 'Đổi thuế suất GTGT'),
    ('set_accounting_date', 'Đổi ngày hạch toán'),
    ('replace_memo', 'Tìm và thay chữ trong diễn giải'),
]
LINE_OPS = {'scale_percent', 'distribute_total', 'set_price', 'set_cost_item', 'set_acc_expense', 'set_acc_payable', 'set_vat_rate'}


class LfoodVoucherBulk(models.TransientModel):
    _name = 'lfood.voucher.bulk'
    _description = 'Điều chỉnh chứng từ hàng loạt'

    voucher_ids = fields.Many2many('lfood.service.voucher', string='Chứng từ được chọn')
    voucher_count = fields.Integer('Số chứng từ', compute='_compute_count')

    # chọn nhanh chứng từ theo điều kiện
    pick_date_from = fields.Date('Ngày hạch toán từ')
    pick_date_to = fields.Date('Đến ngày')
    pick_partner_id = fields.Many2one('res.partner', 'Nhà cung cấp')
    pick_cost_item_id = fields.Many2one('lfood.cost.item', 'Có dòng thuộc khoản mục')
    pick_state = fields.Selection([('posted', 'Đã cất'), ('draft', 'Nháp'), ('both', 'Đã cất và Nháp')],
                                  'Trạng thái', default='posted')
    operation = fields.Selection(OPERATIONS, 'Thao tác', required=True, default='scale_percent')

    scope = fields.Selection([('all', 'Mọi dòng'), ('cost_item', 'Dòng thuộc khoản mục'),
                              ('service_code', 'Dòng có mã dịch vụ'), ('acc_expense', 'Dòng có tài khoản chi phí')],
                             'Áp dụng cho', default='all', required=True)
    scope_cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục (gồm cả khoản con)')
    scope_text = fields.Char('Mã dịch vụ / tài khoản')

    percent = fields.Float('Tỷ lệ %', help='Ví dụ 10 là tăng 10%, -5 là giảm 5%')
    new_total = fields.Float('Tổng mới', digits=(16, 0))
    new_price = fields.Float('Đơn giá mới', digits=(16, 2))
    new_cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục mới')
    new_text = fields.Char('Tài khoản mới')
    new_vat_rate_id = fields.Many2one('lfood.vat.rate', 'Thuế suất mới')
    new_date = fields.Date('Ngày hạch toán mới')
    find_text = fields.Char('Tìm chữ')
    replace_text = fields.Char('Thay bằng')
    reason = fields.Text('Lý do điều chỉnh')

    state = fields.Selection([('edit', 'Nhập'), ('preview', 'Xem trước')], default='edit')
    preview_ids = fields.One2many('lfood.voucher.bulk.preview', 'wizard_id', 'Xem trước thay đổi')
    total_before = fields.Float('Tổng trước', digits=(16, 0), readonly=True)
    total_after = fields.Float('Tổng sau', digits=(16, 0), readonly=True)
    skipped_note = fields.Text('Bỏ qua', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ids = self.env.context.get('active_ids') if self.env.context.get('active_model') == 'lfood.service.voucher' else None
        if ids:
            res['voucher_ids'] = [(6, 0, ids)]
        return res

    def action_pick_vouchers(self):
        self.ensure_one()
        domain = [('company_id', 'in', self.env.companies.ids)]
        domain.append(('state', 'in', ['posted', 'draft'] if self.pick_state == 'both' else [self.pick_state or 'posted']))
        if self.pick_date_from:
            domain.append(('accounting_date', '>=', self.pick_date_from))
        if self.pick_date_to:
            domain.append(('accounting_date', '<=', self.pick_date_to))
        if self.pick_partner_id:
            domain.append(('partner_id', '=', self.pick_partner_id.id))
        if self.pick_cost_item_id:
            domain.append(('line_ids.cost_item_id', 'child_of', self.pick_cost_item_id.id))
        found = self.env['lfood.service.voucher'].search(domain)
        if not found:
            raise UserError(_('Không có chứng từ nào khớp điều kiện.'))
        self.voucher_ids = [(6, 0, found.ids)]
        return self._reopen()

    @api.depends('voucher_ids')
    def _compute_count(self):
        for rec in self:
            rec.voucher_count = len(rec.voucher_ids)

    # ------------------------------------------------------------ lọc dòng
    def _match(self, line):
        if self.scope == 'all':
            return True
        if self.scope == 'cost_item':
            return bool(self.scope_cost_item_id and line.cost_item_id and
                        ('/%s/' % self.scope_cost_item_id.id) in ('/' + (line.cost_item_id.parent_path or '')))
        if self.scope == 'service_code':
            return (line.service_code or '').strip().lower() == (self.scope_text or '').strip().lower()
        if self.scope == 'acc_expense':
            return (line.acc_expense or '').strip() == (self.scope_text or '').strip()
        return False

    def _validate(self):
        op = self.operation
        need = {
            'distribute_total': self.new_total > 0 or op != 'distribute_total',
            'set_cost_item': bool(self.new_cost_item_id),
            'set_acc_expense': bool(self.new_text), 'set_acc_payable': bool(self.new_text),
            'set_vat_rate': bool(self.new_vat_rate_id), 'set_accounting_date': bool(self.new_date),
            'replace_memo': bool(self.find_text), 'set_price': self.new_price >= 0,
        }
        if not need.get(op, True):
            raise UserError(_('Chưa nhập giá trị mới cho thao tác đã chọn.'))
        if op == 'distribute_total' and self.new_total <= 0:
            raise UserError(_('Tổng mới phải lớn hơn 0.'))
        if self.scope in ('service_code', 'acc_expense') and not self.scope_text:
            raise UserError(_('Chưa nhập mã dịch vụ hoặc tài khoản để lọc dòng.'))
        if self.scope == 'cost_item' and not self.scope_cost_item_id:
            raise UserError(_('Chưa chọn khoản mục để lọc dòng.'))
        if not self.voucher_ids:
            raise UserError(_('Chưa chọn chứng từ nào.'))

    # ------------------------------------------------------------ tính kế hoạch thay đổi
    def _plan(self):
        """Trả về (kế hoạch theo chứng từ, danh sách bỏ qua). Không ghi gì vào dữ liệu."""
        self._validate()
        op = self.operation
        plans, skipped = [], []
        targets = []
        for v in self.voucher_ids:
            if v.state not in ('draft', 'posted'):
                skipped.append('%s (%s)' % (v.name, dict(v._fields['state']._description_selection(self.env))[v.state]))
                continue
            lines = v.line_ids.filtered(self._match) if op in LINE_OPS else v.line_ids
            if op in LINE_OPS and not lines:
                skipped.append('%s (không có dòng phù hợp)' % v.name)
                continue
            targets.append((v, lines))

        new_amounts = {}
        if op == 'distribute_total':
            pool = [l for _v, ls in targets for l in ls if not l.locked]
            locked = sum(l.amount for _v, ls in targets for l in ls if l.locked)
            rest = round(self.new_total) - locked
            if rest < 0:
                raise UserError(_('Tổng mới nhỏ hơn tổng các dòng đang khóa (%s).') % vnd(locked))
            for l, part in zip(pool, allocate(rest, [l.amount for l in pool])):
                new_amounts[l.id] = part

        for v, lines in targets:
            header, line_changes = {}, []
            if op == 'set_accounting_date':
                header['accounting_date'] = (v.accounting_date, self.new_date)
            elif op == 'replace_memo':
                memo = v.memo or ''
                if self.find_text in memo:
                    header['memo'] = (memo, memo.replace(self.find_text, self.replace_text or ''))
            for l in lines:
                ch = {}
                if op == 'scale_percent' and not l.locked:
                    ch['amount'] = (l.amount, round(l.amount * (1 + self.percent / 100.0)))
                elif op == 'distribute_total' and l.id in new_amounts:
                    ch['amount'] = (l.amount, new_amounts[l.id])
                elif op == 'set_price' and not l.locked:
                    ch['price_unit'] = (l.price_unit, self.new_price)
                    ch['amount'] = (l.amount, round(l.quantity * self.new_price))
                elif op == 'set_cost_item':
                    ch['cost_item_id'] = (l.cost_item_id, self.new_cost_item_id)
                elif op == 'set_acc_expense':
                    ch['acc_expense'] = (l.acc_expense, self.new_text)
                elif op == 'set_acc_payable':
                    ch['acc_payable'] = (l.acc_payable, self.new_text)
                elif op == 'set_vat_rate':
                    ch['vat_rate_id'] = (l.vat_rate_id, self.new_vat_rate_id)
                ch = {k: val for k, val in ch.items() if val[0] != val[1]}
                if ch:
                    line_changes.append((l, ch))
            header = {k: val for k, val in header.items() if val[0] != val[1]}
            if header or line_changes:
                plans.append({'voucher': v, 'header': header, 'lines': line_changes})
            else:
                skipped.append('%s (không có gì thay đổi)' % v.name)
        return plans, skipped

    def _label(self, value):
        if hasattr(value, '_name'):
            return value.display_name or ''
        if isinstance(value, float):
            return vnd(value) if value == round(value) else ('%.2f' % value)
        return '' if value in (None, False) else str(value)

    def action_preview(self):
        self.ensure_one()
        plans, skipped = self._plan()
        labels = {'amount': 'Thành tiền', 'price_unit': 'Đơn giá', 'cost_item_id': 'Khoản mục CP', 'acc_expense': 'TK chi phí',
                  'acc_payable': 'TK công nợ', 'vat_rate_id': 'Thuế suất', 'accounting_date': 'Ngày hạch toán', 'memo': 'Diễn giải'}
        rows, before, after = [], 0.0, 0.0
        for p in plans:
            v = p['voucher']
            for f, (o, n) in p['header'].items():
                rows.append({'voucher_id': v.id, 'line_label': 'Đầu chứng từ', 'field_label': labels[f],
                             'old_value': self._label(o), 'new_value': self._label(n), 'diff': 0})
            for l, ch in p['lines']:
                for f, (o, n) in ch.items():
                    diff = (n - o) if f == 'amount' else 0
                    rows.append({'voucher_id': v.id, 'line_label': l.name, 'field_label': labels[f],
                                 'old_value': self._label(o), 'new_value': self._label(n), 'diff': diff})
            before += v.amount_untaxed
            after += v.amount_untaxed + sum((ch['amount'][1] - ch['amount'][0]) for _l, ch in p['lines'] if 'amount' in ch)
        self.preview_ids.unlink()
        self.write({'preview_ids': [(0, 0, r) for r in rows], 'state': 'preview', 'total_before': before,
                    'total_after': after, 'skipped_note': '\n'.join(skipped) or False})
        return self._reopen()

    def action_back(self):
        self.write({'state': 'edit'})
        self.preview_ids.unlink()
        return self._reopen()

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new', 'name': _('Điều chỉnh hàng loạt')}

    # ------------------------------------------------------------ áp dụng
    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được điều chỉnh hàng loạt.'))
        if not (self.reason or '').strip():
            raise UserError(_('Phải nhập lý do điều chỉnh.'))
        plans, skipped = self._plan()  # tính lại, không dùng số của màn xem trước
        if not plans:
            raise UserError(_('Không có chứng từ nào thay đổi.'))
        op_label = dict(OPERATIONS)[self.operation]
        batch = self.env['lfood.voucher.bulk.batch'].create({
            'name': self.env['ir.sequence'].next_by_code('lfood.voucher.bulk.batch') or '/',
            'operation': op_label, 'reason': self.reason, 'skipped': '\n'.join(skipped) or False})
        before = after = 0.0
        line_count = 0
        for p in plans:
            v = p['voucher']
            before += v.amount_untaxed
            if v.state == 'posted':
                version = v._new_version('bulk', batch=batch)
                v.with_context(lfood_voucher_system=True).write({'current_version_id': version.id, 'state': 'editing'})
                lines_by_origin = {(l.origin_line_id or l).id: l for l in version.line_ids}
            else:
                lines_by_origin = {(l.origin_line_id or l).id: l for l in v.line_ids}
            if p['header']:
                v.with_context(lfood_voucher_system=True).write({f: (n.id if hasattr(n, '_name') else n)
                                                                  for f, (_o, n) in p['header'].items()})
            for l, ch in p['lines']:
                target = lines_by_origin.get((l.origin_line_id or l).id)
                vals = {f: (n.id if hasattr(n, '_name') else n) for f, (_o, n) in ch.items()}
                if 'amount' in vals and 'price_unit' not in vals and target.quantity:
                    vals['price_unit'] = round(vals['amount'] / target.quantity, 2)
                target.write(vals)
                line_count += 1
            if v.state == 'editing':
                v._save_edit(_('Lô %s: %s. %s') % (batch.name, op_label, self.reason))
            after += v.amount_untaxed
        batch.write({'voucher_count': len(plans), 'line_count': line_count, 'amount_before': before, 'amount_after': after})
        self.env['lfood.audit.log']._record_event(
            'bulk', model=batch._name, res_id=batch.id, res_name=batch.name,
            summary=_('Điều chỉnh hàng loạt %s: %s. %s. Lý do: %s') % (batch.name, op_label, batch._summary_text(), self.reason),
            changes=[{'field': 'vouchers', 'label': 'Chứng từ', 'old': None, 'new': [p['voucher'].name for p in plans]},
                     {'field': 'skipped', 'label': 'Bỏ qua', 'old': None, 'new': skipped}])
        return {'type': 'ir.actions.act_window', 'res_model': batch._name, 'res_id': batch.id, 'view_mode': 'form',
                'name': _('Lô điều chỉnh %s') % batch.name, 'target': 'current'}


class LfoodVoucherBulkPreview(models.TransientModel):
    _name = 'lfood.voucher.bulk.preview'
    _description = 'Xem trước điều chỉnh hàng loạt'

    wizard_id = fields.Many2one('lfood.voucher.bulk', required=True, ondelete='cascade')
    voucher_id = fields.Many2one('lfood.service.voucher', 'Chứng từ')
    line_label = fields.Char('Dòng')
    field_label = fields.Char('Trường')
    old_value = fields.Char('Trước')
    new_value = fields.Char('Sau')
    diff = fields.Float('Chênh lệch', digits=(16, 0))
