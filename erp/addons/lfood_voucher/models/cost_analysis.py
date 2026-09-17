from odoo import fields, models, tools


class LfoodCostAnalysis(models.Model):
    """Báo cáo phân tích chi phí: chỉ đọc phiên bản báo cáo của từng chứng từ,
    nên Sửa chứng từ không làm thay đổi số liệu báo cáo."""
    _name = 'lfood.cost.analysis'
    _description = 'Phân tích chi phí nhiều kỳ'
    _auto = False
    _order = 'date desc'

    voucher_id = fields.Many2one('lfood.service.voucher', 'Chứng từ', readonly=True)
    company_id = fields.Many2one('res.company', 'Công ty', readonly=True)
    date = fields.Date('Ngày hạch toán', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Nhà cung cấp', readonly=True)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục chi tiết', readonly=True)
    lvl1_id = fields.Many2one('lfood.cost.item', 'Cấp 1', readonly=True)
    lvl2_id = fields.Many2one('lfood.cost.item', 'Cấp 2', readonly=True)
    lvl3_id = fields.Many2one('lfood.cost.item', 'Cấp 3', readonly=True)
    lvl4_id = fields.Many2one('lfood.cost.item', 'Cấp 4', readonly=True)
    line_name = fields.Char('Nội dung', readonly=True)
    acc_expense = fields.Char('TK chi phí', readonly=True)
    amount = fields.Float('Số tiền', digits=(16, 0), readonly=True)
    vat_amount = fields.Float('Tiền thuế', digits=(16, 0), readonly=True)
    version_number = fields.Integer('Phiên bản báo cáo', readonly=True)
    has_later_edit = fields.Boolean('Có sửa sau', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW lfood_cost_analysis AS
            SELECT l.id,
                   v.id AS voucher_id,
                   v.company_id,
                   ver.accounting_date AS date,
                   ver.partner_id,
                   l.cost_item_id,
                   NULLIF(split_part(ci.parent_path, '/', 1), '')::int AS lvl1_id,
                   NULLIF(split_part(ci.parent_path, '/', 2), '')::int AS lvl2_id,
                   NULLIF(split_part(ci.parent_path, '/', 3), '')::int AS lvl3_id,
                   NULLIF(split_part(ci.parent_path, '/', 4), '')::int AS lvl4_id,
                   l.name AS line_name,
                   l.acc_expense,
                   l.amount,
                   l.vat_amount,
                   ver.number AS version_number,
                   (v.current_version_id IS DISTINCT FROM v.report_version_id) AS has_later_edit
            FROM lfood_service_voucher_line l
            JOIN lfood_service_voucher_version ver ON ver.id = l.version_id
            JOIN lfood_service_voucher v ON v.report_version_id = ver.id
            LEFT JOIN lfood_cost_item ci ON ci.id = l.cost_item_id
            WHERE v.state IN ('posted', 'editing')
        """)
