from odoo import api, fields, models, tools


class LfoodBudgetReport(models.Model):
    """So kế hoạch với thực tế theo khoản mục và tháng.

    Kế hoạch lấy từ ngân sách đã duyệt của phiên bản mới nhất; thực tế lấy từ
    dòng bút toán đã ghi sổ có gắn khoản mục chi phí.
    """
    _name = 'lfood.budget.report'
    _description = 'Ngân sách và thực tế'
    _auto = False
    _order = 'year desc, month, cost_item_id'

    company_id = fields.Many2one('res.company', 'Công ty', readonly=True)
    year = fields.Integer('Năm', readonly=True)
    month = fields.Integer('Tháng', readonly=True)
    cost_item_id = fields.Many2one('lfood.cost.item', 'Khoản mục chi tiết', readonly=True)
    lvl1_id = fields.Many2one('lfood.cost.item', 'Cấp 1', readonly=True)
    lvl2_id = fields.Many2one('lfood.cost.item', 'Cấp 2', readonly=True)
    lvl3_id = fields.Many2one('lfood.cost.item', 'Cấp 3', readonly=True)
    lvl4_id = fields.Many2one('lfood.cost.item', 'Cấp 4', readonly=True)
    plan_amount = fields.Float('Kế hoạch', digits=(16, 0), readonly=True)
    actual_amount = fields.Float('Thực tế', digits=(16, 0), readonly=True)
    diff_amount = fields.Float('Chênh lệch', digits=(16, 0), readonly=True,
                               help='Thực tế trừ kế hoạch, dương là vượt')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW lfood_budget_report AS
            WITH newest AS (
                SELECT company_id, year, MAX(version) AS version
                FROM lfood_budget WHERE state IN ('approved', 'locked')
                GROUP BY company_id, year
            ), plan AS (
                SELECT b.company_id, b.year, l.cost_item_id, l.month::int AS month,
                       SUM(l.amount) AS amount
                FROM lfood_budget_line l
                JOIN lfood_budget b ON b.id = l.budget_id
                JOIN newest n ON n.company_id = b.company_id AND n.year = b.year AND n.version = b.version
                GROUP BY b.company_id, b.year, l.cost_item_id, l.month
            ), act AS (
                SELECT ml.company_id,
                       EXTRACT(YEAR FROM ml.date)::int AS year,
                       ml.cost_item_id,
                       EXTRACT(MONTH FROM ml.date)::int AS month,
                       SUM(COALESCE(ml.debit, 0) - COALESCE(ml.credit, 0)) AS amount
                FROM lfood_move_line ml
                WHERE ml.state = 'posted' AND ml.cost_item_id IS NOT NULL
                GROUP BY ml.company_id, EXTRACT(YEAR FROM ml.date), ml.cost_item_id, EXTRACT(MONTH FROM ml.date)
            ), joined AS (
                SELECT COALESCE(p.company_id, a.company_id) AS company_id,
                       COALESCE(p.year, a.year) AS year,
                       COALESCE(p.cost_item_id, a.cost_item_id) AS cost_item_id,
                       COALESCE(p.month, a.month) AS month,
                       COALESCE(p.amount, 0) AS plan_amount,
                       COALESCE(a.amount, 0) AS actual_amount
                FROM plan p
                FULL JOIN act a ON a.company_id = p.company_id AND a.year = p.year
                                AND a.cost_item_id = p.cost_item_id AND a.month = p.month
            )
            SELECT row_number() OVER (ORDER BY j.year, j.month, j.cost_item_id) AS id,
                   j.company_id, j.year, j.month, j.cost_item_id,
                   NULLIF(split_part(ci.parent_path, '/', 1), '')::int AS lvl1_id,
                   NULLIF(split_part(ci.parent_path, '/', 2), '')::int AS lvl2_id,
                   NULLIF(split_part(ci.parent_path, '/', 3), '')::int AS lvl3_id,
                   NULLIF(split_part(ci.parent_path, '/', 4), '')::int AS lvl4_id,
                   j.plan_amount, j.actual_amount,
                   j.actual_amount - j.plan_amount AS diff_amount
            FROM joined j
            LEFT JOIN lfood_cost_item ci ON ci.id = j.cost_item_id
        """)

    @api.model
    def actual_for(self, cost_item, year, month=None, company=None):
        """Thực tế đã ghi sổ của một khoản mục, gồm cả các khoản mục con."""
        domain = [('state', '=', 'posted'), ('company_id', '=', (company or self.env.company).id),
                  ('cost_item_id', 'child_of', cost_item.id),
                  ('date', '>=', '%s-01-01' % year), ('date', '<=', '%s-12-31' % year)]
        lines = self.env['lfood.move.line'].search(domain)
        if month:
            lines = lines.filtered(lambda l: l.date.month == int(month))
        return sum(lines.mapped('balance'))


class LfoodServiceVoucher(models.Model):
    """Cảnh báo vượt ngân sách khi Cất chứng từ, không chặn (NS03)."""
    _inherit = 'lfood.service.voucher'

    def action_post(self):
        res = super().action_post()
        Budget = self.env['lfood.budget']
        for rec in self.filtered(lambda r: r.state == 'posted'):
            for item in rec.current_version_id.line_ids.mapped('cost_item_id'):
                warning = Budget.check_over(item, rec.current_version_id.accounting_date)
                if warning:
                    self.env['lfood.audit.log']._record_event(
                        'state', model=rec._name, res_id=rec.id, res_name=rec.name,
                        summary='Vượt ngân sách. ' + warning)
        return res
