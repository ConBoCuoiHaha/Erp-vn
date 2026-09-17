from odoo import fields, models, tools


class LfoodCostAnalysis(models.Model):
    """Thêm khấu hao đã ghi sổ vào báo cáo chi phí theo cây khoản mục."""
    _inherit = 'lfood.cost.analysis'

    source = fields.Selection([('voucher', 'Chứng từ mua dịch vụ'), ('depreciation', 'Khấu hao TSCĐ')],
                              'Nguồn', readonly=True)
    depreciation_id = fields.Many2one('lfood.asset.depreciation', 'Chứng từ khấu hao', readonly=True)
    asset_id = fields.Many2one('lfood.asset', 'Tài sản', readonly=True)

    # báo cho ORM ghi dữ liệu đang chờ xuống bảng trước khi đọc view
    _depends = {
        'lfood.service.voucher': ['state', 'company_id', 'current_version_id', 'report_version_id'],
        'lfood.service.voucher.version': ['accounting_date', 'partner_id', 'number'],
        'lfood.service.voucher.line': ['version_id', 'cost_item_id', 'name', 'acc_expense', 'amount', 'vat_amount'],
        'lfood.cost.item': ['parent_path'],
        'lfood.asset': ['code', 'name'],
        'lfood.asset.depreciation': ['state', 'date', 'company_id'],
        'lfood.asset.depreciation.line': ['depreciation_id', 'asset_id', 'cost_item_id', 'account_expense', 'amount'],
    }

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # id chẵn: dòng chứng từ mua; id lẻ: dòng khấu hao
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW lfood_cost_analysis AS
            SELECT l.id * 2 AS id,
                   'voucher' AS source,
                   v.id AS voucher_id,
                   NULL::int AS depreciation_id,
                   NULL::int AS asset_id,
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
            UNION ALL
            SELECT dl.id * 2 + 1,
                   'depreciation',
                   NULL::int,
                   d.id,
                   a.id,
                   d.company_id,
                   d.date,
                   NULL::int,
                   dl.cost_item_id,
                   NULLIF(split_part(ci.parent_path, '/', 1), '')::int,
                   NULLIF(split_part(ci.parent_path, '/', 2), '')::int,
                   NULLIF(split_part(ci.parent_path, '/', 3), '')::int,
                   NULLIF(split_part(ci.parent_path, '/', 4), '')::int,
                   'Khấu hao ' || a.code || ' ' || a.name,
                   dl.account_expense,
                   dl.amount,
                   0,
                   NULL::int,
                   FALSE
            FROM lfood_asset_depreciation_line dl
            JOIN lfood_asset_depreciation d ON d.id = dl.depreciation_id
            JOIN lfood_asset a ON a.id = dl.asset_id
            LEFT JOIN lfood_cost_item ci ON ci.id = dl.cost_item_id
            WHERE d.state = 'posted'
        """)
