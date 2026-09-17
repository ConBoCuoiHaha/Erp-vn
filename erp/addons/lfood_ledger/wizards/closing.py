from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.lfood_voucher.models.tools import vnd


def balances(env, company, date_to, prefixes):
    """Số dư Nợ trừ Có lũy kế đến ngày, theo tài khoản chi tiết có số hiệu bắt đầu bằng các tiền tố."""
    env['lfood.move.line'].flush_model()
    env.cr.execute("""
        SELECT a.code, SUM(l.balance)
        FROM lfood_move_line l JOIN lfood_account a ON a.id = l.account_id
        WHERE l.company_id = %s AND l.state = 'posted' AND l.date <= %s
          AND a.code LIKE ANY(%s)
        GROUP BY a.code HAVING ROUND(SUM(l.balance)) <> 0 ORDER BY a.code
    """, (company.id, date_to, ['%s%%' % p for p in prefixes]))
    return [(code, round(bal)) for code, bal in env.cr.fetchall()]


class LfoodClosing(models.TransientModel):
    _name = 'lfood.closing'
    _description = 'Kết chuyển cuối kỳ'

    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company)
    date_to = fields.Date('Kết chuyển đến ngày', required=True)
    preview = fields.Html('Xem trước', readonly=True, sanitize=False)

    def _lines(self):
        """Theo Thông tư 99: 621, 622, 627 sang 154; 521 giảm 511; doanh thu, thu nhập, chi phí sang 911; 911 sang 4212."""
        env, c, d = self.env, self.company_id, self.date_to
        lines = []
        for code, bal in balances(env, c, d, ['621', '622', '623', '627']):
            lines += [('154', bal, 0, None, _('Kết chuyển %s sang 154') % code, None), (code, 0, bal, None, _('Kết chuyển %s sang 154') % code, None)]
        for code, bal in balances(env, c, d, ['521']):
            lines += [('511', bal, 0, None, _('Kết chuyển giảm trừ doanh thu'), None), (code, 0, bal, None, _('Kết chuyển giảm trừ doanh thu'), None)]
        result = 0
        # sau bước 521 thì số dư 511 giảm tương ứng
        adj = {'511': sum(b for _, b in balances(env, c, d, ['521']))}
        for code, bal in balances(env, c, d, ['511', '515', '711']):
            bal += adj.pop(code, 0)
            if bal:
                lines += [(code, -bal, 0, None, _('Kết chuyển %s sang 911') % code, None), ('911', 0, -bal, None, _('Kết chuyển %s sang 911') % code, None)]
                result -= bal
        for code, bal in balances(env, c, d, ['632', '635', '641', '642', '811', '821']):
            lines += [('911', bal, 0, None, _('Kết chuyển %s sang 911') % code, None), (code, 0, bal, None, _('Kết chuyển %s sang 911') % code, None)]
            result -= bal
        if result > 0:
            lines += [('911', result, 0, None, _('Kết chuyển lãi'), None), ('4212', 0, result, None, _('Kết chuyển lãi'), None)]
        elif result < 0:
            lines += [('4212', -result, 0, None, _('Kết chuyển lỗ'), None), ('911', 0, -result, None, _('Kết chuyển lỗ'), None)]
        # dòng âm (số dư ngược chiều) thì đổi bên cho đúng quy tắc ghi Nợ/Có không âm
        fixed = []
        for acc, dr, cr, p, n, ci in lines:
            if dr < 0 or cr < 0:
                dr, cr = -cr, -dr
            fixed.append((acc, dr, cr, p, n, ci))
        return fixed, result

    def action_preview(self):
        self.ensure_one()
        lines, result = self._lines()
        rows = ''.join('<tr><td>%s</td><td style="text-align:right">%s</td><td style="text-align:right">%s</td><td>%s</td></tr>'
                       % (a, vnd(dr) if dr else '', vnd(cr) if cr else '', n) for a, dr, cr, p, n, ci in lines)
        self.preview = ('<div class="o_lfood_changes"><table><tr><th>TK</th><th>Nợ</th><th>Có</th><th>Diễn giải</th></tr>%s</table></div>'
                        '<p><b>Kết quả kinh doanh đến ngày: %s</b></p>') % (rows or '<tr><td colspan="4">Không còn số dư để kết chuyển</td></tr>',
                                                                             ('Lãi ' if result >= 0 else 'Lỗ ') + vnd(abs(result)))
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'new'}

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được kết chuyển cuối kỳ.'))
        lines, result = self._lines()
        if not lines:
            raise UserError(_('Không còn số dư để kết chuyển đến ngày %s.') % self.date_to.strftime('%d/%m/%Y'))
        move = self.env['lfood.move']._create_from_source(
            self.company_id, 'closing', self.date_to, lines, company=self.company_id,
            memo=_('Kết chuyển cuối kỳ đến %s') % self.date_to.strftime('%d/%m/%Y'),
            key='closing:%s' % self.date_to, ref=_('KC %s') % self.date_to.strftime('%m/%Y'))
        self.env['lfood.audit.log']._record_event('state', model='lfood.move', res_id=move.id, res_name=move.name,
                                                  company_id=self.company_id.id,
                                                  summary=_('Kết chuyển cuối kỳ đến %s, %s %s') % (
                                                      self.date_to.strftime('%d/%m/%Y'), 'lãi' if result >= 0 else 'lỗ', vnd(abs(result))))
        return {'type': 'ir.actions.act_window', 'res_model': 'lfood.move', 'res_id': move.id, 'view_mode': 'form'}


