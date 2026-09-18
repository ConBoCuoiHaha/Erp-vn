"""Nghiên cứu phát triển sản phẩm (RD01-RD04).

Tách riêng khỏi kế toán: chỉ nhóm R&D (tạo, sửa) và Giám đốc (xem, duyệt) truy cập; kế toán không có quyền đọc.
Công thức có phiên bản: bản nháp sửa được; chốt thì khóa; muốn sửa bản đã chốt thì tạo phiên bản mới. Giám đốc duyệt
bản đã chốt; bản được duyệt trước đó của cùng dự án chuyển thành hết hiệu lực. Mọi lần chốt, duyệt ghi nhật ký.
Nguyên liệu ghi theo tên và mã nội bộ, không nối với danh mục hàng hóa kế toán (R&D không xem giá vốn).
"""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

SENSORY = [('color', 'Màu sắc'), ('smell', 'Mùi'), ('taste', 'Vị'), ('texture', 'Cấu trúc')]


class LfoodRndProject(models.Model):
    _name = 'lfood.rnd.project'
    _description = 'Dự án sản phẩm mới'
    _order = 'id desc'

    code = fields.Char('Mã dự án', default='/', readonly=True, copy=False)
    name = fields.Char('Tên sản phẩm dự kiến', required=True)
    brand = fields.Char('Nhãn hàng')
    idea = fields.Text('Ý tưởng, đối tượng khách hàng')
    target_price = fields.Float('Giá bán mục tiêu', digits=(16, 0))
    target_date = fields.Date('Hạn ra mắt')
    manager_id = fields.Many2one('res.users', 'Chủ nhiệm', default=lambda s: s.env.user)
    member_ids = fields.Many2many('res.users', string='Thành viên')
    stage = fields.Selection([('idea', 'Ý tưởng'), ('formulation', 'Xây dựng công thức'), ('testing', 'Thử mẫu, đánh giá'),
                              ('transfer', 'Chuyển giao sản xuất'), ('done', 'Hoàn thành'), ('cancel', 'Dừng')],
                             'Giai đoạn', default='idea', required=True)
    formula_ids = fields.One2many('lfood.rnd.formula', 'project_id', 'Công thức')
    approved_formula_id = fields.Many2one('lfood.rnd.formula', 'Công thức đang áp dụng', compute='_compute_approved')
    transfer_note = fields.Text('Hồ sơ chuyển giao')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', '/') == '/':
                vals['code'] = self.env['ir.sequence'].next_by_code('lfood.rnd.project') or '/'
        return super().create(vals_list)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '[%s] %s' % (rec.code, rec.name) if rec.code else rec.name

    @api.depends('formula_ids.state')
    def _compute_approved(self):
        for rec in self:
            rec.approved_formula_id = rec.formula_ids.filtered(lambda f: f.state == 'approved')[:1]

    def write(self, vals):
        if vals.get('stage') in ('transfer', 'done'):
            for rec in self:
                if not rec.approved_formula_id:
                    raise UserError(_('Dự án %s chưa có công thức được Giám đốc duyệt.') % rec.name)
        return super().write(vals)


