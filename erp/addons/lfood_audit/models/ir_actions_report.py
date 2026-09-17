from odoo import models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render(self, report_ref, res_ids, data=None):
        result = super()._render(report_ref, res_ids, data=data)
        report = self._get_report(report_ref)
        ids = list(res_ids or [])
        names = ''
        if report.model and ids and report.model in self.env:
            names = ', '.join(self.env[report.model].sudo().browse(ids[:10]).mapped('display_name'))
        self.env['lfood.audit.log']._record_event(
            'print', model=report.model or False, res_id=ids[0] if len(ids) == 1 else False,
            res_name=names, summary='In, xuất báo cáo "%s" cho %s bản ghi' % (report.name, len(ids)),
            changes=[{'field': 'report', 'label': 'Báo cáo', 'old': None, 'new': report.name},
                     {'field': 'ids', 'label': 'Bản ghi', 'old': None, 'new': ids[:50]}])
        return result
