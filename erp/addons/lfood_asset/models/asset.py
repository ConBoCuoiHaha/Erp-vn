from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.lfood_voucher.models.tools import allocate, vnd
from .depr_tools import build_schedule, month_end, monthly_amount, prorate_until

USAGES = [
    ('production', 'Bộ phận sản xuất, nhà máy'),
    ('sales', 'Bộ phận bán hàng'),
    ('admin', 'Bộ phận quản lý'),
]
USAGE_ACCOUNT = {'production': '6274', 'sales': '6414', 'admin': '6424'}
LOCKED_WHEN_RUNNING = {'original_value', 'salvage_value', 'life_months', 'date_start', 'company_id'}
LIFE_UNITS = [('year', 'Năm'), ('month', 'Tháng')]


def months_of(value, unit):
    """Quy thời gian sử dụng về số tháng."""
    return int(round((value or 0) * (12 if unit == 'year' else 1)))
SYSTEM_FIELDS = {'state', 'code', 'confirmed_by', 'confirmed_on', 'dispose_date', 'dispose_reason', 'dispose_proceeds'}


class LfoodAssetCategory(models.Model):
    _name = 'lfood.asset.category'
    _description = 'Loại tài sản cố định'
    _order = 'code'

    code = fields.Char('Mã loại', required=True)
    name = fields.Char('Tên loại', required=True)
    account_asset = fields.Char('TK nguyên giá', required=True, default='2112')
    account_depreciation = fields.Char('TK hao mòn', required=True, default='2141')
    life_min_months = fields.Integer('Thời gian sử dụng tối thiểu (tháng)')
    life_max_months = fields.Integer('Thời gian sử dụng tối đa (tháng)')
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP mặc định')
    note = fields.Char('Căn cứ khung thời gian')
    active = fields.Boolean(default=True)