class LfoodRndFormula(models.Model):
    _name = 'lfood.rnd.formula'
    _description = 'Công thức sản phẩm'
    _order = 'project_id, version desc'

    project_id = fields.Many2one('lfood.rnd.project', 'Dự án', required=True, ondelete='cascade', index=True)
    version = fields.Integer('Phiên bản', required=True, default=1, readonly=True)
    name = fields.Char('Tên công thức', required=True)
    batch_size = fields.Float('Cỡ mẻ (kg)', default=100)
    line_ids = fields.One2many('lfood.rnd.formula.line', 'formula_id', 'Nguyên liệu', copy=True)
    total_pct = fields.Float('Tổng tỷ lệ (%)', compute='_compute_total')
    process = fields.Text('Quy trình chế biến', copy=True)
    change_note = fields.Char('Thay đổi so với bản trước')
    state = fields.Selection([('draft', 'Nháp'), ('locked', 'Đã chốt'), ('approved', 'Giám đốc đã duyệt'),
                              ('obsolete', 'Hết hiệu lực')], 'Trạng thái', default='draft', required=True, readonly=True,
                             copy=False)
    locked_by = fields.Many2one('res.users', 'Người chốt', readonly=True, copy=False)
    approved_by = fields.Many2one('res.users', 'Người duyệt', readonly=True, copy=False)
    approved_on = fields.Datetime('Thời điểm duyệt', readonly=True, copy=False)
    sample_ids = fields.One2many('lfood.rnd.sample', 'formula_id', 'Mẫu thử')

    _version_uniq = models.Constraint('unique(project_id, version)', 'Phiên bản công thức đã tồn tại.')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s v%s' % (rec.name, rec.version)

    @api.depends('line_ids.pct')
    def _compute_total(self):
        for rec in self:
            rec.total_pct = round(sum(rec.line_ids.mapped('pct')), 4)

    def write(self, vals):
        if not self.env.context.get('lfood_rnd_system') and self.filtered(lambda f: f.state != 'draft'):
            raise UserError(_('Công thức đã chốt không sửa được; tạo phiên bản mới.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda f: f.state != 'draft'):
            raise UserError(_('Công thức đã chốt không xóa được.'))
        return super().unlink()

    def _log(self, summary):
        self.env['lfood.audit.log']._record_event('state', model=self._name, res_id=self.id,
                                                  res_name=self.display_name, summary=summary)

    def action_lock(self):
        for rec in self.filtered(lambda f: f.state == 'draft'):
            if not rec.line_ids:
                raise UserError(_('Công thức chưa có nguyên liệu.'))
            if abs(rec.total_pct - 100) > 0.001:
                raise UserError(_('Tổng tỷ lệ nguyên liệu là %s%%, phải bằng 100%%.') % ('%g' % rec.total_pct))
            rec.with_context(lfood_rnd_system=True).write({'state': 'locked', 'locked_by': self.env.uid})
            rec._log(_('Chốt công thức %s') % rec.display_name)
        return True

    def action_approve(self):
        if not self.env.user.has_group('lfood_base.group_director'):
            raise AccessError(_('Chỉ Giám đốc duyệt công thức.'))
        for rec in self.filtered(lambda f: f.state == 'locked'):
            if not rec.sample_ids.filtered(lambda s: s.result == 'pass'):
                raise UserError(_('Công thức %s chưa có mẫu thử đạt.') % rec.display_name)
            old = rec.project_id.formula_ids.filtered(lambda f: f.state == 'approved')
            old.with_context(lfood_rnd_system=True).write({'state': 'obsolete'})
            rec.with_context(lfood_rnd_system=True).write({
                'state': 'approved', 'approved_by': self.env.uid, 'approved_on': fields.Datetime.now()})
            rec._log(_('Giám đốc duyệt công thức %s') % rec.display_name)
        return True

    def action_new_version(self):
        self.ensure_one()
        last = max(self.project_id.formula_ids.mapped('version'))
        new = self.copy({'version': last + 1, 'change_note': False})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': new.id, 'view_mode': 'form'}


class LfoodRndFormulaLine(models.Model):
    _name = 'lfood.rnd.formula.line'
    _description = 'Nguyên liệu trong công thức'
    _order = 'sequence, id'

    formula_id = fields.Many2one('lfood.rnd.formula', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    ingredient = fields.Char('Nguyên liệu', required=True)
    ingredient_code = fields.Char('Mã nội bộ')
    pct = fields.Float('Tỷ lệ (%)', digits=(8, 4), required=True)
    qty = fields.Float('Khối lượng theo mẻ (kg)', digits=(16, 3), compute='_compute_qty')
    note = fields.Char('Ghi chú, tiêu chuẩn')

    @api.depends('pct', 'formula_id.batch_size')
    def _compute_qty(self):
        for rec in self:
            rec.qty = round(rec.formula_id.batch_size * rec.pct / 100, 3)

    @api.constrains('pct')
    def _check_pct(self):
        for rec in self:
            if not 0 < rec.pct <= 100:
                raise ValidationError(_('Tỷ lệ nguyên liệu phải lớn hơn 0 và không quá 100%.'))

    def write(self, vals):
        if not self.env.context.get('lfood_rnd_system') and self.formula_id.filtered(lambda f: f.state != 'draft'):
            raise UserError(_('Công thức đã chốt không sửa được; tạo phiên bản mới.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        formulas = self.env['lfood.rnd.formula'].browse([v.get('formula_id') for v in vals_list if v.get('formula_id')])
        if formulas.filtered(lambda f: f.state != 'draft'):
            raise UserError(_('Công thức đã chốt không thêm nguyên liệu được.'))
        return super().create(vals_list)


class LfoodRndSample(models.Model):
    _name = 'lfood.rnd.sample'
    _description = 'Mẫu thử'
    _order = 'date desc, id desc'

    formula_id = fields.Many2one('lfood.rnd.formula', 'Công thức', required=True, ondelete='cascade', index=True)
    project_id = fields.Many2one(related='formula_id.project_id', store=True)
    name = fields.Char('Mã mẫu', required=True)
    date = fields.Date('Ngày thử', required=True, default=fields.Date.context_today)
    panel = fields.Char('Người đánh giá')
    color = fields.Integer('Màu sắc (1-9)')
    smell = fields.Integer('Mùi (1-9)')
    taste = fields.Integer('Vị (1-9)')
    texture = fields.Integer('Cấu trúc (1-9)')
    sensory_avg = fields.Float('Điểm cảm quan trung bình', compute='_compute_result', store=True)
    min_sensory = fields.Float('Điểm cảm quan tối thiểu', default=6)
    test_ids = fields.One2many('lfood.rnd.sample.test', 'sample_id', 'Chỉ tiêu kiểm nghiệm')
    result = fields.Selection([('pending', 'Chưa đánh giá'), ('pass', 'Đạt'), ('fail', 'Không đạt')], 'Kết luận',
                              compute='_compute_result', store=True)
    note = fields.Text('Nhận xét')

    @api.constrains('color', 'smell', 'taste', 'texture')
    def _check_scores(self):
        for rec in self:
            if any(not 0 <= getattr(rec, k) <= 9 for k, _l in SENSORY):
                raise ValidationError(_('Điểm cảm quan từ 1 đến 9 (0 là chưa chấm).'))

    @api.depends('color', 'smell', 'taste', 'texture', 'min_sensory', 'test_ids.passed')
    def _compute_result(self):
        for rec in self:
            scores = [getattr(rec, k) for k, _l in SENSORY]
            rec.sensory_avg = round(sum(scores) / 4, 2) if all(scores) else 0
            if not all(scores):
                rec.result = 'pending'
            elif rec.sensory_avg < rec.min_sensory or rec.test_ids.filtered(lambda t: not t.passed):
                rec.result = 'fail'
            else:
                rec.result = 'pass'


class LfoodRndSampleTest(models.Model):
    _name = 'lfood.rnd.sample.test'
    _description = 'Chỉ tiêu kiểm nghiệm mẫu thử'

    sample_id = fields.Many2one('lfood.rnd.sample', required=True, ondelete='cascade', index=True)
    indicator = fields.Char('Chỉ tiêu', required=True)
    value = fields.Float('Kết quả', digits=(16, 4))
    unit = fields.Char('Đơn vị')
    limit_min = fields.Float('Tối thiểu', digits=(16, 4))
    limit_max = fields.Float('Tối đa', digits=(16, 4), help='0 là không giới hạn trên')
    passed = fields.Boolean('Đạt', compute='_compute_passed', store=True)

    @api.depends('value', 'limit_min', 'limit_max')
    def _compute_passed(self):
        for rec in self:
            rec.passed = rec.value >= rec.limit_min and (not rec.limit_max or rec.value <= rec.limit_max)
