"""Nhắc hạn tự động (HT12, CH07).

Mỗi ngày app quét các nguồn và cập nhật danh sách việc sắp đến hạn:
- tờ khai thuế GTGT kỳ trước chưa xác nhận (hạn lấy từ phân hệ thuế GTGT);
- tạm nộp thuế TNDN quý trước chưa ghi sổ (hạn lấy từ phân hệ thuế TNDN);
- hợp đồng lao động sắp hết hạn;
- lô hàng còn tồn sắp hết hạn dùng, đã hết hạn;
- hóa đơn bán quá hạn thanh toán còn phải thu;
- tham số pháp lý sắp hết thời gian áp dụng.
Việc không còn điều kiện (đã nộp, đã gia hạn, đã thu) tự chuyển sang Đã xử lý.
"""
from datetime import date, timedelta

from odoo import api, fields, models, _

CATEGORIES = [('tax', 'Thuế'), ('hr', 'Nhân sự'), ('stock', 'Kho'), ('receivable', 'Công nợ'), ('loan', 'Vay'),
              ('legal', 'Tham số pháp lý')]


AUTO_CLOSED = 'Tự đóng'


class ResCompany(models.Model):
    _inherit = 'res.company'

    lfood_remind_days = fields.Integer('Nhắc trước (ngày)', default=30)


