"""Ca làm việc và lịch phân ca (NSU05).

Bộ luật Lao động 2019: giờ làm việc bình thường không quá 08 giờ/ngày và 48 giờ/tuần (Điều 105); làm việc ban đêm từ
22 giờ đến 06 giờ sáng hôm sau (Điều 106); người làm việc theo ca được nghỉ ít nhất 12 giờ trước khi chuyển sang ca
khác (Điều 109 khoản 2); mỗi tuần được nghỉ ít nhất 24 giờ liên tục (Điều 111).
Lịch phân ca kiểm tra các giới hạn trên rồi tạo dòng chấm công (giờ bình thường, giờ làm đêm) để tính lương.
"""
from datetime import datetime, time, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

NIGHT = (22.0, 30.0)  # 22 giờ đến 6 giờ sáng hôm sau, tính theo giờ liên tục từ 0 giờ ngày bắt đầu ca


def shift_hours(start, end, break_hours):
    """(giờ làm việc, giờ làm đêm) của một ca; ca qua đêm khi end <= start.

    Giờ nghỉ giữa ca trừ theo tỷ lệ phần ngày và phần đêm của ca.
    ponytail: nghỉ giữa ca chia đều theo tỷ lệ; ca có giờ nghỉ cố định ban ngày thì chỉnh giờ làm đêm tay trên chấm công.
    """
    stop = end if end > start else end + 24
    duration = stop - start
    night = sum(max(0.0, min(stop, b) - max(start, a)) for a, b in ((NIGHT[0] - 24, NIGHT[1] - 24), NIGHT))
    worked = max(0.0, duration - break_hours)
    return round(worked, 2), round(night * worked / duration, 2) if duration else 0.0


class LfoodHrShift(models.Model):
    _name = 'lfood.hr.shift'
    _description = 'Ca làm việc'
    _order = 'hour_start'

    name = fields.Char('Tên ca', required=True)
    company_id = fields.Many2one('res.company', 'Công ty', required=True, default=lambda s: s.env.company, index=True)
    hour_start = fields.Float('Giờ bắt đầu', required=True, help='Ví dụ 22.0 là 22 giờ, 6.5 là 6 giờ 30')
    hour_end = fields.Float('Giờ kết thúc', required=True, help='Nhỏ hơn giờ bắt đầu nghĩa là kết thúc sáng hôm sau')
    break_hours = fields.Float('Nghỉ giữa ca không tính giờ làm (giờ)', default=0,
                               help='Nghỉ giữa giờ tính vào thời giờ làm việc thì để 0')
    work_hours = fields.Float('Giờ làm việc', compute='_compute_hours', store=True)
    night_hours = fields.Float('Giờ làm đêm', compute='_compute_hours', store=True)
    active = fields.Boolean(default=True)

    @api.depends('hour_start', 'hour_end', 'break_hours')
    def _compute_hours(self):
        for rec in self:
            rec.work_hours, rec.night_hours = shift_hours(rec.hour_start, rec.hour_end, rec.break_hours)

    @api.constrains('hour_start', 'hour_end', 'break_hours')
    def _check_hours(self):
        P = self.env['lfood.legal.param']
        for rec in self:
            if not (0 <= rec.hour_start < 24 and 0 <= rec.hour_end < 24) or rec.hour_start == rec.hour_end:
                raise ValidationError(_('Giờ bắt đầu, kết thúc phải trong 0 đến 24 và khác nhau.'))
            day = P.get_value('GIO_LAM_VIEC_NGAY', fields.Date.context_today(rec), default=8)
            if rec.work_hours > day + 1e-6:
                raise ValidationError(_('Ca %s có %s giờ làm việc, quá %s giờ/ngày (Bộ luật Lao động 2019, Điều 105).')
                                      % (rec.name, '%g' % rec.work_hours, '%g' % day))

    def _span(self, day):
        """(bắt đầu, kết thúc) dạng datetime của ca vào ngày day."""
        self.ensure_one()
        begin = datetime.combine(day, time()) + timedelta(hours=self.hour_start)
        stop = self.hour_end if self.hour_end > self.hour_start else self.hour_end + 24
        return begin, datetime.combine(day, time()) + timedelta(hours=stop)