class LfoodLock(models.TransientModel):
    _name = 'lfood.lock'
    _description = 'Khóa sổ kế toán'

    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company)
    current_lock = fields.Date(related='company_id.lfood_lock_date', string='Đang khóa đến')
    lock_date = fields.Date('Khóa sổ đến ngày', required=True)
    reason = fields.Char('Lý do', required=True)
    draft_count = fields.Integer('Chứng từ chưa ghi sổ trong kỳ', compute='_compute_draft_count')

    @api.depends('lock_date', 'company_id')
    def _compute_draft_count(self):
        for rec in self:
            if not rec.lock_date:
                rec.draft_count = 0
                continue
            dom = [('company_id', '=', rec.company_id.id), ('state', '=', 'draft')]
            rec.draft_count = (
                self.env['lfood.move'].sudo().search_count(dom + [('date', '<=', rec.lock_date)])
                + self.env['lfood.payment'].sudo().search_count(dom + [('date', '<=', rec.lock_date)])
                + self.env['lfood.service.voucher'].sudo().search_count(
                    [('company_id', '=', rec.company_id.id), ('state', 'in', ('draft', 'waiting', 'editing')),
                     ('accounting_date', '<=', rec.lock_date)])
                + self.env['lfood.asset.depreciation'].sudo().search_count(dom + [('date', '<=', rec.lock_date)]))

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được khóa, mở khóa sổ.'))
        if self.draft_count and (not self.current_lock or self.lock_date > self.current_lock):
            raise UserError(_('Còn %s chứng từ Nháp, Chờ duyệt hoặc Đang sửa đến ngày %s. Xử lý xong mới khóa sổ.')
                            % (self.draft_count, self.lock_date.strftime('%d/%m/%Y')))
        old = self.current_lock
        self.company_id.sudo().with_context(lfood_audit_skip=True).write({'lfood_lock_date': self.lock_date})
        opening = old and self.lock_date < old
        self.env['lfood.audit.log']._record_event(
            'config', model='res.company', res_id=self.company_id.id, res_name=self.company_id.name, company_id=self.company_id.id,
            summary=_('%s sổ kế toán: từ %s thành %s. Lý do: %s') % (
                'MỞ KHÓA' if opening else 'Khóa', old.strftime('%d/%m/%Y') if old else 'chưa khóa',
                self.lock_date.strftime('%d/%m/%Y'), self.reason))
        return {'type': 'ir.actions.act_window_close'}
