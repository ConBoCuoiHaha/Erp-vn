"""Đánh giá hiệu suất (NSU16) và đào tạo (NSU17).

Đánh giá theo kỳ: mỗi người có các chỉ tiêu KPI (trọng số, mục tiêu, thực hiện); điểm từng chỉ tiêu = thực hiện / mục
tiêu, tối đa 120%; tổng điểm theo trọng số xếp loại A (từ 100), B (từ 85), C (từ 70), D. Thưởng = mức thưởng cơ sở của kỳ
x hệ số xếp loại (A 1,2; B 1,0; C 0,6; D 0) - quy chế mặc định, sửa được trên từng kỳ. Duyệt kỳ tạo quyết định khen
thưởng để đưa vào bảng lương.
Đào tạo: khóa học, học viên, kết quả, chứng chỉ có hạn; nhắc chứng chỉ sắp hết hạn.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

RATINGS = [('A', 'A - Xuất sắc'), ('B', 'B - Tốt'), ('C', 'C - Đạt'), ('D', 'D - Chưa đạt')]


def rate(score, a=100, b=85, c=70):
    return 'A' if score >= a else 'B' if score >= b else 'C' if score >= c else 'D'


class LfoodKpiPeriod(models.Model):
    _name = 'lfood.kpi.period'
    _description = 'Kỳ đánh giá hiệu suất'
    _order = 'date_to desc'

    name = fields.Char('Kỳ đánh giá', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    date_from = fields.Date('Từ ngày', required=True)
    date_to = fields.Date('Đến ngày', required=True)
    bonus_base = fields.Float('Mức thưởng cơ sở / người', digits=(16, 0))
    coef_a = fields.Float('Hệ số A', default=1.2)
    coef_b = fields.Float('Hệ số B', default=1.0)
    coef_c = fields.Float('Hệ số C', default=0.6)
    coef_d = fields.Float('Hệ số D', default=0)
    review_ids = fields.One2many('lfood.kpi.review', 'period_id', 'Phiếu đánh giá')
    state = fields.Selection([('draft', 'Đang đánh giá'), ('approved', 'Đã duyệt')], 'Trạng thái', default='draft',
                             required=True, readonly=True)
    approved_by = fields.Many2one('res.users', 'Người duyệt', readonly=True)

    def action_approve(self):
        if not self.env.user.has_group('lfood_base.group_director'):
            raise UserError(_('Chỉ Giám đốc duyệt kết quả đánh giá.'))
        Reward = self.env['lfood.hr.reward'].sudo()
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.review_ids:
                raise UserError(_('Kỳ đánh giá chưa có phiếu nào.'))
            for rv in rec.review_ids:
                if rv.bonus > 0:
                    rv.sudo().reward_id = Reward.create({
                        'employee_id': rv.employee_id.id, 'date': rec.date_to, 'amount': rv.bonus,
                        'reason': _('Thưởng hiệu suất %s, xếp loại %s') % (rec.name, rv.rating),
                        'decision_ref': rec.name})
            rec.write({'state': 'approved', 'approved_by': self.env.uid})
            self.env['lfood.audit.log']._record_event(
                'state', model=rec._name, res_id=rec.id, res_name=rec.name, company_id=rec.company_id.id,
                summary=_('Duyệt đánh giá hiệu suất %s: %s người, thưởng %s') % (
                    rec.name, len(rec.review_ids), '{:,.0f}'.format(sum(rec.review_ids.mapped('bonus'))).replace(',', '.')))
        return True


class LfoodKpiReview(models.Model):
    _name = 'lfood.kpi.review'
    _description = 'Phiếu đánh giá hiệu suất'
    _order = 'period_id, employee_id'

    period_id = fields.Many2one('lfood.kpi.period', 'Kỳ', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='period_id.company_id', store=True)
    employee_id = fields.Many2one('lfood.employee', 'Người lao động', required=True)
    line_ids = fields.One2many('lfood.kpi.line', 'review_id', 'Chỉ tiêu')
    score = fields.Float('Điểm', compute='_compute_score', store=True)
    rating = fields.Selection(RATINGS, 'Xếp loại', compute='_compute_score', store=True)
    bonus = fields.Float('Thưởng đề xuất', digits=(16, 0), compute='_compute_score', store=True)
    comment = fields.Text('Nhận xét của quản lý')
    reward_id = fields.Many2one('lfood.hr.reward', 'Quyết định thưởng', readonly=True)

    _uniq = models.Constraint('unique(period_id, employee_id)', 'Người lao động đã có phiếu trong kỳ.')

    @api.depends('line_ids.weight', 'line_ids.achievement', 'period_id.bonus_base', 'period_id.coef_a',
                 'period_id.coef_b', 'period_id.coef_c', 'period_id.coef_d')
    def _compute_score(self):
        for rec in self:
            weight = sum(rec.line_ids.mapped('weight'))
            rec.score = round(sum(l.weight * l.achievement for l in rec.line_ids) / weight, 1) if weight else 0
            rec.rating = rate(rec.score) if rec.line_ids else False
            p = rec.period_id
            coef = {'A': p.coef_a, 'B': p.coef_b, 'C': p.coef_c, 'D': p.coef_d}.get(rec.rating, 0)
            rec.bonus = round(p.bonus_base * coef)

    def write(self, vals):
        if self.filtered(lambda r: r.period_id.state != 'draft') and set(vals) - {'reward_id'}:
            raise UserError(_('Kỳ đánh giá đã duyệt không sửa được.'))
        return super().write(vals)


class LfoodKpiLine(models.Model):
    _name = 'lfood.kpi.line'
    _description = 'Chỉ tiêu KPI'

    review_id = fields.Many2one('lfood.kpi.review', required=True, ondelete='cascade', index=True)
    name = fields.Char('Chỉ tiêu', required=True)
    weight = fields.Float('Trọng số (%)', required=True)
    target = fields.Float('Mục tiêu', required=True)
    actual = fields.Float('Thực hiện')
    lower_better = fields.Boolean('Càng thấp càng tốt', help='Ví dụ tỷ lệ hàng hỏng, số ngày trễ')
    achievement = fields.Float('Mức đạt (%)', compute='_compute_achievement', store=True)

    @api.depends('target', 'actual', 'lower_better')
    def _compute_achievement(self):
        for rec in self:
            if rec.lower_better:
                ratio = (rec.target / rec.actual) if rec.actual else 1.2
            else:
                ratio = (rec.actual / rec.target) if rec.target else 0
            rec.achievement = round(min(max(ratio, 0), 1.2) * 100, 1)

    @api.constrains('weight', 'target')
    def _check(self):
        for rec in self:
            if rec.weight <= 0 or rec.target <= 0:
                raise ValidationError(_('Trọng số và mục tiêu phải lớn hơn 0.'))


class LfoodTrainingCourse(models.Model):
    _name = 'lfood.training.course'
    _description = 'Khóa đào tạo'
    _order = 'date_start desc'

    name = fields.Char('Khóa học', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    kind = fields.Selection([('internal', 'Nội bộ'), ('external', 'Thuê ngoài')], 'Hình thức', default='internal')
    provider = fields.Char('Đơn vị, giảng viên')
    date_start = fields.Date('Ngày học', required=True)
    hours = fields.Float('Số giờ')
    cost = fields.Float('Chi phí', digits=(16, 0))
    valid_months = fields.Integer('Chứng chỉ có hiệu lực (tháng)', help='0 là không có hạn')
    attendee_ids = fields.One2many('lfood.training.attendee', 'course_id', 'Học viên')
    state = fields.Selection([('planned', 'Kế hoạch'), ('done', 'Đã học')], 'Trạng thái', default='planned', required=True)
    cost_per_head = fields.Float('Chi phí / người', digits=(16, 0), compute='_compute_cost')

    def _compute_cost(self):
        for rec in self:
            n = len(rec.attendee_ids)
            rec.cost_per_head = round(rec.cost / n) if n else 0

    def action_done(self):
        for rec in self.filtered(lambda r: r.state == 'planned'):
            for a in rec.attendee_ids.filtered(lambda x: x.result == 'pass' and not x.expiry and rec.valid_months):
                a.expiry = fields.Date.add(rec.date_start, months=rec.valid_months)
            rec.state = 'done'
        return True


class LfoodTrainingAttendee(models.Model):
    _name = 'lfood.training.attendee'
    _description = 'Học viên'

    course_id = fields.Many2one('lfood.training.course', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='course_id.company_id', store=True)
    employee_id = fields.Many2one('lfood.employee', 'Người lao động', required=True)
    result = fields.Selection([('pass', 'Đạt'), ('fail', 'Không đạt'), ('absent', 'Vắng')], 'Kết quả')
    certificate_no = fields.Char('Số chứng chỉ')
    expiry = fields.Date('Hạn chứng chỉ')
    certificate = fields.Binary('Bản chứng chỉ', attachment=True)
    certificate_name = fields.Char()


class LfoodReminder(models.Model):
    _inherit = 'lfood.reminder'

    def _collect_extra(self, company, today, horizon):
        out = super()._collect_extra(company, today, horizon)
        Att = self.env['lfood.training.attendee'].sudo()
        for a in Att.search([('company_id', '=', company.id), ('expiry', '!=', False), ('expiry', '<=', horizon),
                             ('employee_id.active', '=', True)]):
            newer = Att.search_count([('employee_id', '=', a.employee_id.id), ('course_id.name', '=', a.course_id.name),
                                      ('expiry', '>', horizon)])
            if not newer:
                out.append({'key': 'training-%s-%s' % (a.id, a.expiry), 'category': 'hr',
                            'title': _('Chứng chỉ %s của %s hết hạn') % (a.course_id.name, a.employee_id.name),
                            'due_date': a.expiry, 'res_model': a.course_id._name, 'res_id': a.course_id.id})
        return out
