"""Hồ sơ người phụ thuộc (NSU02).

Giảm trừ gia cảnh cho người phụ thuộc được tính từ tháng phát sinh nghĩa vụ nuôi dưỡng đến tháng kết thúc, mỗi người
phụ thuộc chỉ được tính giảm trừ cho một người nộp thuế và phải đăng ký (mã số thuế người phụ thuộc). Mức giảm trừ lấy
từ tham số TNCN_GIAM_TRU_NPT (Nghị quyết 110/2025/UBTVQH15 cho kỳ tính thuế 2026).
Khi nhân viên đã có dòng đăng ký, bảng lương đếm số người theo sổ này thay cho ô nhập tay.
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

RELATIONS = [('child', 'Con'), ('spouse', 'Vợ, chồng'), ('parent', 'Cha, mẹ'), ('other', 'Người khác theo quy định')]


class LfoodDependent(models.Model):
    _name = 'lfood.dependent'
    _description = 'Người phụ thuộc'
    _order = 'employee_id, date_from'

    employee_id = fields.Many2one('lfood.employee', 'Người nộp thuế', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(related='employee_id.company_id', store=True)
    name = fields.Char('Họ tên người phụ thuộc', required=True)
    relation = fields.Selection(RELATIONS, 'Quan hệ', required=True, default='child')
    birth_date = fields.Date('Ngày sinh')
    id_number = fields.Char('Mã số thuế, số định danh', required=True, index=True)
    date_from = fields.Date('Giảm trừ từ tháng', required=True)
    date_to = fields.Date('Đến tháng', help='Để trống nếu chưa kết thúc')
    registered = fields.Boolean('Đã đăng ký với cơ quan thuế')
    document = fields.Binary('Hồ sơ chứng minh', attachment=True)
    document_name = fields.Char()

    @api.constrains('date_from', 'date_to', 'id_number')
    def _check_dependent(self):
        for rec in self:
            if rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_('Tháng kết thúc phải sau tháng bắt đầu.'))
            others = self.sudo().search([('id_number', '=', rec.id_number), ('id', '!=', rec.id)])
            for o in others:
                overlap = (not o.date_to or o.date_to >= rec.date_from) and (not rec.date_to or rec.date_to >= o.date_from)
                if overlap and o.employee_id != rec.employee_id:
                    raise ValidationError(_('%s đang được tính giảm trừ cho %s; mỗi người phụ thuộc chỉ tính cho một '
                                            'người nộp thuế trong cùng thời gian.') % (rec.name, o.employee_id.name))


class LfoodEmployee(models.Model):
    _inherit = 'lfood.employee'

    dependent_ids = fields.One2many('lfood.dependent', 'employee_id', 'Người phụ thuộc')

    def _dependents_in(self, date_from, date_to):
        self.ensure_one()
        if not self.dependent_ids:
            return super()._dependents_in(date_from, date_to)
        # tính cả tháng: người phụ thuộc có hiệu lực vào bất kỳ ngày nào trong kỳ
        return len(self.dependent_ids.filtered(
            lambda d: d.registered and d.date_from <= date_to and (not d.date_to or d.date_to >= date_from)))
