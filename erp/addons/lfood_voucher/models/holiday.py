"""Lịch nghỉ lễ, Tết và ngày làm việc (CH06).

Bộ luật Lao động 2019, Điều 111, 112: nghỉ hằng tuần do doanh nghiệp quy định (mặc định thứ Bảy, Chủ nhật); ngày lễ,
Tết hưởng nguyên lương gồm Tết Dương lịch 1 ngày, Tết Âm lịch 5 ngày, Chiến thắng 30/4, Quốc tế Lao động 1/5,
Quốc khánh 2 ngày, Giỗ Tổ Hùng Vương 10/3 âm lịch; ngày lễ trùng ngày nghỉ hằng tuần thì nghỉ bù vào ngày làm việc
kế tiếp. Lịch cụ thể từng năm (ngày Tết âm lịch, ngày nghỉ bù, hoán đổi) theo thông báo hằng năm nên kế toán nhập theo năm.
"""
from datetime import timedelta

from odoo import api, fields, models


def add_working_days(start, days, holidays=()):
    """Ngày làm việc thứ `days` sau `start` (bỏ thứ Bảy, Chủ nhật và ngày nghỉ trong `holidays`)."""
    d = start
    while days > 0:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in holidays:
            days -= 1
    return d


def working_days_between(start, end, holidays=()):
    """Số ngày làm việc nằm giữa start và end, không tính hai đầu."""
    count, d = 0, start + timedelta(days=1)
    while d < end:
        count += d.weekday() < 5 and d not in holidays
        d += timedelta(days=1)
    return count


class LfoodHoliday(models.Model):
    _name = 'lfood.holiday'
    _description = 'Ngày nghỉ lễ, Tết'
    _order = 'date'

    date = fields.Date('Ngày', required=True, index=True)
    name = fields.Char('Tên ngày nghỉ', required=True)
    kind = fields.Selection([('holiday', 'Ngày lễ, Tết'), ('compensate', 'Nghỉ bù'), ('swap', 'Nghỉ hoán đổi')],
                            'Loại', required=True, default='holiday')
    legal_ref = fields.Char('Căn cứ')
    year = fields.Integer('Năm', compute='_compute_year', store=True)

    _date_uniq = models.Constraint('unique(date)', 'Ngày nghỉ đã khai báo.')

    @api.depends('date')
    def _compute_year(self):
        for rec in self:
            rec.year = rec.date.year if rec.date else 0

    @api.model
    def _dates(self, start, end):
        """Tập ngày nghỉ trong khoảng (mở rộng thêm 60 ngày để các hàm cộng ngày không thiếu)."""
        return set(self.sudo().search([('date', '>=', start), ('date', '<=', end + timedelta(days=60))]).mapped('date'))

    @api.model
    def add_working_days(self, start, days):
        return add_working_days(start, days, self._dates(start, start + timedelta(days=days * 3)))

    @api.model
    def working_days_between(self, start, end):
        return working_days_between(start, end, self._dates(start, end))