class LfoodAsset(models.Model):
    _name = 'lfood.asset'
    _description = 'Tài sản cố định'
    _order = 'code desc, id desc'

    code = fields.Char('Mã tài sản', readonly=True, copy=False, index=True)
    name = fields.Char('Tên tài sản', required=True)
    category_id = fields.Many2one('lfood.asset.category', 'Loại tài sản', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    state = fields.Selection([('draft', 'Nháp'), ('running', 'Đang khấu hao'), ('closed', 'Đã khấu hao hết'),
                              ('disposed', 'Đã thanh lý')], 'Trạng thái', default='draft', readonly=True, copy=False, index=True)

    voucher_id = fields.Many2one('lfood.service.voucher', 'Chứng từ mua', index=True, copy=False)
    partner_id = fields.Many2one('res.partner', 'Nhà cung cấp')
    purchase_date = fields.Date('Ngày mua')
    serial = fields.Char('Số hiệu, biển số')
    location = fields.Char('Nơi đặt')
    usage = fields.Selection(USAGES, 'Bộ phận sử dụng', required=True, default='production')
    account_asset = fields.Char('TK nguyên giá', compute='_compute_accounts', store=True, readonly=False)
    account_depreciation = fields.Char('TK hao mòn', compute='_compute_accounts', store=True, readonly=False)
    account_expense = fields.Char('TK chi phí khấu hao', compute='_compute_accounts', store=True, readonly=False)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP', compute='_compute_accounts', store=True, readonly=False)

    original_value = fields.Float('Nguyên giá', digits=(16, 0), required=True,
                                  help='Giá mua chưa thuế GTGT được khấu trừ, cộng vận chuyển, lắp đặt, chạy thử, lệ phí trước bạ; trừ chiết khấu')
    salvage_value = fields.Float('Giá trị thu hồi dự kiến', digits=(16, 0))
    depreciable_value = fields.Float('Giá trị phải khấu hao', digits=(16, 0), compute='_compute_values', store=True)
    quantity = fields.Integer('Số lượng', default=1, help='Mua nhiều chiếc cùng loại trên một dòng: khi Ghi tăng tự tách mỗi chiếc một thẻ tài sản')
    life_months = fields.Integer('Quy ra tháng', help='App luôn quy thời gian sử dụng về tháng để tính khấu hao')
    life_unit = fields.Selection(LIFE_UNITS, 'Đơn vị', required=True, default='year',
                                 help='Chọn nhập thời gian sử dụng theo năm hay theo tháng')
    life_value = fields.Float('Thời gian sử dụng', digits=(16, 2), compute='_compute_life_value',
                              inverse='_inverse_life_value', store=True, readonly=False,
                              help='Khung thời gian của Thông tư 45 ghi theo năm, mua tài sản đã qua sử dụng thì '
                                   'thường tính theo tháng: chọn đơn vị bên cạnh cho hợp với chứng từ')
    date_start = fields.Date('Ngày bắt đầu khấu hao', required=True, default=fields.Date.context_today)
    monthly_depreciation = fields.Float('Khấu hao tháng', digits=(16, 0), compute='_compute_values', store=True)
    yearly_depreciation = fields.Float('Khấu hao năm', digits=(16, 0), compute='_compute_values', store=True)

    schedule_ids = fields.One2many('lfood.asset.schedule', 'asset_id', 'Lịch khấu hao', readonly=True)
    accumulated_value = fields.Float('Hao mòn lũy kế đã ghi', digits=(16, 0), compute='_compute_progress')
    residual_value = fields.Float('Giá trị còn lại', digits=(16, 0), compute='_compute_progress')
    posted_months = fields.Integer('Số kỳ đã khấu hao', compute='_compute_progress')

    opening_date = fields.Date('Theo dõi trên phần mềm từ',
                               help='Tài sản đã dùng trước khi chạy phần mềm: ghi ngày bắt đầu theo dõi. '
                                    'Các kỳ khấu hao trước ngày này đã nằm trong số dư đầu kỳ TK 214 nên app không lập lại.')
    opening_accumulated = fields.Float('Hao mòn lũy kế đầu kỳ', digits=(16, 0),
                                       help='Số đã khấu hao trước ngày bắt đầu theo dõi, khớp số dư đầu kỳ TK 214.')
    dispose_date = fields.Date('Ngày thanh lý', readonly=True, copy=False)
    dispose_reason = fields.Char('Lý do thanh lý', readonly=True, copy=False)
    dispose_proceeds = fields.Float('Tiền thu thanh lý (chưa thuế)', digits=(16, 0), readonly=True, copy=False)
    confirmed_by = fields.Many2one('res.users', 'Người ghi tăng', readonly=True, copy=False)
    confirmed_on = fields.Datetime('Thời điểm ghi tăng', readonly=True, copy=False)
    below_threshold = fields.Boolean('Dưới ngưỡng TSCĐ', compute='_compute_warnings')
    life_out_of_range = fields.Boolean('Ngoài khung thời gian', compute='_compute_warnings')

    _code_uniq = models.Constraint('unique(company_id, code)', 'Mã tài sản đã tồn tại.')

    @api.depends('category_id', 'usage')
    def _compute_accounts(self):
        for rec in self:
            rec.account_asset = rec.category_id.account_asset or rec.account_asset
            rec.account_depreciation = rec.category_id.account_depreciation or rec.account_depreciation
            rec.account_expense = USAGE_ACCOUNT.get(rec.usage)
            rec.cost_item_id = rec.category_id.cost_item_id or rec.cost_item_id

    @api.depends('life_months', 'life_unit')
    def _compute_life_value(self):
        for rec in self:
            rec.life_value = (rec.life_months or 0) / 12 if rec.life_unit == 'year' else (rec.life_months or 0)

    def _inverse_life_value(self):
        for rec in self:
            months = months_of(rec.life_value, rec.life_unit)
            if months != rec.life_months:
                rec.life_months = months

    @api.onchange('life_value', 'life_unit')
    def _onchange_life_value(self):
        # đổi ngay số tháng hiện trên biểu mẫu, không đợi lưu
        for rec in self:
            rec.life_months = months_of(rec.life_value, rec.life_unit)

    @api.depends('original_value', 'salvage_value', 'life_months')
    def _compute_values(self):
        for rec in self:
            rec.depreciable_value = max(0, (rec.original_value or 0) - (rec.salvage_value or 0))
            rec.monthly_depreciation = monthly_amount(rec.depreciable_value, rec.life_months)
            rec.yearly_depreciation = round(rec.depreciable_value * 12 / rec.life_months) if rec.life_months > 0 else 0

    @api.depends('schedule_ids.posted', 'schedule_ids.amount', 'original_value')
    def _compute_progress(self):
        for rec in self:
            posted = rec.schedule_ids.filtered('posted')
            rec.accumulated_value = (rec.opening_accumulated or 0) + sum(posted.mapped('amount'))
            rec.residual_value = (rec.original_value or 0) - rec.accumulated_value
            rec.posted_months = len(posted)

    @api.depends('original_value', 'purchase_date', 'date_start', 'life_months', 'category_id')
    def _compute_warnings(self):
        Param = self.env['lfood.legal.param']
        for rec in self:
            limit = Param.get_value('NGUONG_TSCD', rec.purchase_date or rec.date_start, default=30000000)
            rec.below_threshold = (rec.original_value or 0) < limit
            cat = rec.category_id
            rec.life_out_of_range = bool(rec.life_months) and (
                (cat.life_min_months and rec.life_months < cat.life_min_months)
                or (cat.life_max_months and rec.life_months > cat.life_max_months))

    @api.constrains('original_value', 'salvage_value', 'life_months')
    def _check_values(self):
        for rec in self:
            if rec.original_value <= 0 or rec.life_months <= 0:
                raise ValidationError(_('Nguyên giá và thời gian sử dụng phải lớn hơn 0.'))
            if rec.salvage_value < 0 or rec.salvage_value >= rec.original_value:
                raise ValidationError(_('Giá trị thu hồi dự kiến phải từ 0 và nhỏ hơn nguyên giá.'))

    # ------------------------------------------------------------ bảo vệ dữ liệu
    @api.model_create_multi
    def create(self, vals_list):
        # quy thời gian sử dụng về tháng ngay lúc tạo: ràng buộc chạy trước hàm nghịch đảo của life_value
        for vals in vals_list:
            if not vals.get('life_months') and vals.get('life_value'):
                unit = vals.get('life_unit') or self.default_get(['life_unit']).get('life_unit') or 'year'
                vals['life_months'] = months_of(vals['life_value'], unit)
        return super().create(vals_list)

    def write(self, vals):
        if SYSTEM_FIELDS & set(vals) and not self.env.context.get('lfood_asset_system'):
            raise UserError(_('Trạng thái tài sản chỉ đổi bằng các nút Ghi tăng, Thanh lý.'))
        if LOCKED_WHEN_RUNNING & set(vals) and not self.env.context.get('lfood_asset_system'):
            if self.filtered(lambda a: a.state != 'draft'):
                raise UserError(_('Tài sản đã ghi tăng không sửa được nguyên giá, thời gian sử dụng, ngày bắt đầu. '
                                  'Muốn sửa phải hủy ghi tăng khi chưa có kỳ khấu hao nào.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda a: a.state != 'draft'):
            raise UserError(_('Chỉ xóa được tài sản Nháp.'))
        return super().unlink()

    def _log(self, summary):
        for rec in self:
            self.env['lfood.audit.log']._record_event('state', model=rec._name, res_id=rec.id,
                                                      res_name='%s %s' % (rec.code, rec.name),
                                                      company_id=rec.company_id.id, summary=summary)

    @api.constrains('opening_date', 'opening_accumulated', 'original_value')
    def _check_opening(self):
        for rec in self:
            if rec.opening_date and rec.opening_accumulated > rec.original_value:
                raise ValidationError(_('Hao mòn lũy kế đầu kỳ %s lớn hơn nguyên giá %s.')
                                      % (vnd(rec.opening_accumulated), vnd(rec.original_value)))
            if rec.opening_accumulated and not rec.opening_date:
                raise ValidationError(_('Có hao mòn lũy kế đầu kỳ thì phải ghi ngày bắt đầu theo dõi trên phần mềm.'))

    def _require_accountant(self):
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán được thao tác với tài sản cố định.'))

    # ------------------------------------------------------------ nghiệp vụ
    def _generate_schedule(self):
        for rec in self:
            rec.schedule_ids.sudo().filtered(lambda s: not s.posted).unlink()
            acc, lines = 0, []
            for period, amount in build_schedule(rec.depreciable_value, rec.life_months, rec.date_start):
                acc += amount
                if rec.opening_date and period < rec.opening_date:
                    continue  # kỳ này đã khấu hao trước khi dùng phần mềm, nằm trong số dư đầu kỳ
                lines.append({'asset_id': rec.id, 'date': period, 'amount': amount,
                              'accumulated': acc, 'residual': rec.original_value - acc})
            self.env['lfood.asset.schedule'].sudo().create(lines)

    def _split_quantity(self):
        """Mỗi tài sản một thẻ: dòng số lượng N tách thành N tài sản, nguyên giá chia khớp tới đồng."""
        result = self.browse()
        for rec in self:
            n = rec.quantity or 1
            if rec.state != 'draft' or n <= 1:
                result |= rec
                continue
            shares = allocate(rec.original_value, [1] * n)
            base = rec.name
            rec.write({'quantity': 1, 'original_value': shares[0], 'name': '%s (1/%s)' % (base, n)})
            result |= rec
            for i, share in enumerate(shares[1:], start=2):
                result |= rec.copy({'quantity': 1, 'original_value': share, 'name': '%s (%s/%s)' % (base, i, n),
                                    'voucher_id': rec.voucher_id.id})
        return result

    def action_confirm(self):
        """Ghi tăng: kiểm tra điều kiện TSCĐ, cấp mã, lập lịch khấu hao."""
        self._require_accountant()
        for rec in self._split_quantity().filtered(lambda a: a.state == 'draft'):
            if rec.below_threshold:
                raise UserError(_('Nguyên giá %s thấp hơn ngưỡng tài sản cố định (tham số NGUONG_TSCD). '
                                  'Khoản này là công cụ dụng cụ, phân bổ qua TK 242.') % vnd(rec.original_value))
            if rec.life_out_of_range:
                cat = rec.category_id
                raise UserError(_('Thời gian sử dụng %s tháng nằm ngoài khung %s–%s tháng của loại %s.')
                                % (rec.life_months, cat.life_min_months, cat.life_max_months, cat.name))
            if not rec.code:
                rec.with_context(lfood_asset_system=True).code = self.env['ir.sequence'].with_company(rec.company_id).next_by_code('lfood.asset')
            rec.with_context(lfood_asset_system=True).write({
                'state': 'running', 'confirmed_by': self.env.user.id, 'confirmed_on': fields.Datetime.now()})
            rec._generate_schedule()
            rec._log(_('Ghi tăng TSCĐ, nguyên giá %s, %s tháng, khấu hao tháng %s, Nợ %s / Có 331')
                     % (vnd(rec.original_value), rec.life_months, vnd(rec.monthly_depreciation), rec.account_asset))
        return True

    def action_reset_draft(self):
        self._require_accountant()
        for rec in self:
            if rec.state != 'running' or rec.schedule_ids.filtered('depreciation_line_id'):
                raise UserError(_('Tài sản %s đã có kỳ khấu hao trên chứng từ, không hủy ghi tăng được.') % rec.code)
            rec.schedule_ids.sudo().unlink()
            rec.with_context(lfood_asset_system=True).write({'state': 'draft'})
            rec._log(_('Hủy ghi tăng TSCĐ'))
        return True

    def _dispose(self, dispose_date, reason, proceeds):
        """Thanh lý: thôi khấu hao từ ngày giảm, tháng giảm tính theo ngày."""
        self.ensure_one()
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được thanh lý tài sản.'))
        if self.state not in ('running', 'closed'):
            raise UserError(_('Chỉ thanh lý được tài sản đã ghi tăng.'))
        if dispose_date < self.date_start:
            raise UserError(_('Ngày thanh lý trước ngày bắt đầu khấu hao.'))
        period = month_end(dispose_date)
        if self.schedule_ids.filtered(lambda s: s.depreciation_line_id and s.date >= period):
            raise UserError(_('Đã có chứng từ khấu hao từ kỳ %s trở đi. Hủy các chứng từ đó trước khi thanh lý.')
                            % period.strftime('%m/%Y'))
        future = self.schedule_ids.filtered(lambda s: s.date >= period)
        done = sum((self.schedule_ids - future).mapped('amount'))
        future.sudo().unlink()
        if period == month_end(self.date_start):
            days = period.day
            last = round(self.monthly_depreciation * (dispose_date.day - self.date_start.day) / days)
        else:
            last = prorate_until(self.monthly_depreciation, dispose_date)
        last = min(last, self.depreciable_value - done)
        if last > 0:
            self.env['lfood.asset.schedule'].sudo().create({
                'asset_id': self.id, 'date': period, 'amount': last, 'accumulated': done + last,
                'residual': self.original_value - done - last})
        self.with_context(lfood_asset_system=True).write({
            'state': 'disposed', 'dispose_date': dispose_date, 'dispose_reason': reason, 'dispose_proceeds': proceeds})
        residual = self.original_value - done - max(last, 0)
        self._log(_('Thanh lý ngày %s: ghi giảm Nợ 214 %s, Nợ 811 %s / Có %s %s; thu %s ghi Có 711')
                  % (dispose_date.strftime('%d/%m/%Y'), vnd(done + max(last, 0)), vnd(residual), self.account_asset,
                     vnd(self.original_value), vnd(proceeds)))
        return True

    def _transfer(self, usage, cost_item, reason):
        """Điều chuyển bộ phận sử dụng: các kỳ khấu hao chưa ghi chứng từ hạch toán vào TK chi phí của bộ phận mới."""
        self.ensure_one()
        if not self.env.user.has_group('lfood_base.group_chief_accountant'):
            raise UserError(_('Chỉ Kế toán trưởng được điều chuyển tài sản.'))
        if self.state != 'running':
            raise UserError(_('Chỉ điều chuyển được tài sản đang khấu hao.'))
        labels = dict(self._fields['usage'].selection)
        old = labels[self.usage]
        self.with_context(lfood_asset_system=True).write({
            'usage': usage, 'account_expense': USAGE_ACCOUNT[usage],
            'cost_item_id': cost_item.id if cost_item else self.cost_item_id.id})
        self._log(_('Điều chuyển từ %s sang %s, TK chi phí khấu hao %s. Lý do: %s')
                  % (old, labels[usage], self.account_expense, reason))
        return True

    def action_open_transfer(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Điều chuyển tài sản'), 'res_model': 'lfood.asset.transfer',
                'view_mode': 'form', 'target': 'new', 'context': {'default_asset_id': self.id}}

    def action_open_dispose(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Thanh lý tài sản'), 'res_model': 'lfood.asset.dispose',
                'view_mode': 'form', 'target': 'new', 'context': {'default_asset_id': self.id}}

    def action_view_audit(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Nhật ký tài sản'), 'res_model': 'lfood.audit.log',
                'view_mode': 'list,form', 'domain': [('model', '=', self._name), ('res_id', '=', self.id)]}


class LfoodAssetDispose(models.TransientModel):
    _name = 'lfood.asset.dispose'
    _description = 'Thanh lý tài sản'

    asset_id = fields.Many2one('lfood.asset', required=True)
    dispose_date = fields.Date('Ngày thanh lý', required=True, default=fields.Date.context_today)
    reason = fields.Char('Lý do', required=True)
    proceeds = fields.Float('Tiền thu (chưa thuế)', digits=(16, 0))

    def action_apply(self):
        self.asset_id._dispose(self.dispose_date, self.reason, self.proceeds)
        return {'type': 'ir.actions.act_window_close'}


class LfoodAssetTransfer(models.TransientModel):
    _name = 'lfood.asset.transfer'
    _description = 'Điều chuyển tài sản'

    asset_id = fields.Many2one('lfood.asset', required=True)
    usage = fields.Selection(USAGES, 'Bộ phận sử dụng mới', required=True)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục CP mới')
    reason = fields.Char('Lý do', required=True)

    def action_apply(self):
        self.asset_id._transfer(self.usage, self.cost_item_id, self.reason)
        return {'type': 'ir.actions.act_window_close'}
