from odoo import fields, models


class LfoodMove(models.Model):
    _inherit = 'lfood.move'

    journal = fields.Selection(selection_add=[('sale', 'Bán hàng')], ondelete={'sale': 'cascade'})