class LfoodHrRoster(models.Model):
    _name = 'lfood.hr.roster'
    _description = 'Lịch phân ca'
    _order = 'date, employee_id'

    employee_id = fields.Many2one('lfood.employee', 'Người lao động', required=True, index=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    date = fields.Date('Ngày', required=True, index=True)
    shift_id = fields.Many2one('lfood.hr.shift', 'Ca', required=True)
    attendance_id = fields.Many2one('lfood.hr.attendance', 'Dòng chấm công', readonly=True, copy=False, ondelete='set null')

    _uniq = models.Constraint('unique(employee_id, date)', 'Người lao động đã có ca ngày này.')

    @api.constrains('employee_id', 'date', 'shift_id')
    def _check_rules(self):
        P = self.env['lfood.legal.param']
        for rec in self:
            rest = P.get_value('NGHI_CHUYEN_CA_GIO', rec.date, default=12)
            week_cap = P.get_value('GIO_LAM_VIEC_TUAN', rec.date, default=48)
            around = self.search([('employee_id', '=', rec.employee_id.id), ('id', '!=', rec.id),
                                  ('date', '>=', rec.date - timedelta(days=7)), ('date', '<=', rec.date + timedelta(days=7))])
            begin, stop = rec.shift_id._span(rec.date)
            for o in around.filtered(lambda o: abs((o.date - rec.date).days) == 1 and o.shift_id != rec.shift_id):
                ob, os_ = o.shift_id._span(o.date)
                gap = (begin - os_) if o.date < rec.date else (ob - stop)
                if gap < timedelta(hours=rest):
                    raise ValidationError(_('%s chuyển ca ngày %s chỉ nghỉ %s giờ, cần ít nhất %s giờ (Bộ luật Lao động 2019, '
                                            'Điều 109).') % (rec.employee_id.name, rec.date.strftime('%d/%m/%Y'),
                                                              '%g' % (gap.total_seconds() / 3600), '%g' % rest))
            monday = rec.date - timedelta(days=rec.date.weekday())
            week = (around | rec).filtered(lambda o: monday <= o.date <= monday + timedelta(days=6))
            hours = sum(week.mapped('shift_id.work_hours'))
            if hours > week_cap + 1e-6:
                raise ValidationError(_('%s tuần từ %s có %s giờ làm việc theo ca, quá %s giờ (Bộ luật Lao động 2019, Điều 105).')
                                      % (rec.employee_id.name, monday.strftime('%d/%m/%Y'), '%g' % hours, '%g' % week_cap))
            if len(week) >= 7:
                raise ValidationError(_('%s tuần từ %s không có ngày nghỉ, mỗi tuần phải nghỉ ít nhất 24 giờ liên tục '
                                        '(Bộ luật Lao động 2019, Điều 111).') % (rec.employee_id.name, monday.strftime('%d/%m/%Y')))

    def action_to_attendance(self):
        """Tạo dòng chấm công theo ca; ngày đã có chấm công thì giữ nguyên số đã chấm."""
        if not self.env.user.has_group('lfood_base.group_accountant'):
            raise UserError(_('Chỉ kế toán, nhân sự được tạo chấm công.'))
        Att = self.env['lfood.hr.attendance']
        made = 0
        for rec in self.filtered(lambda r: not r.attendance_id):
            att = Att.search([('employee_id', '=', rec.employee_id.id), ('date', '=', rec.date)], limit=1)
            if not att:
                att = Att.create({'employee_id': rec.employee_id.id, 'date': rec.date,
                                  'hours_normal': rec.shift_id.work_hours, 'night_hours': rec.shift_id.night_hours,
                                  'note': rec.shift_id.name})
                made += 1
            rec.attendance_id = att
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'message': _('Đã tạo %s dòng chấm công.') % made, 'type': 'success'}}

