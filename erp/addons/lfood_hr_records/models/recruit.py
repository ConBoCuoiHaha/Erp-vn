"""Tuyển dụng (NSU01): yêu cầu tuyển, hồ sơ ứng viên, phỏng vấn, nhận việc.

Yêu cầu tuyển do bộ phận lập, Giám đốc duyệt. Ứng viên đi qua các bước sàng lọc, phỏng vấn, mời nhận việc; nhận việc
thì app tạo hồ sơ nhân viên. Hồ sơ ứng viên là dữ liệu cá nhân (Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15): phải ghi nhận
sự đồng ý trước khi xử lý tiếp; ứng viên không trúng tuyển được xóa sau số tháng lưu theo quy chế công ty (tham số
TUYEN_DUNG_LUU_HO_SO_THANG), trừ khi ứng viên đồng ý lưu lâu hơn.
"""
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LfoodHrJobRequest(models.Model):
    _name = 'lfood.hr.job.request'
    _description = 'Yêu cầu tuyển dụng'
    _order = 'id desc'

    name = fields.Char('Vị trí cần tuyển', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    department_id = fields.Many2one('lfood.department', 'Phòng ban')
    job_id = fields.Many2one('lfood.job.position', 'Chức danh')
    quantity = fields.Integer('Số lượng', required=True, default=1)
    reason = fields.Char('Lý do tuyển', required=True)
    salary_range = fields.Char('Mức lương dự kiến')
    date_needed = fields.Date('Cần người trước ngày')
    applicant_ids = fields.One2many('lfood.hr.applicant', 'request_id', 'Ứng viên')
    hired = fields.Integer('Đã tuyển', compute='_compute_hired')
    approved_by = fields.Many2one('res.users', 'Người duyệt', readonly=True, copy=False)
    state = fields.Selection([('draft', 'Nháp'), ('approved', 'Đang tuyển'), ('closed', 'Đã đóng')], 'Trạng thái',
                             default='draft', required=True, readonly=True, copy=False)

    def _compute_hired(self):
        for rec in self:
            rec.hired = len(rec.applicant_ids.filtered(lambda a: a.stage == 'hired'))

    def action_approve(self):
        if not self.env.user.has_group('lfood_base.group_director'):
            raise UserError(_('Chỉ Giám đốc duyệt yêu cầu tuyển dụng.'))
        self.filtered(lambda r: r.state == 'draft').write({'state': 'approved', 'approved_by': self.env.uid})
        return True

    def action_close(self):
        self.filtered(lambda r: r.state == 'approved').write({'state': 'closed'})
        return True


class LfoodHrApplicant(models.Model):
    _name = 'lfood.hr.applicant'
    _description = 'Ứng viên'
    _order = 'id desc'

    name = fields.Char('Họ tên', required=True)
    request_id = fields.Many2one('lfood.hr.job.request', 'Yêu cầu tuyển', required=True, index=True, ondelete='restrict')
    company_id = fields.Many2one(related='request_id.company_id', store=True, index=True)
    phone = fields.Char('Điện thoại')
    email = fields.Char('Email')
    source = fields.Char('Nguồn ứng tuyển')
    cv = fields.Binary('Hồ sơ, CV', attachment=True)
    cv_name = fields.Char()
    consent = fields.Boolean('Ứng viên đồng ý xử lý dữ liệu cá nhân cho tuyển dụng')
    consent_date = fields.Date('Ngày đồng ý')
    keep_longer = fields.Boolean('Đồng ý lưu hồ sơ cho đợt tuyển sau')
    stage = fields.Selection([('new', 'Mới nhận'), ('screening', 'Sàng lọc'), ('interview', 'Phỏng vấn'),
                              ('offer', 'Mời nhận việc'), ('hired', 'Đã nhận việc'), ('rejected', 'Không đạt')],
                             'Bước', default='new', required=True, index=True)
    interview_date = fields.Datetime('Lịch phỏng vấn')
    interviewer = fields.Char('Người phỏng vấn')
    score = fields.Integer('Điểm đánh giá (0-100)')
    evaluation = fields.Text('Nhận xét')
    closed_on = fields.Date('Ngày kết thúc hồ sơ', readonly=True)
    employee_code = fields.Char('Mã nhân viên khi nhận việc')
    date_start = fields.Date('Ngày vào làm')
    employee_id = fields.Many2one('lfood.employee', 'Hồ sơ nhân viên', readonly=True)

    @api.onchange('consent')
    def _onchange_consent(self):
        if self.consent and not self.consent_date:
            self.consent_date = fields.Date.context_today(self)

    def write(self, vals):
        if vals.get('stage') and vals['stage'] not in ('new', 'rejected'):
            for rec in self:
                if not (vals.get('consent', rec.consent)):
                    raise UserError(_('%s chưa đồng ý xử lý dữ liệu cá nhân; chưa chuyển bước được.') % rec.name)
        if vals.get('stage') == 'hired' and not self.env.context.get('lfood_hire'):
            raise UserError(_('Dùng nút Nhận việc để tạo hồ sơ nhân viên.'))
        if vals.get('stage') == 'rejected':
            vals['closed_on'] = fields.Date.context_today(self)
        return super().write(vals)

    def action_hire(self):
        for rec in self.filtered(lambda r: r.stage == 'offer'):
            req = rec.request_id
            if req.state != 'approved':
                raise UserError(_('Yêu cầu tuyển %s chưa duyệt hoặc đã đóng.') % req.name)
            if req.hired >= req.quantity:
                raise UserError(_('Yêu cầu tuyển %s đã đủ %s người.') % (req.name, req.quantity))
            if not (rec.employee_code and rec.date_start):
                raise UserError(_('Nhập mã nhân viên và ngày vào làm.'))
            vals = {'code': rec.employee_code, 'name': rec.name, 'company_id': req.company_id.id,
                    'date_start': rec.date_start, 'job': req.job_id.name or req.name}
            if req.department_id:
                vals['department_id'] = req.department_id.id
            if req.job_id:
                vals['job_id'] = req.job_id.id
            emp = self.env['lfood.employee'].create(vals)
            rec.with_context(lfood_hire=True).write({'stage': 'hired', 'employee_id': emp.id,
                                                     'closed_on': fields.Date.context_today(self)})
            req.invalidate_recordset(['hired'])
            if req.hired >= req.quantity:
                req.state = 'closed'
        return True

    @api.model
    def _cron_purge(self, today=None):
        """Xóa hồ sơ ứng viên không đạt đã quá thời hạn lưu (không áp dụng người đồng ý lưu lâu hơn)."""
        today = today or fields.Date.context_today(self)
        months = self.env['lfood.legal.param'].get_value('TUYEN_DUNG_LUU_HO_SO_THANG', today, default=12)
        old = self.sudo().search([('stage', '=', 'rejected'), ('keep_longer', '=', False),
                                  ('closed_on', '<', today - timedelta(days=int(months * 30.5)))])
        count = len(old)
        if old:
            old.unlink()
            self.env['lfood.audit.log']._record_event(
                'unlink', model=self._name, summary=_('Xóa %s hồ sơ ứng viên không trúng tuyển quá %s tháng') % (count, '%g' % months))
        return count