class LfoodReminder(models.Model):
    _name = 'lfood.reminder'
    _description = 'Việc sắp đến hạn'
    _order = 'state, due_date, id'

    key = fields.Char(required=True, index=True, readonly=True)
    company_id = fields.Many2one('res.company', 'Công ty', index=True, readonly=True)
    category = fields.Selection(CATEGORIES, 'Nhóm', required=True, readonly=True)
    title = fields.Char('Nội dung', required=True, readonly=True)
    due_date = fields.Date('Hạn', required=True, readonly=True, index=True)
    days_left = fields.Integer('Còn (ngày)', compute='_compute_days_left')
    res_model = fields.Char(readonly=True)
    res_id = fields.Integer(readonly=True)
    state = fields.Selection([('open', 'Cần xử lý'), ('done', 'Đã xử lý')], 'Trạng thái', default='open',
                             required=True, readonly=True, index=True)
    done_note = fields.Char('Ghi chú xử lý', readonly=True)

    _key_uniq = models.Constraint('unique(key)', 'Việc nhắc đã tồn tại.')

    def _compute_days_left(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.days_left = (rec.due_date - today).days

    def action_done(self):
        self.filtered(lambda r: r.state == 'open').write({'state': 'done', 'done_note': _('Đánh dấu bởi %s') % self.env.user.name})
        return True

    def action_open(self):
        self.ensure_one()
        if not self.res_model:
            return False
        return {'type': 'ir.actions.act_window', 'res_model': self.res_model, 'res_id': self.res_id, 'view_mode': 'form'}

    # ---- nguồn nhắc: mỗi hàm trả về [dict(key, company_id, category, title, due_date, res_model, res_id)]
    def _collect_tax(self, company, today):
        out = []
        Vat = self.env['lfood.vat.return'].sudo()
        if company.lfood_vat_period == 'quarter':
            q = (today.month - 1) // 3  # quý trước
            year, period = (today.year, {'period_type': 'quarter', 'quarter': q}) if q else \
                (today.year - 1, {'period_type': 'quarter', 'quarter': 4})
        else:
            prev = today.replace(day=1) - timedelta(days=1)
            year, period = prev.year, {'period_type': 'month', 'month': prev.month}
        probe = Vat.new(dict(period, year=year, company_id=company.id))
        done = Vat.search_count([('company_id', '=', company.id), ('state', '=', 'confirmed'),
                                 ('date_from', '=', probe.date_from), ('date_to', '=', probe.date_to)])
        if not done:
            out.append({'key': 'vat-%s-%s' % (company.id, probe.date_from), 'category': 'tax',
                        'title': _('Nộp tờ khai %s') % probe.name, 'due_date': probe.due_date,
                        'res_model': 'lfood.vat.return', 'res_id': 0})
        Cit = self.env['lfood.cit.provisional'].sudo()
        q = (today.month - 1) // 3
        cyear, cq = (today.year, q) if q else (today.year - 1, 4)
        probe = Cit.new({'year': cyear, 'quarter': str(cq), 'company_id': company.id})
        rec = Cit.search([('company_id', '=', company.id), ('year', '=', cyear), ('quarter', '=', str(cq))], limit=1)
        if rec.state != 'posted':
            out.append({'key': 'cit-%s-%s-%s' % (company.id, cyear, cq), 'category': 'tax',
                        'title': _('Tạm nộp thuế TNDN quý %s/%s') % (cq, cyear), 'due_date': probe.date_due,
                        'res_model': 'lfood.cit.provisional', 'res_id': rec.id})
        return out

    def _collect_hr(self, company, today, horizon):
        contracts = self.env['lfood.hr.contract'].sudo().search([
            ('company_id', '=', company.id), ('state', '=', 'running'),
            ('date_end', '!=', False), ('date_end', '<=', horizon)])
        return [{'key': 'hdld-%s-%s' % (c.id, c.date_end), 'category': 'hr',
                 'title': _('Hợp đồng %s của %s hết hạn') % (c.name, c.employee_id.name), 'due_date': c.date_end,
                 'res_model': c._name, 'res_id': c.id} for c in contracts]

    def _collect_stock(self, company, today, horizon):
        out = []
        warehouses = self.env['lfood.warehouse'].sudo().search([('company_id', '=', company.id)])
        lots = self.env['lfood.stock.lot'].sudo().search([('expiry_date', '!=', False), ('expiry_date', '<=', horizon)])
        for lot in lots:
            qty = sum(lot.product_id._position(wh, lot)[0] for wh in warehouses)
            if qty > 0:
                word = _('đã hết hạn') if lot.expiry_date < today else _('sắp hết hạn')
                out.append({'key': 'lot-%s-%s' % (company.id, lot.id), 'category': 'stock',
                            'title': _('Lô %s của %s %s, còn %s %s') % (
                                lot.name, lot.product_id.display_name, word, '%g' % qty, lot.product_id.uom),
                            'due_date': lot.expiry_date, 'res_model': lot._name, 'res_id': lot.id})
        return out

    def _collect_receivable(self, company, today, horizon):
        invoices = self.env['lfood.sale.invoice'].sudo().search([
            ('company_id', '=', company.id), ('state', '=', 'posted'), ('kind', '=', 'invoice'),
            ('due_date', '!=', False), ('due_date', '<', today)])
        return [{'key': 'ar-%s' % inv.id, 'category': 'receivable',
                 'title': _('Hóa đơn %s của %s quá hạn, còn phải thu %s') % (
                     inv.invoice_number or inv.name, inv.partner_id.name, '{:,.0f}'.format(inv.amount_residual).replace(',', '.')),
                 'due_date': inv.due_date, 'res_model': inv._name, 'res_id': inv.id}
                for inv in invoices if inv.amount_residual > 0]

    def _collect_loan(self, company, today, horizon):
        """Kỳ trả gốc vay chưa trả đủ đến hạn trong khoảng nhắc (số đã trả tính cho các kỳ sớm nhất)."""
        out = []
        for loan in self.env['lfood.loan'].sudo().search([('company_id', '=', company.id), ('state', '=', 'running')]):
            paid = loan.principal_paid
            for s in loan.schedule_ids:
                covered = min(paid, s.amount)
                paid -= covered
                left = s.amount - covered
                if left > 0 and s.due_date <= horizon:
                    out.append({'key': 'loan-%s-%s' % (s.id, s.due_date), 'category': 'loan',
                                'title': _('Trả gốc vay %s cho %s: %s') % (
                                    loan.contract_ref, loan.partner_id.name, '{:,.0f}'.format(left).replace(',', '.')),
                                'due_date': s.due_date, 'res_model': loan._name, 'res_id': loan.id})
        return out

    def _collect_extra(self, company, today, horizon):
        """Phân hệ khác ghi đè để thêm việc nhắc."""
        return []

    def _collect_legal(self, today, horizon):
        values = self.env['lfood.legal.param.value'].sudo().search([
            ('state', '=', 'approved'), ('date_to', '!=', False), ('date_to', '>=', today), ('date_to', '<=', horizon)])
        return [{'key': 'param-%s-%s' % (v.id, v.date_to), 'category': 'legal',
                 'title': _('Tham số %s hết áp dụng, kiểm tra văn bản thay thế') % v.param_id.code,
                 'due_date': v.date_to, 'res_model': v.param_id._name, 'res_id': v.param_id.id} for v in values]

    @api.model
    def _cron_refresh(self, today=None):
        today = today or fields.Date.context_today(self)
        found = []
        for company in self.env['res.company'].sudo().search([]):
            horizon = today + timedelta(days=company.lfood_remind_days or 30)
            items = (self._collect_tax(company, today) + self._collect_hr(company, today, horizon)
                     + self._collect_stock(company, today, horizon) + self._collect_receivable(company, today, horizon)
                     + self._collect_loan(company, today, horizon) + self._collect_extra(company, today, horizon))
            for item in items:
                item['company_id'] = company.id
            found += items
        found += self._collect_legal(today, today + timedelta(days=60))
        Reminder = self.sudo()
        existing = {r.key: r for r in Reminder.search([])}
        seen = set()
        for item in found:
            seen.add(item['key'])
            rec = existing.get(item['key'])
            if not rec:
                Reminder.create(item)
            elif rec.state == 'open' or (rec.done_note or '').startswith(AUTO_CLOSED):
                # việc app tự đóng mà điều kiện xuất hiện lại thì mở lại; việc người dùng đánh dấu xử lý thì giữ nguyên
                rec.write({'title': item['title'], 'due_date': item['due_date'], 'state': 'open', 'done_note': False})
        stale = Reminder.search([('state', '=', 'open'), ('key', 'not in', list(seen))])
        stale.write({'state': 'done', 'done_note': AUTO_CLOSED + _(': không còn điều kiện nhắc')})
        return True
