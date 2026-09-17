from odoo import api, fields, models


class LfoodAssetSchedule(models.Model):
    _name = 'lfood.asset.schedule'
    _description = 'Lịch khấu hao tài sản'
    _order = 'asset_id, date'

    asset_id = fields.Many2one('lfood.asset', 'Tài sản', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='asset_id.company_id', store=True)
    date = fields.Date('Kỳ (cuối tháng)', required=True, index=True)
    amount = fields.Float('Khấu hao kỳ', digits=(16, 0))
    accumulated = fields.Float('Hao mòn lũy kế', digits=(16, 0))
    residual = fields.Float('Giá trị còn lại', digits=(16, 0))
    depreciation_line_id = fields.Many2one('lfood.asset.depreciation.line', 'Dòng chứng từ khấu hao',
                                           readonly=True, copy=False, index=True, ondelete='set null')
    posted = fields.Boolean('Đã ghi chứng từ', compute='_compute_posted', store=True)

    @api.depends('depreciation_line_id.depreciation_id.state')
    def _compute_posted(self):
        for rec in self:
            rec.posted = rec.depreciation_line_id.depreciation_id.state == 'posted'
